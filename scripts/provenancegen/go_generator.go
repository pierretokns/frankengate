package main

import (
	"crypto/sha256"
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

const goInventoryHeader = "path\tversion\tpurl\tdirectness\toriginal_path\toriginal_version\teffective_path\teffective_version\tgo_sum\tgo_mod_sum\tsource_archive_sha256\tlicense_declared\tlicense_concluded\tevidence_sha256\tevidence_paths\n"

type goProvenanceLock struct {
	SchemaVersion         int              `json:"schemaVersion"`
	ModuleCount           int              `json:"moduleCount"`
	SelectedModulesSHA256 string           `json:"selectedModulesSha256"`
	Manifest              goInputFile      `json:"manifest"`
	GoSum                 goInputFile      `json:"goSum"`
	Root                  goLockedModule   `json:"root"`
	Modules               []goLockedModule `json:"modules"`
}

type goInputFile struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}
type goReplacement struct {
	Path    string `json:"path"`
	Version string `json:"version"`
}
type goSourceArchive struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}
type goLockedModule struct {
	Path             string          `json:"path"`
	Version          string          `json:"version"`
	Indirect         bool            `json:"indirect"`
	Sum              string          `json:"sum"`
	GoModSum         string          `json:"goModSum"`
	Replacement      *goReplacement  `json:"replacement,omitempty"`
	SourceArchive    goSourceArchive `json:"sourceArchive"`
	LicenseDeclared  string          `json:"licenseDeclared"`
	LicenseConcluded string          `json:"licenseConcluded"`
	Evidence         []evidenceFile  `json:"evidence"`
}

type resolvedGoModule struct {
	OriginalPath, OriginalVersion, EffectivePath, EffectiveVersion string
	PURL, Directness, Sum, GoModSum, SourceSHA256                  string
	LicenseDeclared, LicenseConcluded, EvidenceHash, EvidencePaths string
}

// GenerateGo is structural-only: it verifies lock shape and manifest/go.sum
// byte bindings but does not open source archives or license evidence. Trusted
// callers must use GenerateGoFiles.
func GenerateGo(lockBytes, manifestBytes, goSumBytes []byte, created string) ([]byte, []byte, error) {
	if err := rejectDuplicateJSONKeys(lockBytes); err != nil {
		return nil, nil, fmt.Errorf("Go provenance lock: %w", err)
	}
	var lock goProvenanceLock
	if err := strictUnmarshal(lockBytes, &lock); err != nil {
		return nil, nil, fmt.Errorf("Go provenance lock: %w", err)
	}
	if lock.SchemaVersion != 1 {
		return nil, nil, fmt.Errorf("Go provenance schemaVersion must be 1, got %d", lock.SchemaVersion)
	}
	if _, err := time.Parse(time.RFC3339, created); err != nil {
		return nil, nil, fmt.Errorf("invalid created time: %w", err)
	}
	if err := verifyInputBinding(lock.Manifest, manifestBytes, "manifest"); err != nil {
		return nil, nil, err
	}
	if err := verifyInputBinding(lock.GoSum, goSumBytes, "go.sum"); err != nil {
		return nil, nil, err
	}
	mods, err := resolveGoModules(lock)
	if err != nil {
		return nil, nil, err
	}
	if lock.ModuleCount != len(mods) {
		return nil, nil, fmt.Errorf("selected module count mismatch: lock=%d actual=%d", lock.ModuleCount, len(mods))
	}
	selectedHash := goSelectionHash(mods)
	if !strings.EqualFold(lock.SelectedModulesSHA256, selectedHash) {
		return nil, nil, fmt.Errorf("stale selected-module binding: declared %s computed %s", lock.SelectedModulesSHA256, selectedHash)
	}
	return goInventoryBytes(mods), goSPDXBytes(mods, lock.Root, lock.Manifest, lock.GoSum, created), nil
}

func GenerateGoFiles(lockPath, manifestPath, goSumPath, sourceRoot, evidenceRoot, created string) ([]byte, []byte, error) {
	lockBytes, err := os.ReadFile(lockPath)
	if err != nil {
		return nil, nil, fmt.Errorf("read Go provenance lock: %w", err)
	}
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, nil, fmt.Errorf("read manifest: %w", err)
	}
	goSumBytes, err := os.ReadFile(goSumPath)
	if err != nil {
		return nil, nil, fmt.Errorf("read go.sum: %w", err)
	}
	var lock goProvenanceLock
	if err := rejectDuplicateJSONKeys(lockBytes); err != nil {
		return nil, nil, err
	}
	if err := strictUnmarshal(lockBytes, &lock); err != nil {
		return nil, nil, err
	}
	if sourceRoot == "" {
		sourceRoot = filepath.Dir(lockPath)
	}
	if evidenceRoot == "" {
		evidenceRoot = filepath.Dir(lockPath)
	}
	all := append([]goLockedModule{lock.Root}, lock.Modules...)
	for _, m := range all {
		if err := verifyBoundedHash(sourceRoot, m.SourceArchive.Path, m.SourceArchive.SHA256, "source archive for "+m.Path); err != nil {
			return nil, nil, err
		}
		for _, e := range m.Evidence {
			if err := verifyBoundedHash(evidenceRoot, e.Path, e.SHA256, "license evidence for "+m.Path); err != nil {
				return nil, nil, err
			}
		}
	}
	return GenerateGo(lockBytes, manifestBytes, goSumBytes, created)
}

func verifyInputBinding(input goInputFile, data []byte, label string) error {
	if input.Path == "" {
		return fmt.Errorf("%s path is required", label)
	}
	if err := validSHA256(input.SHA256); err != nil {
		return fmt.Errorf("%s has invalid SHA-256", label)
	}
	s := sha256.Sum256(data)
	if !strings.EqualFold(input.SHA256, hex.EncodeToString(s[:])) {
		return fmt.Errorf("stale %s binding: declared %s computed %s", label, input.SHA256, hex.EncodeToString(s[:]))
	}
	return nil
}

func resolveGoModules(lock goProvenanceLock) ([]resolvedGoModule, error) {
	all := append([]goLockedModule{lock.Root}, lock.Modules...)
	seenOriginal := map[string]bool{}
	seenEffective := map[string]string{}
	out := make([]resolvedGoModule, 0, len(all))
	for i, m := range all {
		if m.Path == "" || m.Version == "" || m.Version == "(devel)" {
			return nil, fmt.Errorf("module %d has unversioned/devel coordinates", i)
		}
		if i == 0 && m.Indirect {
			return nil, errors.New("root module cannot be indirect")
		}
		if i > 0 && (m.Sum == "" || m.GoModSum == "") {
			return nil, fmt.Errorf("external module %s@%s lacks Go Sum or GoModSum", m.Path, m.Version)
		}
		if i > 0 {
			if validGoSum(m.Sum) != nil || validGoSum(m.GoModSum) != nil {
				return nil, fmt.Errorf("external module %s@%s has invalid Go Sum or GoModSum", m.Path, m.Version)
			}
		}
		if err := validSHA256(m.SourceArchive.SHA256); err != nil {
			return nil, fmt.Errorf("module %s@%s has invalid source archive SHA-256", m.Path, m.Version)
		}
		if m.SourceArchive.Path == "" {
			return nil, fmt.Errorf("module %s@%s has no source archive path", m.Path, m.Version)
		}
		if err := validRelativePath(m.SourceArchive.Path); err != nil {
			return nil, fmt.Errorf("module %s@%s has invalid source archive path: %w", m.Path, m.Version, err)
		}
		if m.LicenseDeclared == "" {
			m.LicenseDeclared = "NOASSERTION"
		}
		if m.LicenseConcluded == "" || m.LicenseConcluded == "NONE" || m.LicenseConcluded == "NOASSERTION" {
			return nil, fmt.Errorf("module %s@%s lacks concluded license", m.Path, m.Version)
		}
		if len(m.Evidence) == 0 {
			return nil, fmt.Errorf("module %s@%s lacks license evidence", m.Path, m.Version)
		}
		effectivePath, effectiveVersion := m.Path, m.Version
		if m.Replacement != nil {
			if m.Replacement.Path == "" || m.Replacement.Version == "" || m.Replacement.Version == "(devel)" {
				return nil, fmt.Errorf("module %s@%s has malformed/unversioned replacement", m.Path, m.Version)
			}
			effectivePath, effectiveVersion = m.Replacement.Path, m.Replacement.Version
		}
		originalKey := identityKey(m.Path, m.Version)
		if seenOriginal[originalKey] {
			return nil, fmt.Errorf("duplicate original module %s", originalKey)
		}
		seenOriginal[originalKey] = true
		effectiveKey := identityKey(effectivePath, effectiveVersion)
		if prior, ok := seenEffective[effectiveKey]; ok && prior != originalKey {
			return nil, fmt.Errorf("effective module collision: %s replaces both %s and %s", effectiveKey, prior, originalKey)
		}
		seenEffective[effectiveKey] = originalKey
		sort.Slice(m.Evidence, func(i, j int) bool {
			if m.Evidence[i].Path != m.Evidence[j].Path {
				return m.Evidence[i].Path < m.Evidence[j].Path
			}
			return m.Evidence[i].SHA256 < m.Evidence[j].SHA256
		})
		paths := []string{}
		h := sha256.New()
		seenPaths := map[string]bool{}
		for _, e := range m.Evidence {
			if e.Path == "" || validRelativePath(e.Path) != nil || seenPaths[e.Path] || validSHA256(e.SHA256) != nil {
				return nil, fmt.Errorf("module %s@%s has invalid/duplicate evidence", m.Path, m.Version)
			}
			seenPaths[e.Path] = true
			paths = append(paths, e.Path)
			fmt.Fprintf(h, "%s\x00%s\x00", e.Path, strings.ToLower(e.SHA256))
		}
		direct := "direct"
		if m.Indirect {
			direct = "indirect"
		}
		out = append(out, resolvedGoModule{OriginalPath: m.Path, OriginalVersion: m.Version, EffectivePath: effectivePath, EffectiveVersion: effectiveVersion, PURL: goPURL(effectivePath, effectiveVersion), Directness: direct, Sum: m.Sum, GoModSum: m.GoModSum, SourceSHA256: strings.ToLower(m.SourceArchive.SHA256), LicenseDeclared: m.LicenseDeclared, LicenseConcluded: m.LicenseConcluded, EvidenceHash: hex.EncodeToString(h.Sum(nil)), EvidencePaths: strings.Join(paths, ",")})
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].PURL != out[j].PURL {
			return out[i].PURL < out[j].PURL
		}
		return out[i].OriginalPath < out[j].OriginalPath
	})
	return out, nil
}

func goInventoryBytes(mods []resolvedGoModule) []byte {
	var b strings.Builder
	b.WriteString(goInventoryHeader)
	for _, m := range mods {
		fmt.Fprintf(&b, "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", m.EffectivePath, m.EffectiveVersion, m.PURL, m.Directness, m.OriginalPath, m.OriginalVersion, m.EffectivePath, m.EffectiveVersion, m.Sum, m.GoModSum, m.SourceSHA256, m.LicenseDeclared, m.LicenseConcluded, m.EvidenceHash, m.EvidencePaths)
	}
	return []byte(b.String())
}

func goSelectionHash(mods []resolvedGoModule) string {
	h := sha256.New()
	for _, m := range mods {
		fmt.Fprintf(h, "%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00%s\x00", m.OriginalPath, m.OriginalVersion, m.EffectivePath, m.EffectiveVersion, m.Sum, m.GoModSum, m.SourceSHA256, m.LicenseDeclared, m.LicenseConcluded, m.EvidenceHash)
	}
	return hex.EncodeToString(h.Sum(nil))
}

func goSPDXBytes(mods []resolvedGoModule, root goLockedModule, manifest, goSum goInputFile, created string) []byte {
	h := sha256.New()
	for _, m := range mods {
		fmt.Fprintf(h, "%s\x00%s\x00%s\x00%s\x00%s\x00", m.PURL, m.SourceSHA256, m.LicenseDeclared, m.LicenseConcluded, m.EvidenceHash)
	}
	fmt.Fprintf(h, "%s\x00%s\x00", manifest.SHA256, goSum.SHA256)
	namespace := hex.EncodeToString(h.Sum(nil))
	rootPath, rootVersion := root.Path, root.Version
	if root.Replacement != nil {
		rootPath, rootVersion = root.Replacement.Path, root.Replacement.Version
	}
	rootID := spdxID(rootPath, rootVersion)
	doc := spdxDocument{SPDXVersion: "SPDX-2.3", DataLicense: "CC0-1.0", SPDXID: "SPDXRef-DOCUMENT", Name: rootPath + "-go-closure", DocumentNamespace: "https://github.com/pierretokns/frankengate/spdx/go/" + namespace, CreationInfo: spdxCreationInfo{Created: created, Creators: []string{"Tool: frankengate-provenancegen-1"}}, DocumentDescribes: []string{rootID}}
	for _, m := range mods {
		id := spdxID(m.EffectivePath, m.EffectiveVersion)
		comments := "Go Sum: " + m.Sum + "; GoModSum: " + m.GoModSum + "; license evidence SHA256: " + m.EvidenceHash
		if m.OriginalPath != m.EffectivePath || m.OriginalVersion != m.EffectiveVersion {
			comments += "; replaces " + m.OriginalPath + "@" + m.OriginalVersion
		}
		doc.Packages = append(doc.Packages, spdxPackage{Name: m.EffectivePath, SPDXID: id, VersionInfo: m.EffectiveVersion, DownloadLocation: "NOASSERTION", FilesAnalyzed: false, LicenseConcluded: m.LicenseConcluded, LicenseDeclared: m.LicenseDeclared, CopyrightText: "NOASSERTION", LicenseComments: comments, ExternalRefs: []spdxExternalRef{{ReferenceCategory: "PACKAGE-MANAGER", ReferenceType: "purl", ReferenceLocator: m.PURL}}, Checksums: []spdxChecksum{{Algorithm: "SHA256", ChecksumValue: m.SourceSHA256}}})
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

func goPURL(path, version string) string {
	parts := strings.Split(path, "/")
	for i := range parts {
		parts[i] = url.PathEscape(parts[i])
	}
	return "pkg:golang/" + strings.Join(parts, "/") + "@" + url.PathEscape(version)
}
func validSHA256(s string) error {
	if len(s) != 64 {
		return errors.New("wrong length")
	}
	_, err := hex.DecodeString(s)
	return err
}
func validGoSum(s string) error {
	if !strings.HasPrefix(s, "h1:") {
		return errors.New("missing h1 prefix")
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(s, "h1:"))
	if err != nil || len(raw) != 32 {
		return errors.New("invalid h1 digest")
	}
	return nil
}
func validRelativePath(path string) error {
	if filepath.IsAbs(path) {
		return errors.New("absolute path")
	}
	clean := filepath.Clean(filepath.FromSlash(path))
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return errors.New("path escapes root")
	}
	return nil
}

func verifyBoundedHash(root, path, want, label string) error {
	if validSHA256(want) != nil {
		return fmt.Errorf("%s has invalid declared SHA-256", label)
	}
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return err
	}
	rootResolved, err := filepath.EvalSymlinks(rootAbs)
	if err != nil {
		return fmt.Errorf("resolve root for %s: %w", label, err)
	}
	if filepath.IsAbs(path) {
		return fmt.Errorf("%s path %q is absolute", label, path)
	}
	clean := filepath.Clean(filepath.FromSlash(path))
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return fmt.Errorf("%s path %q escapes root", label, path)
	}
	resolved, err := filepath.EvalSymlinks(filepath.Join(rootResolved, clean))
	if err != nil {
		return fmt.Errorf("open %s: %w", label, err)
	}
	rel, err := filepath.Rel(rootResolved, resolved)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return fmt.Errorf("%s path %q escapes root through symlink", label, path)
	}
	info, err := os.Stat(resolved)
	if err != nil || !info.Mode().IsRegular() {
		return fmt.Errorf("%s is not a regular file", label)
	}
	data, err := os.ReadFile(resolved)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(data)
	got := hex.EncodeToString(sum[:])
	if !strings.EqualFold(got, want) {
		return fmt.Errorf("%s hash mismatch: declared %s computed %s", label, want, got)
	}
	return nil
}
