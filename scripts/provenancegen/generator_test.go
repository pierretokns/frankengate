package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const testManifest = `{"name":"root","version":"1.0.0","scripts":{"build":"ignored"}}`
const testCreated = "2026-07-15T00:00:00Z"
const hashA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
const hashB = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
const hashC = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
const sriA = "sha512-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="

func TestOrderIndependenceAndDeterministicBytes(t *testing.T) {
	lockA := `{"lockfileVersion":3,"packages":{"node_modules/z":{"version":"2.0.0","integrity":"` + sriA + `"},"":{"name":"root","version":"1.0.0"},"node_modules/@scope/a":{"version":"3.0.0","integrity":"` + sriA + `"}}}`
	lockB := `{"packages":{"node_modules/@scope/a":{"integrity":"` + sriA + `","version":"3.0.0"},"":{"version":"1.0.0","name":"root"},"node_modules/z":{"integrity":"` + sriA + `","version":"2.0.0"}},"lockfileVersion":3}`
	evA := `{"schemaVersion":1,"packages":[{"name":"z","version":"2.0.0","licenseConcluded":"MIT","evidence":[{"path":"NOTICE","sha256":"` + hashC + `"},{"path":"LICENSE","sha256":"` + hashB + `"}]},{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]},{"name":"@scope/a","version":"3.0.0","licenseConcluded":"BSD-3-Clause","evidence":[{"path":"COPYING","sha256":"` + hashB + `"}]}]}`
	evB := `{"packages":[{"evidence":[{"sha256":"` + hashB + `","path":"COPYING"}],"licenseConcluded":"BSD-3-Clause","version":"3.0.0","name":"@scope/a"},{"version":"1.0.0","name":"root","evidence":[{"sha256":"` + hashA + `","path":"LICENSE"}],"licenseConcluded":"Apache-2.0"},{"name":"z","version":"2.0.0","evidence":[{"sha256":"` + hashB + `","path":"LICENSE"},{"sha256":"` + hashC + `","path":"NOTICE"}],"licenseConcluded":"MIT"}],"schemaVersion":1}`
	invA, spdxA, err := Generate([]byte(testManifest), []byte(lockA), []byte(evA), testCreated)
	if err != nil {
		t.Fatal(err)
	}
	invB, spdxB, err := Generate([]byte(testManifest), []byte(lockB), []byte(evB), testCreated)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(invA, invB) {
		t.Fatalf("inventory differs by input order:\n%s\n%s", invA, invB)
	}
	if !bytes.Equal(spdxA, spdxB) {
		t.Fatalf("SPDX differs by input order:\n%s\n%s", spdxA, spdxB)
	}
	if !bytes.Contains(spdxA, []byte(`"referenceLocator": "pkg:npm/%40scope/a@3.0.0"`)) {
		t.Fatalf("scoped npm PURL was not canonical:\n%s", spdxA)
	}
	invC, spdxC, err := Generate([]byte(testManifest), []byte(lockA), []byte(evA), testCreated)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(invA, invC) || !bytes.Equal(spdxA, spdxC) {
		t.Fatal("repeated generation was not byte deterministic")
	}
}

func TestMissingEvidenceFailsClosed(t *testing.T) {
	lock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"node_modules/a":{"version":"1.0.0","integrity":"` + sriA + `"}}}`
	evidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]}]}`
	_, _, err := Generate([]byte(testManifest), []byte(lock), []byte(evidence), testCreated)
	if err == nil || !strings.Contains(err.Error(), "missing license evidence for a@1.0.0") {
		t.Fatalf("expected missing-evidence failure, got %v", err)
	}
}

func TestDuplicateAndCollidingInputsFail(t *testing.T) {
	lock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"}}}`
	duplicateEvidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"MIT","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]},{"name":"root","version":"1.0.0","licenseConcluded":"MIT","evidence":[{"path":"COPYING","sha256":"` + hashB + `"}]}]}`
	if _, _, err := Generate([]byte(testManifest), []byte(lock), []byte(duplicateEvidence), testCreated); err == nil || !strings.Contains(err.Error(), "duplicate evidence") {
		t.Fatalf("expected duplicate identity failure, got %v", err)
	}
	duplicateKeyLock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"":{"name":"other","version":"2.0.0"}}}`
	if _, _, err := Generate([]byte(testManifest), []byte(duplicateKeyLock), []byte(`{"schemaVersion":1,"packages":[]}`), testCreated); err == nil || !strings.Contains(err.Error(), "duplicate object key") {
		t.Fatalf("expected duplicate JSON-key failure, got %v", err)
	}
	pathCollision := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"node_modules/a":{"name":"b","version":"1.0.0","integrity":"` + sriA + `"}}}`
	if _, _, err := Generate([]byte(testManifest), []byte(pathCollision), []byte(`{"schemaVersion":1,"packages":[]}`), testCreated); err == nil || !strings.Contains(err.Error(), "conflicts with path-derived") {
		t.Fatalf("expected path/name collision failure, got %v", err)
	}
}

func TestLinksAreExcluded(t *testing.T) {
	lock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"node_modules/workspace":{"link":true},"packages/workspace":{"name":"workspace","version":"9.9.9","link":true}}}`
	evidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]}]}`
	inv, spdx, err := Generate([]byte(testManifest), []byte(lock), []byte(evidence), testCreated)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(inv, []byte("workspace")) || bytes.Contains(spdx, []byte("workspace")) {
		t.Fatal("link package appeared in output")
	}
}

func TestDuplicatePackagePairIsOneSetMember(t *testing.T) {
	lock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"node_modules/a":{"version":"1.2.3","integrity":"` + sriA + `"},"node_modules/parent/node_modules/a":{"version":"1.2.3","integrity":"` + sriA + `"}}}`
	evidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]},{"name":"a","version":"1.2.3","licenseConcluded":"MIT","evidence":[{"path":"LICENSE","sha256":"` + hashB + `"}]}]}`
	inv, _, err := Generate([]byte(testManifest), []byte(lock), []byte(evidence), testCreated)
	if err != nil {
		t.Fatal(err)
	}
	if got := strings.Count(string(inv), "a\t1.2.3\t"); got != 1 {
		t.Fatalf("duplicate name/version pair emitted %d times", got)
	}
}

func TestIntegrityIsRequiredAndValidated(t *testing.T) {
	evidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]},{"name":"a","version":"1.0.0","licenseConcluded":"MIT","evidence":[{"path":"LICENSE","sha256":"` + hashB + `"}]}]}`
	for name, integrity := range map[string]string{"missing": "", "wrong algorithm": "sha256-AAAA", "bad base64": "sha512-not-base64", "wrong length": "sha512-AA=="} {
		t.Run(name, func(t *testing.T) {
			lock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"node_modules/a":{"version":"1.0.0","integrity":"` + integrity + `"}}}`
			if _, _, err := Generate([]byte(testManifest), []byte(lock), []byte(evidence), testCreated); err == nil || (!strings.Contains(err.Error(), "integrity") && !strings.Contains(err.Error(), "SRI")) {
				t.Fatalf("expected integrity failure, got %v", err)
			}
		})
	}
}

func TestSPDXChecksumsAndVerifierStructure(t *testing.T) {
	lock := `{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"},"node_modules/a":{"version":"1.0.0","integrity":"` + sriA + `"}}}`
	evidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","licenseDeclared":"Apache-2.0","evidence":[{"path":"LICENSE","sha256":"` + hashA + `"}]},{"name":"a","version":"1.0.0","licenseConcluded":"MIT","evidence":[{"path":"LICENSE","sha256":"` + hashB + `"}]}]}`
	_, spdx, err := Generate([]byte(testManifest), []byte(lock), []byte(evidence), testCreated)
	if err != nil {
		t.Fatal(err)
	}
	for _, marker := range [][]byte{[]byte(`"spdxVersion"`), []byte(`"SPDXID"`)} {
		if !bytes.Contains(spdx, marker) {
			t.Fatalf("missing current verifier marker %s", marker)
		}
	}
	var doc spdxDocument
	if err := json.Unmarshal(spdx, &doc); err != nil {
		t.Fatal(err)
	}
	if doc.SPDXVersion != "SPDX-2.3" || len(doc.Packages) != 2 {
		t.Fatalf("invalid SPDX document")
	}
	rootSum := sha256.Sum256([]byte(testManifest))
	for _, p := range doc.Packages {
		if len(p.Checksums) != 1 {
			t.Fatalf("package %s has %d checksums", p.Name, len(p.Checksums))
		}
		if p.Name == "root" && (p.Checksums[0].Algorithm != "SHA256" || p.Checksums[0].ChecksumValue != hex.EncodeToString(rootSum[:]) || p.LicenseDeclared != "Apache-2.0") {
			t.Fatalf("bad root fields: %#v", p)
		}
		if p.Name == "a" && (p.Checksums[0].Algorithm != "SHA512" || p.Checksums[0].ChecksumValue != strings.Repeat("00", 64) || p.LicenseDeclared != "NOASSERTION") {
			t.Fatalf("bad dependency fields: %#v", p)
		}
	}
}

func TestGenerateFilesVerifiesEvidenceContentsAndBoundary(t *testing.T) {
	makeInputs := func(t *testing.T, evidencePath, declaredHash string) (string, string, string, string) {
		t.Helper()
		dir := t.TempDir()
		if err := os.WriteFile(filepath.Join(dir, "package.json"), []byte(testManifest), 0o600); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, "package-lock.json"), []byte(`{"lockfileVersion":3,"packages":{"":{"name":"root","version":"1.0.0"}}}`), 0o600); err != nil {
			t.Fatal(err)
		}
		evidence := `{"schemaVersion":1,"packages":[{"name":"root","version":"1.0.0","licenseConcluded":"Apache-2.0","evidence":[{"path":"` + evidencePath + `","sha256":"` + declaredHash + `"}]}]}`
		if err := os.WriteFile(filepath.Join(dir, "evidence.json"), []byte(evidence), 0o600); err != nil {
			t.Fatal(err)
		}
		return dir, filepath.Join(dir, "package.json"), filepath.Join(dir, "package-lock.json"), filepath.Join(dir, "evidence.json")
	}
	t.Run("valid", func(t *testing.T) {
		contents := []byte("license text")
		s := sha256.Sum256(contents)
		dir, m, l, e := makeInputs(t, "LICENSE", hex.EncodeToString(s[:]))
		if err := os.WriteFile(filepath.Join(dir, "LICENSE"), contents, 0o600); err != nil {
			t.Fatal(err)
		}
		if _, _, err := GenerateFiles(m, l, e, dir, testCreated); err != nil {
			t.Fatal(err)
		}
	})
	t.Run("missing", func(t *testing.T) {
		dir, m, l, e := makeInputs(t, "MISSING", hashA)
		if _, _, err := GenerateFiles(m, l, e, dir, testCreated); err == nil || !strings.Contains(err.Error(), "open evidence") {
			t.Fatalf("expected missing evidence failure, got %v", err)
		}
	})
	t.Run("tampered", func(t *testing.T) {
		dir, m, l, e := makeInputs(t, "LICENSE", hashA)
		if err := os.WriteFile(filepath.Join(dir, "LICENSE"), []byte("tampered"), 0o600); err != nil {
			t.Fatal(err)
		}
		if _, _, err := GenerateFiles(m, l, e, dir, testCreated); err == nil || !strings.Contains(err.Error(), "hash mismatch") {
			t.Fatalf("expected tamper failure, got %v", err)
		}
	})
	t.Run("path escape", func(t *testing.T) {
		dir, m, l, e := makeInputs(t, "../LICENSE", hashA)
		if _, _, err := GenerateFiles(m, l, e, dir, testCreated); err == nil || !strings.Contains(err.Error(), "escapes evidence root") {
			t.Fatalf("expected escape failure, got %v", err)
		}
	})
	t.Run("symlink escape", func(t *testing.T) {
		outside := t.TempDir()
		contents := []byte("outside")
		s := sha256.Sum256(contents)
		if err := os.WriteFile(filepath.Join(outside, "LICENSE"), contents, 0o600); err != nil {
			t.Fatal(err)
		}
		dir, m, l, e := makeInputs(t, "LICENSE", hex.EncodeToString(s[:]))
		if err := os.Symlink(filepath.Join(outside, "LICENSE"), filepath.Join(dir, "LICENSE")); err != nil {
			t.Fatal(err)
		}
		if _, _, err := GenerateFiles(m, l, e, dir, testCreated); err == nil || !strings.Contains(err.Error(), "escapes evidence root through symlink") {
			t.Fatalf("expected symlink escape failure, got %v", err)
		}
	})
}
