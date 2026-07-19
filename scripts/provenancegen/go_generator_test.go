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

const goH1 = "h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

func sumBytes(b []byte) string { s := sha256.Sum256(b); return hex.EncodeToString(s[:]) }
func goModule(path, version, archive, archiveSum, licensePath, licenseSum string, indirect bool) goLockedModule {
	return goLockedModule{Path: path, Version: version, Indirect: indirect, Sum: goH1, GoModSum: goH1, SourceArchive: goSourceArchive{Path: archive, SHA256: archiveSum}, LicenseConcluded: "Apache-2.0", LicenseDeclared: "Apache-2.0", Evidence: []evidenceFile{{Path: licensePath, SHA256: licenseSum}}}
}
func goLockFixture(manifest, gosum []byte, modules []goLockedModule) goProvenanceLock {
	root := goModule("example.com/root", "v1.0.0", "root.zip", hashA, "root-LICENSE", hashB, false)
	root.Sum = ""
	root.GoModSum = ""
	lock := goProvenanceLock{SchemaVersion: 1, Manifest: goInputFile{Path: "go.mod", SHA256: sumBytes(manifest)}, GoSum: goInputFile{Path: "go.sum", SHA256: sumBytes(gosum)}, Root: root, Modules: modules}
	return sealGoLock(lock)
}
func sealGoLock(lock goProvenanceLock) goProvenanceLock {
	mods, err := resolveGoModules(lock)
	if err != nil {
		panic(err)
	}
	lock.ModuleCount = len(mods)
	lock.SelectedModulesSHA256 = goSelectionHash(mods)
	return lock
}
func marshalLock(t *testing.T, v any) []byte {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestGoDeterministicOrderAndReplacement(t *testing.T) {
	manifest := []byte("module example.com/root\n")
	gosum := []byte("example sums\n")
	a := goModule("old.example/mod", "v1.2.0", "a.zip", hashB, "a-LICENSE", hashC, false)
	a.Replacement = &goReplacement{Path: "fork.example/mod", Version: "v1.2.1"}
	b := goModule("example.com/indirect", "v2.0.0", "b.zip", hashC, "b-LICENSE", hashA, true)
	l1 := goLockFixture(manifest, gosum, []goLockedModule{b, a})
	l2 := goLockFixture(manifest, gosum, []goLockedModule{a, b})
	i1, s1, err := GenerateGo(marshalLock(t, l1), manifest, gosum, testCreated)
	if err != nil {
		t.Fatal(err)
	}
	i2, s2, err := GenerateGo(marshalLock(t, l2), manifest, gosum, testCreated)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(i1, i2) || !bytes.Equal(s1, s2) {
		t.Fatal("Go output depends on module order")
	}
	i3, s3, err := GenerateGo(marshalLock(t, l1), manifest, gosum, testCreated)
	if err != nil || !bytes.Equal(i1, i3) || !bytes.Equal(s1, s3) {
		t.Fatal("Go output is not byte deterministic")
	}
	if !bytes.Contains(i1, []byte("pkg:golang/fork.example/mod@v1.2.1")) || !bytes.Contains(s1, []byte("replaces old.example/mod@v1.2.0")) {
		t.Fatal("replacement coordinates not explicit")
	}
}

func TestGoMalformedMissingExtraCollisionAndStale(t *testing.T) {
	manifest := []byte("module x\n")
	gosum := []byte("sum\n")
	base := goModule("example.com/a", "v1.0.0", "a.zip", hashA, "LICENSE", hashB, false)
	tests := map[string]func(*goProvenanceLock){"devel": func(l *goProvenanceLock) { l.Modules[0].Version = "(devel)" }, "missing evidence": func(l *goProvenanceLock) { l.Modules[0].Evidence = nil }, "bad source hash": func(l *goProvenanceLock) { l.Modules[0].SourceArchive.SHA256 = "bad" }, "malformed replacement": func(l *goProvenanceLock) { l.Modules[0].Replacement = &goReplacement{Path: "fork/a"} }, "duplicate collision": func(l *goProvenanceLock) { l.Modules = append(l.Modules, l.Modules[0]) }}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			l := goLockFixture(manifest, gosum, []goLockedModule{base})
			mutate(&l)
			if _, _, err := GenerateGo(marshalLock(t, l), manifest, gosum, testCreated); err == nil {
				t.Fatal("expected failure")
			}
		})
	}
	t.Run("extra field", func(t *testing.T) {
		raw := marshalLock(t, goLockFixture(manifest, gosum, []goLockedModule{base}))
		raw = bytes.Replace(raw, []byte(`"schemaVersion":1`), []byte(`"schemaVersion":1,"unexpected":true`), 1)
		if _, _, err := GenerateGo(raw, manifest, gosum, testCreated); err == nil {
			t.Fatal("expected extra-field failure")
		}
	})
	t.Run("missing selected module", func(t *testing.T) {
		l := goLockFixture(manifest, gosum, []goLockedModule{base, goModule("example.com/b", "v1.0.0", "b.zip", hashB, "B-LICENSE", hashC, true)})
		l.Modules = l.Modules[:1]
		if _, _, err := GenerateGo(marshalLock(t, l), manifest, gosum, testCreated); err == nil || !strings.Contains(err.Error(), "module count mismatch") {
			t.Fatalf("expected missing-module failure, got %v", err)
		}
	})
	t.Run("extra selected module", func(t *testing.T) {
		l := goLockFixture(manifest, gosum, []goLockedModule{base})
		l.Modules = append(l.Modules, goModule("example.com/b", "v1.0.0", "b.zip", hashB, "B-LICENSE", hashC, true))
		if _, _, err := GenerateGo(marshalLock(t, l), manifest, gosum, testCreated); err == nil || !strings.Contains(err.Error(), "module count mismatch") {
			t.Fatalf("expected extra-module failure, got %v", err)
		}
	})
	t.Run("stale manifest", func(t *testing.T) {
		l := goLockFixture(manifest, gosum, []goLockedModule{base})
		if _, _, err := GenerateGo(marshalLock(t, l), []byte("changed"), gosum, testCreated); err == nil || !strings.Contains(err.Error(), "stale manifest") {
			t.Fatalf("expected stale binding, got %v", err)
		}
	})
}

func TestGoTrustedFilesTamperAndEscape(t *testing.T) {
	dir := t.TempDir()
	sources := filepath.Join(dir, "sources")
	evidence := filepath.Join(dir, "evidence")
	if err := os.MkdirAll(sources, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(evidence, 0o700); err != nil {
		t.Fatal(err)
	}
	manifest := []byte("module example.com/root\n")
	gosum := []byte("sums\n")
	write := func(path string, data []byte) {
		if err := os.WriteFile(path, data, 0o600); err != nil {
			t.Fatal(err)
		}
	}
	write(filepath.Join(dir, "go.mod"), manifest)
	write(filepath.Join(dir, "go.sum"), gosum)
	rootZip := []byte("root source")
	depZip := []byte("dep source")
	rootLic := []byte("root license")
	depLic := []byte("dep license")
	write(filepath.Join(sources, "root.zip"), rootZip)
	write(filepath.Join(sources, "dep.zip"), depZip)
	write(filepath.Join(evidence, "root-LICENSE"), rootLic)
	write(filepath.Join(evidence, "dep-LICENSE"), depLic)
	dep := goModule("example.com/dep", "v1.0.0", "dep.zip", sumBytes(depZip), "dep-LICENSE", sumBytes(depLic), false)
	lock := goLockFixture(manifest, gosum, []goLockedModule{dep})
	lock.Root.SourceArchive.SHA256 = sumBytes(rootZip)
	lock.Root.Evidence[0].SHA256 = sumBytes(rootLic)
	lock = sealGoLock(lock)
	lockPath := filepath.Join(dir, "lock.json")
	write(lockPath, marshalLock(t, lock))
	_, spdx, err := GenerateGoFiles(lockPath, filepath.Join(dir, "go.mod"), filepath.Join(dir, "go.sum"), sources, evidence, testCreated)
	if err != nil {
		t.Fatal(err)
	}
	var doc spdxDocument
	if err := json.Unmarshal(spdx, &doc); err != nil {
		t.Fatal(err)
	}
	found := false
	for _, p := range doc.Packages {
		if p.Name == "example.com/dep" {
			found = true
			if len(p.Checksums) != 1 || p.Checksums[0].Algorithm != "SHA256" || p.Checksums[0].ChecksumValue != sumBytes(depZip) {
				t.Fatalf("bad Go source checksum: %#v", p)
			}
		}
	}
	if !found {
		t.Fatal("dependency missing from SPDX")
	}
	write(filepath.Join(sources, "dep.zip"), []byte("tampered"))
	if _, _, err := GenerateGoFiles(lockPath, filepath.Join(dir, "go.mod"), filepath.Join(dir, "go.sum"), sources, evidence, testCreated); err == nil || !strings.Contains(err.Error(), "hash mismatch") {
		t.Fatalf("expected archive tamper failure, got %v", err)
	}
	write(filepath.Join(sources, "dep.zip"), depZip)
	write(filepath.Join(evidence, "dep-LICENSE"), []byte("tampered license"))
	if _, _, err := GenerateGoFiles(lockPath, filepath.Join(dir, "go.mod"), filepath.Join(dir, "go.sum"), sources, evidence, testCreated); err == nil || !strings.Contains(err.Error(), "hash mismatch") {
		t.Fatalf("expected evidence tamper failure, got %v", err)
	}
	write(filepath.Join(evidence, "dep-LICENSE"), depLic)
	lock.Modules[0].Evidence[0].Path = "../outside"
	write(lockPath, marshalLock(t, lock))
	if _, _, err := GenerateGoFiles(lockPath, filepath.Join(dir, "go.mod"), filepath.Join(dir, "go.sum"), sources, evidence, testCreated); err == nil || !strings.Contains(err.Error(), "escapes root") {
		t.Fatalf("expected path escape failure, got %v", err)
	}
}
