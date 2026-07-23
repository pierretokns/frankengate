package contract

import (
	"bytes"
	"encoding/json"
	"math"
	"strings"
	"testing"
)

func validRecorderTranscript(t *testing.T) []RecorderRecord {
	t.Helper()
	bridges, err := BridgeNames("run-1")
	if err != nil {
		t.Fatal(err)
	}
	records := []RecorderRecord{{
		Schema: RecorderControlSchema, Type: RecorderRecordReady, RunID: "run-1",
		InvocationNonce: strings.Repeat("a", 64), Ordinal: 1, MonotonicNS: 100,
		RuntimeLockSHA256: strings.Repeat("b", 64), RecorderPolicySHA256: strings.Repeat("c", 64),
		RecorderImage: "registry.invalid/recorder@sha256:" + strings.Repeat("d", 64), Platform: "linux/arm64",
		Bridges: []RecorderBridge{
			{Role: "client_net", Name: bridges["client_net"], IfIndex: 11},
			{Role: "control_net", Name: bridges["control_net"], IfIndex: 12},
			{Role: "data_net", Name: bridges["data_net"], IfIndex: 13},
		},
	}}
	for index, phase := range recorderLifecyclePhases {
		records = append(records, RecorderRecord{
			Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1",
			InvocationNonce: strings.Repeat("a", 64), Ordinal: uint64(index + 2), MonotonicNS: uint64(200 + index*100), Phase: phase,
		})
	}
	records = append(records, RecorderRecord{
		Schema: RecorderControlSchema, Type: RecorderRecordFinalized, RunID: "run-1",
		InvocationNonce: strings.Repeat("a", 64), Ordinal: uint64(len(records) + 1), MonotonicNS: 1200,
		Outcome: RecorderOutcomeComplete,
		Manifest: &RecorderArtifactManifest{
			Artifacts: []RecorderArtifact{
				{Kind: "pcapng", File: "capture.pcapng", SHA256: strings.Repeat("e", 64), SizeBytes: 4096},
				{Kind: "ledger", File: "ledger.jsonl", SHA256: strings.Repeat("f", 64), SizeBytes: 1024},
			},
			Interfaces: []RecorderInterfaceCounter{
				{Role: "client_net", Name: bridges["client_net"], IfIndex: 11, Packets: 20},
				{Role: "control_net", Name: bridges["control_net"], IfIndex: 12, Packets: 30},
				{Role: "data_net", Name: bridges["data_net"], IfIndex: 13, Packets: 40},
			},
		},
	})
	return resealRecorderRecords(t, records)
}

func validRecorderExpectations(t *testing.T) RecorderExpectations {
	t.Helper()
	bridges, err := BridgeNames("run-1")
	if err != nil {
		t.Fatal(err)
	}
	return RecorderExpectations{
		RunID: "run-1", InvocationNonce: strings.Repeat("a", 64), RuntimeLockSHA256: strings.Repeat("b", 64),
		RecorderPolicySHA256: strings.Repeat("c", 64), RecorderImage: "registry.invalid/recorder@sha256:" + strings.Repeat("d", 64),
		Platform: "linux/arm64", Bridges: []RecorderBridge{
			{Role: "client_net", Name: bridges["client_net"], IfIndex: 11},
			{Role: "control_net", Name: bridges["control_net"], IfIndex: 12},
			{Role: "data_net", Name: bridges["data_net"], IfIndex: 13},
		},
	}
}

func resealRecorderRecords(t *testing.T, records []RecorderRecord) []RecorderRecord {
	t.Helper()
	previous := ""
	sealed := make([]RecorderRecord, len(records))
	for index, record := range records {
		record.PreviousSHA256, record.RecordSHA256 = "", ""
		var err error
		sealed[index], err = SealRecorderRecord(record, previous)
		if err != nil {
			t.Fatalf("seal record[%d]: %v", index, err)
		}
		previous = sealed[index].RecordSHA256
	}
	return sealed
}

func recorderJSONL(t *testing.T, records []RecorderRecord) []byte {
	t.Helper()
	var output bytes.Buffer
	encoder := json.NewEncoder(&output)
	for _, record := range records {
		if err := encoder.Encode(record); err != nil {
			t.Fatal(err)
		}
	}
	return output.Bytes()
}

func TestDecodeRecorderTranscriptComplete(t *testing.T) {
	records := validRecorderTranscript(t)
	transcript, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t))
	if err != nil {
		t.Fatalf("valid recorder transcript rejected: %v", err)
	}
	last := len(transcript.Records) - 1
	if len(transcript.Records) != len(recorderLifecyclePhases)+2 || transcript.Records[0].Type != RecorderRecordReady || transcript.Records[last].Outcome != RecorderOutcomeComplete {
		t.Fatalf("unexpected decoded transcript: %#v", transcript)
	}
	if err := transcript.Validate(validRecorderExpectations(t)); err != nil {
		t.Fatalf("second validation failed: %v", err)
	}
}

func TestRecorderTranscriptAbortedAfterEveryPrefix(t *testing.T) {
	full := validRecorderTranscript(t)
	for prefix := 0; prefix <= len(recorderLifecyclePhases); prefix++ {
		t.Run(string(rune('0'+prefix)), func(t *testing.T) {
			records := append([]RecorderRecord(nil), full[:1+prefix]...)
			ordinal := uint64(len(records) + 1)
			records = append(records, RecorderRecord{
				Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1", InvocationNonce: strings.Repeat("a", 64),
				Ordinal: ordinal, MonotonicNS: 1100, Phase: RecorderOutcomeAborted,
				Failure: &RecorderFailure{Code: "capture_failed", Message: "synthetic recorder failure"},
			})
			finalized := full[len(full)-1]
			finalized.Ordinal, finalized.MonotonicNS, finalized.Outcome = ordinal+1, 1200, RecorderOutcomeAborted
			records = append(records, finalized)
			records = resealRecorderRecords(t, records)
			if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t)); err != nil {
				t.Fatalf("valid aborted prefix %d rejected: %v", prefix, err)
			}
		})
	}
}

func TestRecorderTranscriptSemanticMutationsFailClosed(t *testing.T) {
	finalIndex := len(recorderLifecyclePhases) + 1
	tests := map[string]func([]RecorderRecord){
		"schema":              func(r []RecorderRecord) { r[0].Schema = "sealed-lab-recorder-control/v2" },
		"record type case":    func(r []RecorderRecord) { r[0].Type = "ready" },
		"short nonce":         func(r []RecorderRecord) { r[0].InvocationNonce = strings.Repeat("a", 62) },
		"upper nonce":         func(r []RecorderRecord) { r[0].InvocationNonce = strings.Repeat("A", 64) },
		"run mismatch":        func(r []RecorderRecord) { r[1].RunID = "run-2" },
		"nonce mismatch":      func(r []RecorderRecord) { r[1].InvocationNonce = strings.Repeat("9", 64) },
		"zero ordinal":        func(r []RecorderRecord) { r[0].Ordinal = 0 },
		"ordinal gap":         func(r []RecorderRecord) { r[2].Ordinal++ },
		"zero monotonic":      func(r []RecorderRecord) { r[0].MonotonicNS = 0 },
		"time regression":     func(r []RecorderRecord) { r[2].MonotonicNS = r[1].MonotonicNS },
		"time overflow":       func(r []RecorderRecord) { r[2].MonotonicNS = math.MaxUint64 },
		"runtime hash":        func(r []RecorderRecord) { r[0].RuntimeLockSHA256 = "bad" },
		"policy hash":         func(r []RecorderRecord) { r[0].RecorderPolicySHA256 = "bad" },
		"floating image":      func(r []RecorderRecord) { r[0].RecorderImage = "recorder:latest" },
		"wrong platform":      func(r []RecorderRecord) { r[0].Platform = "linux/386" },
		"missing bridge":      func(r []RecorderRecord) { r[0].Bridges = r[0].Bridges[:2] },
		"bridge order":        func(r []RecorderRecord) { r[0].Bridges[0], r[0].Bridges[1] = r[0].Bridges[1], r[0].Bridges[0] },
		"bridge name":         func(r []RecorderRecord) { r[0].Bridges[0].Name = "br-attacker" },
		"zero ifindex":        func(r []RecorderRecord) { r[0].Bridges[0].IfIndex = 0 },
		"duplicate ifindex":   func(r []RecorderRecord) { r[0].Bridges[1].IfIndex = r[0].Bridges[0].IfIndex },
		"ready phase field":   func(r []RecorderRecord) { r[0].Phase = "services-started" },
		"skipped phase":       func(r []RecorderRecord) { r[1].Phase = "cells-complete" },
		"phase failure":       func(r []RecorderRecord) { r[1].Failure = &RecorderFailure{Code: "bad", Message: "bad"} },
		"phase ready binding": func(r []RecorderRecord) { r[1].Platform = "linux/arm64" },
		"final phase field":   func(r []RecorderRecord) { r[finalIndex].Phase = "topology-removed" },
		"wrong outcome":       func(r []RecorderRecord) { r[finalIndex].Outcome = RecorderOutcomeAborted },
		"missing manifest":    func(r []RecorderRecord) { r[finalIndex].Manifest = nil },
		"artifact order": func(r []RecorderRecord) {
			r[finalIndex].Manifest.Artifacts[0], r[finalIndex].Manifest.Artifacts[1] = r[finalIndex].Manifest.Artifacts[1], r[finalIndex].Manifest.Artifacts[0]
		},
		"artifact path": func(r []RecorderRecord) { r[finalIndex].Manifest.Artifacts[0].File = "../capture.pcapng" },
		"duplicate artifact": func(r []RecorderRecord) {
			r[finalIndex].Manifest.Artifacts[1].File = r[finalIndex].Manifest.Artifacts[0].File
		},
		"empty artifact":    func(r []RecorderRecord) { r[finalIndex].Manifest.Artifacts[0].SizeBytes = 0 },
		"oversize artifact": func(r []RecorderRecord) { r[finalIndex].Manifest.Artifacts[0].SizeBytes = maxRecorderPCAPNGBytes + 1 },
		"oversize ledger":   func(r []RecorderRecord) { r[finalIndex].Manifest.Artifacts[1].SizeBytes = maxRecorderLedgerBytes + 1 },
		"artifact hash":     func(r []RecorderRecord) { r[finalIndex].Manifest.Artifacts[0].SHA256 = "bad" },
		"counter bridge":    func(r []RecorderRecord) { r[finalIndex].Manifest.Interfaces[0].Name = "br-attacker" },
		"counter ifindex":   func(r []RecorderRecord) { r[finalIndex].Manifest.Interfaces[0].IfIndex = 99 },
		"counter overflow":  func(r []RecorderRecord) { r[finalIndex].Manifest.Interfaces[0].Packets = maxRecorderCounter + 1 },
		"complete zero packets": func(r []RecorderRecord) {
			r[finalIndex].Manifest.Interfaces[0].Packets = 0
		},
		"complete drops": func(r []RecorderRecord) {
			r[finalIndex].Manifest.Interfaces[0].DroppedPackets = 1
		},
		"complete truncation": func(r []RecorderRecord) {
			r[finalIndex].Manifest.Interfaces[0].TruncatedPackets = 1
		},
		"drop overflow": func(r []RecorderRecord) { r[finalIndex].Manifest.Interfaces[0].DroppedPackets = maxRecorderCounter + 1 },
		"truncation overflow": func(r []RecorderRecord) {
			r[finalIndex].Manifest.Interfaces[0].TruncatedPackets = maxRecorderCounter + 1
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			records := validRecorderTranscript(t)
			mutate(records)
			records = resealRecorderRecords(t, records)
			if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t)); err == nil {
				t.Fatal("unsafe recorder semantic mutation accepted")
			}
		})
	}
}

func TestRecorderTrustedExpectationsRejectSubstitution(t *testing.T) {
	records := validRecorderTranscript(t)
	attackerNames, err := BridgeNames("attacker-run")
	if err != nil {
		t.Fatal(err)
	}
	for index := range records {
		records[index].RunID = "attacker-run"
		records[index].InvocationNonce = strings.Repeat("1", 64)
	}
	records[0].RuntimeLockSHA256 = strings.Repeat("2", 64)
	records[0].RecorderPolicySHA256 = strings.Repeat("3", 64)
	records[0].RecorderImage = "registry.invalid/attacker@sha256:" + strings.Repeat("4", 64)
	records[0].Platform = "linux/amd64"
	for index, role := range []string{"client_net", "control_net", "data_net"} {
		records[0].Bridges[index].Name = attackerNames[role]
		records[len(records)-1].Manifest.Interfaces[index].Name = attackerNames[role]
	}
	records = resealRecorderRecords(t, records)
	if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t)); err == nil {
		t.Fatal("self-consistent substituted transcript accepted against trusted expectations")
	}

	expectationMutations := map[string]func(*RecorderExpectations){
		"run":          func(e *RecorderExpectations) { e.RunID = "wrong-run" },
		"nonce":        func(e *RecorderExpectations) { e.InvocationNonce = strings.Repeat("9", 64) },
		"runtime lock": func(e *RecorderExpectations) { e.RuntimeLockSHA256 = strings.Repeat("9", 64) },
		"policy":       func(e *RecorderExpectations) { e.RecorderPolicySHA256 = strings.Repeat("9", 64) },
		"image": func(e *RecorderExpectations) {
			e.RecorderImage = "registry.invalid/wrong@sha256:" + strings.Repeat("9", 64)
		},
		"platform": func(e *RecorderExpectations) { e.Platform = "linux/amd64" },
		"ifindex":  func(e *RecorderExpectations) { e.Bridges[0].IfIndex++ },
	}
	valid := validRecorderTranscript(t)
	for name, mutate := range expectationMutations {
		t.Run(name, func(t *testing.T) {
			expected := validRecorderExpectations(t)
			mutate(&expected)
			if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, valid)), expected); err == nil {
				t.Fatal("transcript accepted against mismatched trusted expectation")
			}
		})
	}
}

func TestRecorderHashPreimageGolden(t *testing.T) {
	tests := []struct {
		name          string
		record        RecorderRecord
		wantPreimage  string
		wantSHA256Hex string
	}{
		{
			name: "normal phase",
			record: RecorderRecord{
				Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1",
				InvocationNonce: strings.Repeat("a", 64), Ordinal: 2, MonotonicNS: 200,
				PreviousSHA256: strings.Repeat("0", 64), Phase: RecorderPhaseTopologyCreated,
			},
			wantPreimage:  `{"schema":"sealed-lab-recorder-control/v1","type":"phase","run_id":"run-1","invocation_nonce":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","ordinal":2,"monotonic_ns":200,"previous_sha256":"0000000000000000000000000000000000000000000000000000000000000000","phase":"topology-created"}`,
			wantSHA256Hex: "02eb52b5a953fa65abb92bc68c54be57dbf2098988ce3278443462fd011860cb",
		},
		{
			name: "aborted phase HTML unescaped",
			record: RecorderRecord{
				Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1",
				InvocationNonce: strings.Repeat("a", 64), Ordinal: 3, MonotonicNS: 300,
				PreviousSHA256: strings.Repeat("1", 64), Phase: RecorderOutcomeAborted,
				Failure: &RecorderFailure{Code: "capture_failed", Message: `capture <failed> & "quoted"`},
			},
			wantPreimage:  `{"schema":"sealed-lab-recorder-control/v1","type":"phase","run_id":"run-1","invocation_nonce":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","ordinal":3,"monotonic_ns":300,"previous_sha256":"1111111111111111111111111111111111111111111111111111111111111111","phase":"aborted","failure":{"code":"capture_failed","message":"capture <failed> & \"quoted\""}}`,
			wantSHA256Hex: "d239b66defbec20f5935ec390035d1d9b4b217acdb132e4a34ed54c38c18e449",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			preimage, err := recorderRecordPreimage(test.record)
			if err != nil {
				t.Fatal(err)
			}
			if string(preimage) != test.wantPreimage {
				t.Fatalf("portable preimage changed\n got: %s\nwant: %s", preimage, test.wantPreimage)
			}
			digest, err := recorderRecordDigest(test.record)
			if err != nil {
				t.Fatal(err)
			}
			if digest != test.wantSHA256Hex {
				t.Fatalf("portable digest changed: %s", digest)
			}
			if bytes.Contains(preimage, []byte("record_sha256")) || bytes.HasSuffix(preimage, []byte("\n")) {
				t.Fatal("hash preimage contains omitted digest field or newline")
			}
		})
	}
}

func TestRecorderStringsMustBePrintableASCII(t *testing.T) {
	abort := RecorderRecord{
		Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1", InvocationNonce: strings.Repeat("a", 64),
		Ordinal: 2, MonotonicNS: 200, Phase: RecorderOutcomeAborted,
		Failure: &RecorderFailure{Code: "capture_failed", Message: "failed"},
	}
	for name, message := range map[string]string{"unicode": "café", "newline": "line\nbreak", "delete": "bad\x7f"} {
		t.Run(name, func(t *testing.T) {
			record := abort
			record.Failure = &RecorderFailure{Code: "capture_failed", Message: message}
			if _, err := SealRecorderRecord(record, strings.Repeat("0", 64)); err == nil {
				t.Fatal("non-portable failure message accepted by sealer")
			}
		})
	}
}

func TestRecorderHashChainMutationsFailClosed(t *testing.T) {
	tests := map[string]func([]RecorderRecord){
		"tampered record": func(r []RecorderRecord) { r[2].Phase = "attacker" },
		"bad previous":    func(r []RecorderRecord) { r[2].PreviousSHA256 = strings.Repeat("9", 64) },
		"bad record hash": func(r []RecorderRecord) { r[2].RecordSHA256 = strings.Repeat("9", 64) },
		"reordered":       func(r []RecorderRecord) { r[1], r[2] = r[2], r[1] },
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			records := validRecorderTranscript(t)
			mutate(records)
			if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t)); err == nil {
				t.Fatal("broken recorder hash chain accepted")
			}
		})
	}
	if _, err := SealRecorderRecord(validRecorderTranscript(t)[0], ""); err == nil {
		t.Fatal("already sealed record accepted for resealing")
	}
	if _, err := SealRecorderRecord(RecorderRecord{}, "not-a-hash"); err == nil {
		t.Fatal("invalid previous digest accepted")
	}
}

func TestRecorderAbortedSemanticsFailClosed(t *testing.T) {
	full := validRecorderTranscript(t)
	tests := map[string][]RecorderRecord{}

	abort := RecorderRecord{Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1", InvocationNonce: strings.Repeat("a", 64), Ordinal: 2, MonotonicNS: 200, Phase: RecorderOutcomeAborted, Failure: &RecorderFailure{Code: "capture_failed", Message: "failed"}}
	final := full[len(full)-1]
	final.Ordinal, final.MonotonicNS, final.Outcome = 3, 300, RecorderOutcomeAborted
	validAborted := []RecorderRecord{full[0], abort, final}

	missingFailure := append([]RecorderRecord(nil), validAborted...)
	missingFailure[1].Failure = nil
	tests["missing failure"] = missingFailure
	badCode := append([]RecorderRecord(nil), validAborted...)
	badCode[1].Failure = &RecorderFailure{Code: "CaptureFailed", Message: "failed"}
	tests["noncanonical code"] = badCode
	blankMessage := append([]RecorderRecord(nil), validAborted...)
	blankMessage[1].Failure = &RecorderFailure{Code: "capture_failed", Message: ""}
	tests["blank message"] = blankMessage
	completeOutcome := append([]RecorderRecord(nil), validAborted...)
	completeOutcome[2].Outcome = RecorderOutcomeComplete
	tests["complete after abort"] = completeOutcome
	phaseAfterAbort := append([]RecorderRecord(nil), validAborted[:2]...)
	extraPhase := full[1]
	extraPhase.Ordinal, extraPhase.MonotonicNS = 3, 300
	phaseAfterAbort = append(phaseAfterAbort, extraPhase)
	lateFinal := final
	lateFinal.Ordinal, lateFinal.MonotonicNS = 4, 400
	phaseAfterAbort = append(phaseAfterAbort, lateFinal)
	tests["phase after abort"] = phaseAfterAbort
	shortComplete := []RecorderRecord{full[0], full[1], full[len(full)-1]}
	shortComplete[2].Ordinal, shortComplete[2].MonotonicNS = 3, 300
	tests["premature complete"] = shortComplete

	for name, records := range tests {
		t.Run(name, func(t *testing.T) {
			records = resealRecorderRecords(t, records)
			if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t)); err == nil {
				t.Fatal("invalid aborted lifecycle accepted")
			}
		})
	}
}

func TestRecorderJSONStrictnessAndBounds(t *testing.T) {
	valid := recorderJSONL(t, validRecorderTranscript(t))
	firstNewline := bytes.IndexByte(valid, '\n')
	first := string(valid[:firstNewline])
	tests := map[string][]byte{
		"unknown key":          []byte(strings.Replace(first, `"schema":`, `"unknown":1,"schema":`, 1) + string(valid[firstNewline:])),
		"duplicate key":        []byte(strings.Replace(first, `"schema":`, `"schema":"`+RecorderControlSchema+`","schema":`, 1) + string(valid[firstNewline:])),
		"case alias key":       []byte(strings.Replace(first, `"schema":`, `"Schema":"`+RecorderControlSchema+`","schema":`, 1) + string(valid[firstNewline:])),
		"hyphen alias key":     []byte(strings.Replace(first, `"run_id":`, `"run-id":"run-1","run_id":`, 1) + string(valid[firstNewline:])),
		"missing required key": []byte(strings.Replace(first, `"ordinal":1,`, "", 1) + string(valid[firstNewline:])),
		"cross-type empty key": []byte(strings.Replace(first, `"bridges":`, `"phase":"","bridges":`, 1) + string(valid[firstNewline:])),
		"nested unknown":       []byte(strings.Replace(string(valid), `"packets":20`, `"unknown":0,"packets":20`, 1)),
		"nested duplicate":     []byte(strings.Replace(string(valid), `"packets":20`, `"packets":0,"packets":20`, 1)),
		"nested case alias":    []byte(strings.Replace(string(valid), `"packets":20`, `"Packets":20,"packets":20`, 1)),
		"missing counter key":  []byte(strings.Replace(string(valid), `"dropped_packets":0,`, "", 1)),
		"blank line":           append([]byte("\n"), valid...),
		"trailing JSON":        []byte(first + ` {}` + string(valid[firstNewline:])),
		"empty":                nil,
		"single record":        append([]byte(first), '\n'),
		"oversized record":     []byte(`{"schema":"` + strings.Repeat("x", maxRecorderRecordBytes) + `"}`),
	}
	for name, input := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := DecodeRecorderTranscript(bytes.NewReader(input), validRecorderExpectations(t)); err == nil {
				t.Fatal("malformed or unbounded recorder transcript accepted")
			}
		})
	}

	many := make([]RecorderRecord, maxRecorderRecords+1)
	for index := range many {
		many[index] = validRecorderTranscript(t)[0]
	}
	if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, many)), validRecorderExpectations(t)); err == nil {
		t.Fatal("excessive recorder record count accepted")
	}

	largeLine := strings.Replace(first, strings.Repeat("a", 64), strings.Repeat("a", 50_000), 1) + "\n"
	if _, err := DecodeRecorderTranscript(strings.NewReader(strings.Repeat(largeLine, 22)), validRecorderExpectations(t)); err == nil {
		t.Fatal("oversized aggregate recorder transcript accepted")
	}
}
