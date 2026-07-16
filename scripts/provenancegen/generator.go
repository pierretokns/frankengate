package main

import (
	"bytes"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const inventoryHeader = "name\tversion\tpurl\tsource_checksum_algorithm\tsource_checksum\tlicense_declared\tlicense_concluded\tevidence_sha256\tevidence_paths\n"

type packageManifest struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type lockFile struct {
	LockfileVersion int                    `json:"lockfileVersion"`
	Packages        map[string]lockPackage `json:"packages"`
}

type lockPackage struct {
	Name      string `json:"name"`
	Version   string `json:"version"`
	Link      bool   `json:"link"`
	Integrity string `json:"integrity"`
}

type evidenceFile struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type evidencePackage struct {
	Name             string         `json:"name"`
	Version          string         `json:"version"`
	LicenseConcluded string         `json:"licenseConcluded"`
	LicenseDeclared  string         `json:"licenseDeclared"`
	Evidence         []evidenceFile `json:"evidence"`
}

type evidenceMap struct {
	SchemaVersion int               `json:"schemaVersion"`
	Packages      []evidencePackage `json:"packages"`
}

type resolvedPackage struct {
	Name, Version, PURL, License, EvidenceHash, EvidencePaths string
	LicenseDeclared, ChecksumAlgorithm, ChecksumValue         string
}

type spdxDocument struct {
	SPDXVersion       string             `json:"spdxVersion"`
	DataLicense       string             `json:"dataLicense"`
	SPDXID            string             `json:"SPDXID"`
	Name              string             `json:"name"`
	DocumentNamespace string             `json:"documentNamespace"`
	CreationInfo      spdxCreationInfo   `json:"creationInfo"`
	DocumentDescribes []string           `json:"documentDescribes"`
	Packages          []spdxPackage      `json:"packages"`
	Relationships     []spdxRelationship `json:"relationships"`
}

type spdxCreationInfo struct {
	Created  string   `json:"created"`
	Creators []string `json:"creators"`
}

type spdxPackage struct {
	Name                 string            `json:"name"`
	SPDXID               string            `json:"SPDXID"`
	VersionInfo          string            `json:"versionInfo"`
	DownloadLocation     string            `json:"downloadLocation"`
	FilesAnalyzed        bool              `json:"filesAnalyzed"`
	LicenseConcluded     string            `json:"licenseConcluded"`
	LicenseDeclared      string            `json:"licenseDeclared"`
	CopyrightText        string            `json:"copyrightText"`
	LicenseInfoFromFiles []string          `json:"licenseInfoFromFiles,omitempty"`
	LicenseComments      string            `json:"licenseComments"`
	ExternalRefs         []spdxExternalRef `json:"externalRefs"`
	Checksums            []spdxChecksum    `json:"checksums"`
}

type spdxExternalRef struct {
	ReferenceCategory string `json:"referenceCategory"`
	ReferenceType     string `json:"referenceType"`
	ReferenceLocator  string `json:"referenceLocator"`
}

type spdxChecksum struct {
	Algorithm     string `json:"algorithm"`
	ChecksumValue string `json:"checksumValue"`
}

type spdxRelationship struct {
	SPDXElementID      string `json:"spdxElementId"`
	RelationshipType   string `json:"relationshipType"`
	RelatedSPDXElement string `json:"relatedSpdxElement"`
}

func GenerateFiles(packageJSONPath, lockPath, evidencePath, evidenceRoot, created string) ([]byte, []byte, error) {
	manifest, err := os.ReadFile(packageJSONPath)
	if err != nil {
		return nil, nil, fmt.Errorf("read package.json: %w", err)
	}
	lock, err := os.ReadFile(lockPath)
	if err != nil {
		return nil, nil, fmt.Errorf("read package lock: %w", err)
	}
	evidence, err := os.ReadFile(evidencePath)
	if err != nil {
		return nil, nil, fmt.Errorf("read evidence: %w", err)
	}
	if evidenceRoot == "" {
		evidenceRoot = filepath.Dir(evidencePath)
	}
	if err := verifyEvidenceFiles(evidence, evidenceRoot); err != nil {
		return nil, nil, err
	}
	return Generate(manifest, lock, evidence, created)
}

// Generate validates the structure and hashes declared by its byte inputs and
// produces deterministic artifacts. It does not open evidence paths and is not
// a trusted file-verification boundary; CLI callers must use GenerateFiles.
func Generate(manifestBytes, lockBytes, evidenceBytes []byte, created string) ([]byte, []byte, error) {
	for label, data := range map[string][]byte{"package.json": manifestBytes, "package-lock.json": lockBytes, "evidence": evidenceBytes} {
		if err := rejectDuplicateJSONKeys(data); err != nil {
			return nil, nil, fmt.Errorf("%s: %w", label, err)
		}
	}
	var manifest packageManifest
	var lock lockFile
	var evidence evidenceMap
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return nil, nil, fmt.Errorf("package.json: %w", err)
	}
	if err := json.Unmarshal(lockBytes, &lock); err != nil {
		return nil, nil, fmt.Errorf("package-lock.json: %w", err)
	}
	if err := strictUnmarshal(evidenceBytes, &evidence); err != nil {
		return nil, nil, fmt.Errorf("evidence: %w", err)
	}
	if manifest.Name == "" || manifest.Version == "" {
		return nil, nil, errors.New("package.json name and version are required")
	}
	if lock.LockfileVersion != 3 {
		return nil, nil, fmt.Errorf("lockfileVersion must be 3, got %d", lock.LockfileVersion)
	}
	if evidence.SchemaVersion != 1 {
		return nil, nil, fmt.Errorf("evidence schemaVersion must be 1, got %d", evidence.SchemaVersion)
	}
	if _, err := time.Parse(time.RFC3339, created); err != nil {
		return nil, nil, fmt.Errorf("invalid created time: %w", err)
	}

	identities, err := packageSet(manifest, lock, manifestBytes)
	if err != nil {
		return nil, nil, err
	}
	resolved, err := bindEvidence(identities, evidence)
	if err != nil {
		return nil, nil, err
	}
	return inventoryBytes(resolved), spdxBytes(resolved, manifest, created), nil
}

type packageIdentity struct {
	packageManifest
	ChecksumAlgorithm string
	ChecksumValue     string
}

func packageSet(manifest packageManifest, lock lockFile, manifestBytes []byte) ([]packageIdentity, error) {
	root, ok := lock.Packages[""]
	if !ok {
		return nil, errors.New("package lock has no root packages entry")
	}
	if root.Link {
		return nil, errors.New("root package cannot be a link")
	}
	if root.Name != "" && root.Name != manifest.Name {
		return nil, fmt.Errorf("root name mismatch: package.json=%q lock=%q", manifest.Name, root.Name)
	}
	if root.Version != "" && root.Version != manifest.Version {
		return nil, fmt.Errorf("root version mismatch: package.json=%q lock=%q", manifest.Version, root.Version)
	}

	set := map[string]packageIdentity{}
	manifestSum := sha256.Sum256(manifestBytes)
	add := func(p packageIdentity) error {
		key := identityKey(p.Name, p.Version)
		if prior, exists := set[key]; exists && (prior.ChecksumAlgorithm != p.ChecksumAlgorithm || prior.ChecksumValue != p.ChecksumValue) {
			return fmt.Errorf("package %s has colliding source checksums", key)
		}
		set[key] = p
		return nil
	}
	if err := add(packageIdentity{packageManifest: manifest, ChecksumAlgorithm: "SHA256", ChecksumValue: hex.EncodeToString(manifestSum[:])}); err != nil {
		return nil, err
	}
	paths := make([]string, 0, len(lock.Packages))
	for path := range lock.Packages {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	for _, path := range paths {
		if path == "" {
			continue
		}
		p := lock.Packages[path]
		if p.Link {
			continue
		}
		name, err := packageNameFromPath(path)
		if err != nil {
			return nil, err
		}
		if p.Name != "" && p.Name != name {
			return nil, fmt.Errorf("package %q name %q conflicts with path-derived name %q", path, p.Name, name)
		}
		if p.Version == "" {
			return nil, fmt.Errorf("package %q has no version", path)
		}
		integrity, err := parseSHA512SRI(p.Integrity)
		if err != nil {
			return nil, fmt.Errorf("package %q: %w", path, err)
		}
		if err := add(packageIdentity{packageManifest: packageManifest{Name: name, Version: p.Version}, ChecksumAlgorithm: "SHA512", ChecksumValue: integrity}); err != nil {
			return nil, err
		}
	}
	out := make([]packageIdentity, 0, len(set))
	for _, p := range set {
		out = append(out, p)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Name != out[j].Name {
			return out[i].Name < out[j].Name
		}
		return out[i].Version < out[j].Version
	})
	return out, nil
}

func packageNameFromPath(path string) (string, error) {
	const marker = "node_modules/"
	i := strings.LastIndex(path, marker)
	if i < 0 {
		return "", fmt.Errorf("non-link package path %q is not under node_modules", path)
	}
	name := path[i+len(marker):]
	if name == "" || strings.Contains(name, "/node_modules/") || strings.Count(name, "/") > 1 || (strings.HasPrefix(name, "@") && strings.Count(name, "/") != 1) {
		return "", fmt.Errorf("invalid package path %q", path)
	}
	return name, nil
}

func parseSHA512SRI(integrity string) (string, error) {
	if integrity == "" {
		return "", errors.New("missing sha512 integrity")
	}
	parts := strings.Fields(integrity)
	if len(parts) != 1 || !strings.HasPrefix(parts[0], "sha512-") {
		return "", fmt.Errorf("integrity must be exactly one sha512 SRI value, got %q", integrity)
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(parts[0], "sha512-"))
	if err != nil || len(raw) != sha512.Size {
		return "", fmt.Errorf("invalid sha512 SRI %q", integrity)
	}
	return hex.EncodeToString(raw), nil
}

func verifyEvidenceFiles(evidenceBytes []byte, root string) error {
	if err := rejectDuplicateJSONKeys(evidenceBytes); err != nil {
		return fmt.Errorf("evidence: %w", err)
	}
	var evidence evidenceMap
	if err := strictUnmarshal(evidenceBytes, &evidence); err != nil {
		return fmt.Errorf("evidence: %w", err)
	}
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return fmt.Errorf("resolve evidence root: %w", err)
	}
	rootResolved, err := filepath.EvalSymlinks(rootAbs)
	if err != nil {
		return fmt.Errorf("resolve evidence root: %w", err)
	}
	for _, pkg := range evidence.Packages {
		for _, item := range pkg.Evidence {
			if filepath.IsAbs(item.Path) {
				return fmt.Errorf("evidence path %q is absolute", item.Path)
			}
			clean := filepath.Clean(filepath.FromSlash(item.Path))
			if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
				return fmt.Errorf("evidence path %q escapes evidence root", item.Path)
			}
			candidate := filepath.Join(rootResolved, clean)
			resolved, err := filepath.EvalSymlinks(candidate)
			if err != nil {
				return fmt.Errorf("open evidence %q for %s: %w", item.Path, identityKey(pkg.Name, pkg.Version), err)
			}
			rel, err := filepath.Rel(rootResolved, resolved)
			if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
				return fmt.Errorf("evidence path %q escapes evidence root through symlink", item.Path)
			}
			info, err := os.Stat(resolved)
			if err != nil {
				return fmt.Errorf("stat evidence %q: %w", item.Path, err)
			}
			if !info.Mode().IsRegular() {
				return fmt.Errorf("evidence path %q is not a regular file", item.Path)
			}
			contents, err := os.ReadFile(resolved)
			if err != nil {
				return fmt.Errorf("read evidence %q: %w", item.Path, err)
			}
			sum := sha256.Sum256(contents)
			actual := hex.EncodeToString(sum[:])
			if !strings.EqualFold(actual, item.SHA256) {
				return fmt.Errorf("evidence hash mismatch for %q: declared %s, computed %s", item.Path, item.SHA256, actual)
			}
		}
	}
	return nil
}

func bindEvidence(packages []packageIdentity, evidence evidenceMap) ([]resolvedPackage, error) {
	byID := make(map[string]evidencePackage, len(evidence.Packages))
	for _, e := range evidence.Packages {
		key := identityKey(e.Name, e.Version)
		if e.Name == "" || e.Version == "" {
			return nil, errors.New("evidence package name and version are required")
		}
		if _, exists := byID[key]; exists {
			return nil, fmt.Errorf("duplicate evidence for %s", key)
		}
		if e.LicenseConcluded == "" || e.LicenseConcluded == "NOASSERTION" || e.LicenseConcluded == "NONE" {
			return nil, fmt.Errorf("package %s has no concluded license", key)
		}
		if e.LicenseDeclared == "" {
			e.LicenseDeclared = "NOASSERTION"
		}
		if e.LicenseDeclared == "NONE" {
			return nil, fmt.Errorf("package %s has invalid declared license NONE", key)
		}
		if len(e.Evidence) == 0 {
			return nil, fmt.Errorf("package %s has no license evidence", key)
		}
		seenPaths := map[string]bool{}
		for _, f := range e.Evidence {
			if f.Path == "" || strings.HasPrefix(f.Path, "/") || strings.Contains(f.Path, "..") || strings.ContainsAny(f.Path, "\t\r\n") {
				return nil, fmt.Errorf("package %s has invalid evidence path %q", key, f.Path)
			}
			if seenPaths[f.Path] {
				return nil, fmt.Errorf("package %s repeats evidence path %q", key, f.Path)
			}
			seenPaths[f.Path] = true
			if len(f.SHA256) != 64 {
				return nil, fmt.Errorf("package %s evidence %q has invalid SHA-256", key, f.Path)
			}
			if _, err := hex.DecodeString(f.SHA256); err != nil {
				return nil, fmt.Errorf("package %s evidence %q has invalid SHA-256", key, f.Path)
			}
		}
		byID[key] = e
	}
	resolved := make([]resolvedPackage, 0, len(packages))
	used := map[string]bool{}
	for _, p := range packages {
		key := identityKey(p.Name, p.Version)
		e, ok := byID[key]
		if !ok {
			return nil, fmt.Errorf("missing license evidence for %s", key)
		}
		used[key] = true
		sort.Slice(e.Evidence, func(i, j int) bool {
			if e.Evidence[i].Path != e.Evidence[j].Path {
				return e.Evidence[i].Path < e.Evidence[j].Path
			}
			return e.Evidence[i].SHA256 < e.Evidence[j].SHA256
		})
		var paths []string
		h := sha256.New()
		for _, f := range e.Evidence {
			paths = append(paths, f.Path)
			fmt.Fprintf(h, "%s\x00%s\x00", f.Path, strings.ToLower(f.SHA256))
		}
		resolved = append(resolved, resolvedPackage{Name: p.Name, Version: p.Version, PURL: npmPURL(p.Name, p.Version), License: e.LicenseConcluded, LicenseDeclared: e.LicenseDeclared, EvidenceHash: hex.EncodeToString(h.Sum(nil)), EvidencePaths: strings.Join(paths, ","), ChecksumAlgorithm: p.ChecksumAlgorithm, ChecksumValue: p.ChecksumValue})
	}
	for key := range byID {
		if !used[key] {
			return nil, fmt.Errorf("evidence contains package absent from lock closure: %s", key)
		}
	}
	return resolved, nil
}

func inventoryBytes(packages []resolvedPackage) []byte {
	var b strings.Builder
	b.WriteString(inventoryHeader)
	for _, p := range packages {
		fmt.Fprintf(&b, "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", p.Name, p.Version, p.PURL, p.ChecksumAlgorithm, p.ChecksumValue, p.LicenseDeclared, p.License, p.EvidenceHash, p.EvidencePaths)
	}
	return []byte(b.String())
}

func spdxBytes(packages []resolvedPackage, root packageManifest, created string) []byte {
	inputHash := sha256.New()
	for _, p := range packages {
		fmt.Fprintf(inputHash, "%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00", p.PURL, p.ChecksumAlgorithm, p.ChecksumValue, p.LicenseDeclared, p.License, p.EvidenceHash, p.EvidencePaths)
	}
	docHash := hex.EncodeToString(inputHash.Sum(nil))
	rootID := spdxID(root.Name, root.Version)
	doc := spdxDocument{SPDXVersion: "SPDX-2.3", DataLicense: "CC0-1.0", SPDXID: "SPDXRef-DOCUMENT", Name: root.Name + "-npm-closure", DocumentNamespace: "https://github.com/pierretokns/frankengate/spdx/npm/" + docHash, CreationInfo: spdxCreationInfo{Created: created, Creators: []string{"Tool: frankengate-provenancegen-1"}}, DocumentDescribes: []string{rootID}}
	for _, p := range packages {
		id := spdxID(p.Name, p.Version)
		doc.Packages = append(doc.Packages, spdxPackage{Name: p.Name, SPDXID: id, VersionInfo: p.Version, DownloadLocation: "NOASSERTION", FilesAnalyzed: false, LicenseConcluded: p.License, LicenseDeclared: p.LicenseDeclared, CopyrightText: "NOASSERTION", LicenseComments: "Hash-bound license evidence aggregate SHA256: " + p.EvidenceHash + "; paths: " + p.EvidencePaths, ExternalRefs: []spdxExternalRef{{ReferenceCategory: "PACKAGE-MANAGER", ReferenceType: "purl", ReferenceLocator: p.PURL}}, Checksums: []spdxChecksum{{Algorithm: p.ChecksumAlgorithm, ChecksumValue: p.ChecksumValue}}})
		if id != rootID {
			doc.Relationships = append(doc.Relationships, spdxRelationship{SPDXElementID: rootID, RelationshipType: "DEPENDS_ON", RelatedSPDXElement: id})
		}
	}
	sort.Slice(doc.Relationships, func(i, j int) bool {
		return doc.Relationships[i].RelatedSPDXElement < doc.Relationships[j].RelatedSPDXElement
	})
	b, _ := json.MarshalIndent(doc, "", "  ")
	return append(b, '\n')
}

func identityKey(name, version string) string { return name + "@" + version }
func npmPURL(name, version string) string {
	escapedName := url.PathEscape(name)
	if strings.HasPrefix(name, "@") {
		parts := strings.Split(name, "/")
		if len(parts) == 2 {
			escapedName = "%40" + url.PathEscape(strings.TrimPrefix(parts[0], "@")) + "/" + url.PathEscape(parts[1])
		}
	}
	return "pkg:npm/" + escapedName + "@" + url.PathEscape(version)
}
func spdxID(name, version string) string {
	h := sha256.Sum256([]byte(identityKey(name, version)))
	return "SPDXRef-Package-" + hex.EncodeToString(h[:16])
}

func strictUnmarshal(data []byte, dst any) error {
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(dst); err != nil {
		return err
	}
	if d.More() {
		return errors.New("trailing JSON value")
	}
	return nil
}

func rejectDuplicateJSONKeys(data []byte) error {
	d := json.NewDecoder(bytes.NewReader(data))
	var walk func() error
	walk = func() error {
		t, err := d.Token()
		if err != nil {
			return err
		}
		delim, ok := t.(json.Delim)
		if !ok {
			return nil
		}
		switch delim {
		case '{':
			seen := map[string]bool{}
			for d.More() {
				k, err := d.Token()
				if err != nil {
					return err
				}
				key := k.(string)
				if seen[key] {
					return fmt.Errorf("duplicate object key %q", key)
				}
				seen[key] = true
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = d.Token()
			return err
		case '[':
			for d.More() {
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = d.Token()
			return err
		default:
			return fmt.Errorf("unexpected delimiter %q", delim)
		}
	}
	if err := walk(); err != nil {
		return err
	}
	if _, err := d.Token(); err == nil {
		return errors.New("trailing JSON value")
	}
	return nil
}
