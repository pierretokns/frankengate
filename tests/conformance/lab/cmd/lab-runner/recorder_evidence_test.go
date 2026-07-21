package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

func recorderCapableLockForEvidence(t *testing.T, policy []byte) contract.RuntimeLock {
	t.Helper()
	platforms := []string{"linux/amd64", "linux/arm64"}
	image := func(id, digest string) contract.RuntimeImage {
		return contract.RuntimeImage{ID: id, Reference: "registry.invalid/" + id + "@sha256:" + digest, Platforms: platforms, Source: "locked"}
	}
	images := []contract.RuntimeImage{
		image("bifrost", strings.Repeat("a", 64)), image("claude-runner", strings.Repeat("b", 64)),
		image("codex-runner", strings.Repeat("c", 64)), image("egress-sentinel", strings.Repeat("d", 64)),
		image("network-recorder", strings.Repeat("1", 64)),
	}
	images[1].ClientVersion = "1.2.3"
	images[2].ClientVersion = "1.2.3"
	images[4].Source = "git:" + strings.Repeat("3", 40)
	images[4].BinaryDigests = []contract.PlatformDigest{{Platform: platforms[0], SHA256: strings.Repeat("4", 64)}, {Platform: platforms[1], SHA256: strings.Repeat("5", 64)}}
	return contract.RuntimeLock{Schema: contract.RuntimeLockSchemaV2, RunID: "run-1", SourceLockSHA256: strings.Repeat("e", 64), RecorderPolicySHA256: contract.SHA256Hex(policy), Images: images}
}

func TestExternalRecorderEvidenceProductionPathFailsClosed(t *testing.T) {
	directory := t.TempDir()
	policy := []byte("reviewed recorder policy")
	lock := recorderCapableLockForEvidence(t, policy)
	if !lock.IsRecorderCapable() {
		t.Fatal("test lock is not recorder capable")
	}
	names, err := contract.BridgeNames(lock.RunID)
	if err != nil {
		t.Fatal(err)
	}
	write := func(name string, data []byte) string {
		path := filepath.Join(directory, name)
		if err := os.WriteFile(path, data, 0o600); err != nil {
			t.Fatal(err)
		}
		return path
	}
	expectations := `{"invocation_nonce":"` + strings.Repeat("a", 64) + `","bridges":[` +
		`{"role":"client_net","name":"` + names["client_net"] + `","ifindex":11},` +
		`{"role":"control_net","name":"` + names["control_net"] + `","ifindex":12},` +
		`{"role":"data_net","name":"` + names["data_net"] + `","ifindex":13}]}`
	paths := recorderEvidencePaths{
		Expectations: write("expectations.json", []byte(expectations)),
		Transcript:   write("transcript.jsonl", []byte("{}\n")),
		PCAPNG:       write("capture.pcapng", []byte("not-pcapng")),
		Ledger:       write("ledger.jsonl", []byte("{}\n")),
	}
	if err := paths.validate(true); err != nil {
		t.Fatalf("complete absolute evidence paths rejected: %v", err)
	}
	if err := verifyExternalRecorderEvidence(paths, lock, []byte("runtime-lock"), policy, "linux/amd64"); err == nil || !strings.Contains(err.Error(), "verify recorder transcript") {
		t.Fatalf("invalid transcript did not fail through production verifier: %v", err)
	}

	paths.Transcript = write("empty-transcript", nil)
	if err := verifyExternalRecorderEvidence(paths, lock, []byte("runtime-lock"), policy, "linux/amd64"); err == nil || !strings.Contains(err.Error(), "bounded") {
		t.Fatalf("empty transcript was not bounded before decode: %v", err)
	}
}

func TestRecorderEvidencePathSetIsAllOrNothingAndRejectsSymlinks(t *testing.T) {
	if err := (recorderEvidencePaths{Transcript: "/tmp/transcript"}).validate(true); err == nil {
		t.Fatal("partial v2 evidence path set accepted")
	}
	if err := (recorderEvidencePaths{Expectations: "relative", Transcript: "/t", PCAPNG: "/p", Ledger: "/l"}).validate(true); err == nil {
		t.Fatal("relative evidence path accepted")
	}
	directory := t.TempDir()
	target := filepath.Join(directory, "target")
	link := filepath.Join(directory, "link")
	if err := os.WriteFile(target, []byte("evidence"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, link); err != nil {
		t.Fatal(err)
	}
	if _, err := readBoundedRegularFile(link, 100); err == nil {
		t.Fatal("symlinked recorder evidence accepted")
	}
}
