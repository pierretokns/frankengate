package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

func evidenceBlock(order binary.ByteOrder, kind uint32, body []byte) []byte {
	length := uint32(len(body) + 12)
	block := make([]byte, length)
	order.PutUint32(block[0:4], kind)
	order.PutUint32(block[4:8], length)
	copy(block[8:len(block)-4], body)
	order.PutUint32(block[len(block)-4:], length)
	return block
}

func evidenceOption(order binary.ByteOrder, code uint16, value []byte) []byte {
	padded := (len(value) + 3) &^ 3
	option := make([]byte, 4+padded)
	order.PutUint16(option[0:2], code)
	order.PutUint16(option[2:4], uint16(len(value)))
	copy(option[4:], value)
	return option
}

func evidencePCAPNG(t *testing.T, expected contract.RecorderExpectations) []byte {
	t.Helper()
	order := binary.LittleEndian
	section := make([]byte, 16)
	order.PutUint32(section[0:4], 0x1a2b3c4d)
	order.PutUint16(section[4:6], 1)
	order.PutUint64(section[8:16], ^uint64(0))
	blocks := [][]byte{evidenceBlock(order, 0x0a0d0d0a, section)}
	for _, bridge := range expected.Bridges {
		body := make([]byte, 8)
		order.PutUint16(body[0:2], 1)
		order.PutUint32(body[4:8], 65535)
		body = append(body, evidenceOption(order, 2, []byte(bridge.Name))...)
		body = append(body, evidenceOption(order, 3, []byte("linux-ifindex="+strings.TrimSpace(jsonNumber(uint64(bridge.IfIndex)))))...)
		body = append(body, evidenceOption(order, 9, []byte{9})...)
		body = append(body, 0, 0, 0, 0)
		blocks = append(blocks, evidenceBlock(order, 1, body))
	}
	for interfaceID, bridge := range expected.Bridges {
		for index, marker := range []string{contract.RecorderCalibrationStart, contract.RecorderCalibrationEnd} {
			frame, err := contract.RecorderCalibrationFrame(expected.InvocationNonce, bridge.Role, marker)
			if err != nil {
				t.Fatal(err)
			}
			timestamp := uint64(90)
			if index == 1 {
				timestamp = 1050
			}
			body := make([]byte, 20)
			order.PutUint32(body[0:4], uint32(interfaceID))
			order.PutUint32(body[4:8], uint32(timestamp>>32))
			order.PutUint32(body[8:12], uint32(timestamp))
			order.PutUint32(body[12:16], uint32(len(frame)))
			order.PutUint32(body[16:20], uint32(len(frame)))
			body = append(body, frame...)
			blocks = append(blocks, evidenceBlock(order, 6, body))
		}
	}
	for interfaceID := uint32(0); interfaceID < 3; interfaceID++ {
		body := make([]byte, 12)
		order.PutUint32(body[0:4], interfaceID)
		order.PutUint32(body[8:12], 1100)
		for _, option := range []struct {
			code  uint16
			value uint64
		}{{2, 80}, {3, 1100}, {4, 2}, {5, 0}, {7, 0}} {
			value := make([]byte, 8)
			order.PutUint64(value, option.value)
			body = append(body, evidenceOption(order, option.code, value)...)
		}
		body = append(body, 0, 0, 0, 0)
		blocks = append(blocks, evidenceBlock(order, 5, body))
	}
	return bytes.Join(blocks, nil)
}

func jsonNumber(value uint64) string {
	data, _ := json.Marshal(value)
	return string(data)
}

func sealEvidenceRecords(t *testing.T, records []contract.RecorderRecord) []contract.RecorderRecord {
	t.Helper()
	previous := ""
	for index := range records {
		sealed, err := contract.SealRecorderRecord(records[index], previous)
		if err != nil {
			t.Fatal(err)
		}
		records[index], previous = sealed, sealed.RecordSHA256
	}
	return records
}

func evidenceJSONL(t *testing.T, records []contract.RecorderRecord) []byte {
	t.Helper()
	var output bytes.Buffer
	for _, record := range records {
		data, err := json.Marshal(record)
		if err != nil {
			t.Fatal(err)
		}
		output.Write(data)
		output.WriteByte('\n')
	}
	return output.Bytes()
}

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

func completeRecorderEvidence(t *testing.T, aborted bool) (recorderEvidencePaths, contract.RuntimeLock, []byte, []byte) {
	t.Helper()
	directory := t.TempDir()
	policy := []byte("reviewed recorder policy")
	runtimeLockData := []byte("canonical runtime lock bytes")
	lock := recorderCapableLockForEvidence(t, policy)
	names, err := contract.BridgeNames(lock.RunID)
	if err != nil {
		t.Fatal(err)
	}
	expected := contract.RecorderExpectations{
		RunID: lock.RunID, InvocationNonce: strings.Repeat("a", 64),
		RuntimeLockSHA256: contract.SHA256Hex(runtimeLockData), RecorderPolicySHA256: contract.SHA256Hex(policy),
		RecorderImage: lock.Images[4].Reference, Platform: "linux/amd64",
		Bridges: []contract.RecorderBridge{{Role: "client_net", Name: names["client_net"], IfIndex: 11}, {Role: "control_net", Name: names["control_net"], IfIndex: 12}, {Role: "data_net", Name: names["data_net"], IfIndex: 13}},
	}
	ready := contract.RecorderRecord{Schema: contract.RecorderControlSchema, Type: contract.RecorderRecordReady, RunID: lock.RunID, InvocationNonce: expected.InvocationNonce, Ordinal: 1, MonotonicNS: 100, RuntimeLockSHA256: expected.RuntimeLockSHA256, RecorderPolicySHA256: expected.RecorderPolicySHA256, RecorderImage: expected.RecorderImage, Platform: expected.Platform, Bridges: expected.Bridges}
	records := []contract.RecorderRecord{ready}
	if aborted {
		records = append(records, contract.RecorderRecord{Schema: contract.RecorderControlSchema, Type: contract.RecorderRecordPhase, RunID: lock.RunID, InvocationNonce: expected.InvocationNonce, Ordinal: 2, MonotonicNS: 200, Phase: contract.RecorderOutcomeAborted, Failure: &contract.RecorderFailure{Code: "capture_failed", Message: "producer reported failure"}})
	} else {
		phases := []string{contract.RecorderPhaseTopologyCreated, contract.RecorderPhaseServicesStarting, contract.RecorderPhaseServicesReady, contract.RecorderPhaseNormalCellsStarting, contract.RecorderPhaseNormalCellsComplete, contract.RecorderPhaseAdversarialProbeStarting, contract.RecorderPhaseAdversarialProbeComplete, contract.RecorderPhaseTeardownStarting, contract.RecorderPhaseTopologyRemoved}
		for index, phase := range phases {
			records = append(records, contract.RecorderRecord{Schema: contract.RecorderControlSchema, Type: contract.RecorderRecordPhase, RunID: lock.RunID, InvocationNonce: expected.InvocationNonce, Ordinal: uint64(index + 2), MonotonicNS: uint64((index + 2) * 100), Phase: phase})
		}
	}
	records = sealEvidenceRecords(t, records)
	ledger := evidenceJSONL(t, records)
	pcapng := evidencePCAPNG(t, expected)
	outcome := contract.RecorderOutcomeComplete
	if aborted {
		outcome = contract.RecorderOutcomeAborted
	}
	interfaces := make([]contract.RecorderInterfaceCounter, 3)
	for index, bridge := range expected.Bridges {
		interfaces[index] = contract.RecorderInterfaceCounter{Role: bridge.Role, Name: bridge.Name, IfIndex: bridge.IfIndex, Packets: 2}
	}
	final := contract.RecorderRecord{Schema: contract.RecorderControlSchema, Type: contract.RecorderRecordFinalized, RunID: lock.RunID, InvocationNonce: expected.InvocationNonce, Ordinal: uint64(len(records) + 1), MonotonicNS: 1200, Outcome: outcome, Manifest: &contract.RecorderArtifactManifest{Artifacts: []contract.RecorderArtifact{{Kind: "pcapng", File: "capture.pcapng", SHA256: contract.SHA256Hex(pcapng), SizeBytes: uint64(len(pcapng))}, {Kind: "ledger", File: "ledger.jsonl", SHA256: contract.SHA256Hex(ledger), SizeBytes: uint64(len(ledger))}}, Interfaces: interfaces}}
	sealedFinal, err := contract.SealRecorderRecord(final, records[len(records)-1].RecordSHA256)
	if err != nil {
		t.Fatal(err)
	}
	records = append(records, sealedFinal)
	write := func(name string, data []byte) string {
		path := filepath.Join(directory, name)
		if err := os.WriteFile(path, data, 0o600); err != nil {
			t.Fatal(err)
		}
		return path
	}
	expectations, err := json.Marshal(recorderInvocationExpectations{InvocationNonce: expected.InvocationNonce, Bridges: expected.Bridges})
	if err != nil {
		t.Fatal(err)
	}
	return recorderEvidencePaths{Expectations: write("expectations.json", expectations), Transcript: write("transcript.jsonl", evidenceJSONL(t, records)), PCAPNG: write("capture.pcapng", pcapng), Ledger: write("ledger.jsonl", ledger)}, lock, runtimeLockData, policy
}

func TestExternalRecorderEvidenceAcceptsCompleteAndRejectsAbortedOrMutated(t *testing.T) {
	paths, lock, runtimeLockData, policy := completeRecorderEvidence(t, false)
	if err := verifyExternalRecorderEvidence(paths, lock, runtimeLockData, policy, "linux/amd64"); err != nil {
		t.Fatalf("complete producer evidence rejected: %v", err)
	}
	pcapng, err := os.ReadFile(paths.PCAPNG)
	if err != nil {
		t.Fatal(err)
	}
	pcapng[len(pcapng)/2] ^= 1
	if err := os.WriteFile(paths.PCAPNG, pcapng, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := verifyExternalRecorderEvidence(paths, lock, runtimeLockData, policy, "linux/amd64"); err == nil {
		t.Fatal("mutated producer artifact accepted")
	}

	abortedPaths, abortedLock, abortedRuntime, abortedPolicy := completeRecorderEvidence(t, true)
	if err := verifyExternalRecorderEvidence(abortedPaths, abortedLock, abortedRuntime, abortedPolicy, "linux/amd64"); err == nil || !strings.Contains(err.Error(), "did not complete") {
		t.Fatalf("structurally valid aborted recorder evidence accepted: %v", err)
	}
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
