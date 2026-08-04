package main

import (
	"archive/tar"
	"bytes"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

func recorderTar(t *testing.T, entries ...struct {
	name string
	mode int64
	body []byte
}) []byte {
	t.Helper()
	var output bytes.Buffer
	writer := tar.NewWriter(&output)
	for _, entry := range entries {
		if err := writer.WriteHeader(&tar.Header{Name: entry.name, Mode: entry.mode, Size: int64(len(entry.body)), Typeflag: tar.TypeReg}); err != nil {
			t.Fatal(err)
		}
		if _, err := writer.Write(entry.body); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return output.Bytes()
}

func recorderTarWithDirectory(t *testing.T, uid, gid int, mode int64, binary []byte) []byte {
	t.Helper()
	var output bytes.Buffer
	writer := tar.NewWriter(&output)
	if err := writer.WriteHeader(&tar.Header{Name: "tmp/", Mode: mode, Typeflag: tar.TypeDir, Uid: uid, Gid: gid}); err != nil {
		t.Fatal(err)
	}
	if err := writer.WriteHeader(&tar.Header{Name: recorderBinaryPath, Mode: 0o555, Size: int64(len(binary)), Typeflag: tar.TypeReg}); err != nil {
		t.Fatal(err)
	}
	if _, err := writer.Write(binary); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return output.Bytes()
}

func TestRecorderBinaryExtractionIsExactBoundedAndExecutable(t *testing.T) {
	body := []byte("ELF recorder")
	valid := recorderTar(t, struct {
		name string
		mode int64
		body []byte
	}{"network-recorder", 0o555, body})
	got, err := extractRecorderBinary(valid)
	if err != nil || !bytes.Equal(got, body) {
		t.Fatalf("valid recorder extraction: got=%q err=%v", got, err)
	}
	if got, err := extractRecorderBinary(recorderTarWithDirectory(t, 0, 0, 0o755, body)); err != nil || !bytes.Equal(got, body) {
		t.Fatalf("canonical root-owned Docker directory rejected: got=%q err=%v", got, err)
	}
	for name, candidate := range map[string][]byte{
		"missing": recorderTar(t, struct {
			name string
			mode int64
			body []byte
		}{"other", 0o555, body}),
		"not executable": recorderTar(t, struct {
			name string
			mode int64
			body []byte
		}{"network-recorder", 0o444, body}),
		"duplicate": recorderTar(t,
			struct {
				name string
				mode int64
				body []byte
			}{"network-recorder", 0o555, body},
			struct {
				name string
				mode int64
				body []byte
			}{"./network-recorder", 0o555, body}),
		"setuid target": recorderTar(t, struct {
			name string
			mode int64
			body []byte
		}{"network-recorder", 0o4555, body}),
		"world writable target": recorderTar(t, struct {
			name string
			mode int64
			body []byte
		}{"network-recorder", 0o557, body}),
		"extra executable": recorderTar(t,
			struct {
				name string
				mode int64
				body []byte
			}{"network-recorder", 0o555, body},
			struct {
				name string
				mode int64
				body []byte
			}{"backdoor", 0o555, body}),
		"non-root directory": recorderTarWithDirectory(t, 1000, 1000, 0o755, body),
		"writable directory": recorderTarWithDirectory(t, 0, 0, 0o777, body),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := extractRecorderBinary(candidate); err == nil {
				t.Fatal("unsafe recorder artifact archive accepted")
			}
		})
	}
}

type recorderExecutor struct {
	archive          []byte
	calls            []string
	fail             string
	containerID      string
	createdOnFailure bool
	ownershipToken   string
	imageReference   string
}

func (executor *recorderExecutor) Run(_ []string, stdout, _ io.Writer, _ string, args ...string) error {
	executor.calls = append(executor.calls, strings.Join(args, " "))
	if executor.containerID == "" {
		executor.containerID = strings.Repeat("1", 64)
	}
	if args[0] == "create" {
		executor.imageReference = args[len(args)-1]
		for index, argument := range args {
			if argument == "--label" && index+1 < len(args) && strings.HasPrefix(args[index+1], "frankengate.sealed-lab.extract=") {
				executor.ownershipToken = strings.TrimPrefix(args[index+1], "frankengate.sealed-lab.extract=")
			}
		}
	}
	if executor.fail != "" && strings.Contains(strings.Join(args, " "), executor.fail) {
		return errors.New("injected executor failure")
	}
	switch args[0] {
	case "create":
		_, _ = io.WriteString(stdout, executor.containerID+"\n")
	case "inspect":
		if !executor.createdOnFailure {
			return errors.New("no owned container")
		}
		_, _ = io.WriteString(stdout, executor.containerID+"\trun-1\t"+executor.ownershipToken+"\t"+executor.imageReference+"\n")
	case "cp":
		_, _ = stdout.Write(executor.archive)
	}
	return nil
}

func TestRecorderExtractionCleanupRunsOnVerificationFailure(t *testing.T) {
	policy := []byte("policy")
	path := filepath.Join(t.TempDir(), "policy.bin")
	if err := os.WriteFile(path, policy, 0o600); err != nil {
		t.Fatal(err)
	}
	lock := recorderRuntimeLock(policy, []byte("binary"))
	executor := &recorderExecutor{fail: "cp"}
	if err := verifyPinnedRecorderArtifacts(executor, nil, io.Discard, "/docker", path, "linux/arm64", lock); err == nil {
		t.Fatal("copy failure did not fail recorder verification")
	}
	if calls := strings.Join(executor.calls, "\n"); !strings.Contains(calls, "cp "+strings.Repeat("1", 64)+":/network-recorder -") || !strings.Contains(calls, "rm --force "+strings.Repeat("1", 64)) {
		t.Fatalf("failed extraction did not clean up: %s", calls)
	}
}

func TestAmbiguousRecorderCreateFailureOnlyRemovesInvocationOwnedContainer(t *testing.T) {
	policy := []byte("policy")
	path := filepath.Join(t.TempDir(), "policy.bin")
	if err := os.WriteFile(path, policy, 0o600); err != nil {
		t.Fatal(err)
	}
	executor := &recorderExecutor{fail: "create", createdOnFailure: true}
	if err := verifyPinnedRecorderArtifacts(executor, nil, io.Discard, "/docker", path, "linux/arm64", recorderRuntimeLock(policy, []byte("binary"))); err == nil {
		t.Fatal("ambiguous create failure did not fail verification")
	}
	if calls := strings.Join(executor.calls, "\n"); !strings.Contains(calls, "create --name fg-recorder-extract-run-1") || !strings.Contains(calls, "inspect --type container") || !strings.Contains(calls, "rm --force "+strings.Repeat("1", 64)) {
		t.Fatalf("ambiguous create did not attempt cleanup: %s", calls)
	}
}

func TestRecorderCreateNameCollisionNeverDeletesUnownedContainer(t *testing.T) {
	policy := []byte("policy")
	path := filepath.Join(t.TempDir(), "policy.bin")
	if err := os.WriteFile(path, policy, 0o600); err != nil {
		t.Fatal(err)
	}
	executor := &recorderExecutor{fail: "create"}
	if err := verifyPinnedRecorderArtifacts(executor, nil, io.Discard, "/docker", path, "linux/arm64", recorderRuntimeLock(policy, []byte("binary"))); err == nil {
		t.Fatal("name collision did not fail verification")
	}
	if calls := strings.Join(executor.calls, "\n"); strings.Contains(calls, "rm --force") {
		t.Fatalf("unowned recorder container was removed: %s", calls)
	}
}

func TestAmbiguousRecorderCreateRejectsMismatchedOwnership(t *testing.T) {
	policy := []byte("policy")
	path := filepath.Join(t.TempDir(), "policy.bin")
	if err := os.WriteFile(path, policy, 0o600); err != nil {
		t.Fatal(err)
	}
	executor := &recorderExecutor{fail: "create", createdOnFailure: true, ownershipToken: "attacker"}
	// The create parser overwrites ownershipToken, so corrupt the inspected image
	// identity instead and prove exact-image ownership is required for cleanup.
	executor.imageReference = "registry.invalid/unowned@sha256:" + strings.Repeat("9", 64)
	lock := recorderRuntimeLock(policy, []byte("binary"))
	// Preserve the mismatched inspect identity after create parses its arguments.
	executor.fail = "create"
	if err := verifyPinnedRecorderArtifacts(&mismatchedInspectExecutor{recorderExecutor: executor}, nil, io.Discard, "/docker", path, "linux/arm64", lock); err == nil {
		t.Fatal("mismatched recorder ownership did not fail verification")
	}
	if calls := strings.Join(executor.calls, "\n"); strings.Contains(calls, "rm --force") {
		t.Fatalf("mismatched recorder container was removed: %s", calls)
	}
}

type mismatchedInspectExecutor struct{ recorderExecutor *recorderExecutor }

func (executor *mismatchedInspectExecutor) Run(environment []string, stdout, stderr io.Writer, binary string, args ...string) error {
	if args[0] == "inspect" {
		executor.recorderExecutor.calls = append(executor.recorderExecutor.calls, strings.Join(args, " "))
		_, _ = io.WriteString(stdout, executor.recorderExecutor.containerID+"\trun-1\t"+executor.recorderExecutor.ownershipToken+"\tregistry.invalid/unowned@sha256:"+strings.Repeat("9", 64)+"\n")
		return nil
	}
	return executor.recorderExecutor.Run(environment, stdout, stderr, binary, args...)
}

func TestPinnedRecorderVerificationUsesImageBytesAndCleansExtractionContainer(t *testing.T) {
	policy, binary := []byte("policy"), []byte("ELF recorder")
	directory := t.TempDir()
	policyPath := filepath.Join(directory, "policy.bin")
	if err := os.WriteFile(policyPath, policy, 0o600); err != nil {
		t.Fatal(err)
	}
	lock := recorderRuntimeLock(policy, binary)
	executor := &recorderExecutor{archive: recorderTar(t, struct {
		name string
		mode int64
		body []byte
	}{"network-recorder", 0o555, binary})}
	if err := verifyPinnedRecorderArtifacts(executor, nil, io.Discard, "/docker", policyPath, "linux/arm64", lock); err != nil {
		t.Fatal(err)
	}
	calls := strings.Join(executor.calls, "\n")
	for _, required := range []string{"create --name fg-recorder-extract-run-1 --label frankengate.sealed-lab.run=run-1 --label frankengate.sealed-lab.extract=", "cp " + strings.Repeat("1", 64) + ":/network-recorder -", "rm --force " + strings.Repeat("1", 64)} {
		if !strings.Contains(calls, required) {
			t.Fatalf("recorder verification omitted %q: %s", required, calls)
		}
	}
}

func recorderRuntimeLock(policy, binary []byte) contract.RuntimeLock {
	return contract.RuntimeLock{
		Schema: contract.RuntimeLockSchemaV2, RunID: "run-1", SourceLockSHA256: strings.Repeat("a", 64),
		RecorderPolicySHA256: contract.SHA256Hex(policy),
		Images: []contract.RuntimeImage{
			{ID: "bifrost", Reference: digestRef("a"), Platforms: platforms(), Source: "git:a"},
			{ID: "claude-runner", Reference: digestRef("b"), Platforms: platforms(), Source: "lock:claude", ClientVersion: "2.1.214"},
			{ID: "codex-runner", Reference: digestRef("c"), Platforms: platforms(), Source: "lock:codex", ClientVersion: "0.144.5"},
			{ID: "egress-sentinel", Reference: digestRef("d"), Platforms: platforms(), Source: "git:d"},
			{ID: "network-recorder", Reference: digestRef("e"), Platforms: platforms(), Source: "git:" + strings.Repeat("f", 40), BinaryDigests: []contract.PlatformDigest{{Platform: "linux/amd64", SHA256: contract.SHA256Hex(binary)}, {Platform: "linux/arm64", SHA256: contract.SHA256Hex(binary)}}},
		},
	}
}

func digestRef(letter string) string {
	return "registry.invalid/image@sha256:" + strings.Repeat(letter, 64)
}
func platforms() []string { return []string{"linux/amd64", "linux/arm64"} }
