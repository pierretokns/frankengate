package contract

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"path/filepath"
	"regexp"
	"strings"
)

const (
	RecorderControlSchema = "sealed-lab-recorder-control/v1"

	RecorderRecordReady     = "READY"
	RecorderRecordPhase     = "phase"
	RecorderRecordFinalized = "FINALIZED"

	RecorderOutcomeComplete = "complete"
	RecorderOutcomeAborted  = "aborted"

	RecorderPhaseTopologyCreated          = "topology-created"
	RecorderPhaseServicesStarting         = "services-starting"
	RecorderPhaseServicesReady            = "services-ready"
	RecorderPhaseNormalCellsStarting      = "normal-cells-starting"
	RecorderPhaseNormalCellsComplete      = "normal-cells-complete"
	RecorderPhaseAdversarialProbeStarting = "adversarial-probe-starting"
	RecorderPhaseAdversarialProbeComplete = "adversarial-probe-complete"
	RecorderPhaseTeardownStarting         = "teardown-starting"
	RecorderPhaseTopologyRemoved          = "topology-removed"

	maxRecorderTranscriptBytes = 1 << 20
	maxRecorderRecordBytes     = 64 << 10
	maxRecorderRecords         = 32
	maxRecorderPCAPNGBytes     = 256 << 20
	maxRecorderLedgerBytes     = 1 << 20
	maxRecorderCounter         = 1 << 53
)

var (
	invocationNonce = regexp.MustCompile(`^[0-9a-f]{64}$`)
	recorderCode    = regexp.MustCompile(`^[a-z][a-z0-9_]{0,63}$`)
	recorderFile    = regexp.MustCompile(`^[a-z0-9][a-z0-9._-]{0,127}$`)
)

var recorderLifecyclePhases = [...]string{
	RecorderPhaseTopologyCreated,
	RecorderPhaseServicesStarting,
	RecorderPhaseServicesReady,
	RecorderPhaseNormalCellsStarting,
	RecorderPhaseNormalCellsComplete,
	RecorderPhaseAdversarialProbeStarting,
	RecorderPhaseAdversarialProbeComplete,
	RecorderPhaseTeardownStarting,
	RecorderPhaseTopologyRemoved,
}

type RecorderRecord struct {
	Schema          string `json:"schema"`
	Type            string `json:"type"`
	RunID           string `json:"run_id"`
	InvocationNonce string `json:"invocation_nonce"`
	Ordinal         uint64 `json:"ordinal"`
	MonotonicNS     uint64 `json:"monotonic_ns"`
	PreviousSHA256  string `json:"previous_sha256"`
	RecordSHA256    string `json:"record_sha256"`

	RuntimeLockSHA256    string           `json:"runtime_lock_sha256,omitempty"`
	RecorderPolicySHA256 string           `json:"recorder_policy_sha256,omitempty"`
	RecorderImage        string           `json:"recorder_image,omitempty"`
	Platform             string           `json:"platform,omitempty"`
	Bridges              []RecorderBridge `json:"bridges,omitempty"`

	Phase   string           `json:"phase,omitempty"`
	Failure *RecorderFailure `json:"failure,omitempty"`

	Outcome  string                    `json:"outcome,omitempty"`
	Manifest *RecorderArtifactManifest `json:"manifest,omitempty"`
}

type RecorderBridge struct {
	Role    string `json:"role"`
	Name    string `json:"name"`
	IfIndex uint32 `json:"ifindex"`
}

type RecorderFailure struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type RecorderArtifactManifest struct {
	Artifacts  []RecorderArtifact         `json:"artifacts"`
	Interfaces []RecorderInterfaceCounter `json:"interfaces"`
}

type RecorderArtifact struct {
	Kind      string `json:"kind"`
	File      string `json:"file"`
	SHA256    string `json:"sha256"`
	SizeBytes uint64 `json:"size_bytes"`
}

type RecorderInterfaceCounter struct {
	Role             string `json:"role"`
	Name             string `json:"name"`
	IfIndex          uint32 `json:"ifindex"`
	Packets          uint64 `json:"packets"`
	DroppedPackets   uint64 `json:"dropped_packets"`
	TruncatedPackets uint64 `json:"truncated_packets"`
}

// RecorderTranscript is a fully validated recorder control stream. A valid
// transcript always begins with READY, ends with FINALIZED, and is bound to a
// single invocation and hash chain.
type RecorderTranscript struct {
	Records []RecorderRecord
}

// RecorderExpectations are derived by the trusted runner before it accepts any
// recorder output. A transcript is never authoritative without matching every
// value, including the host-observed bridge indexes.
type RecorderExpectations struct {
	RunID                string
	InvocationNonce      string
	RuntimeLockSHA256    string
	RecorderPolicySHA256 string
	RecorderImage        string
	Platform             string
	Bridges              []RecorderBridge
}

// SealRecorderRecord fills the link and digest fields using the canonical hash
// preimage defined by recorderRecordPreimage. The first record must pass an
// empty previous digest, which is represented on the wire by 64 zeroes.
func SealRecorderRecord(record RecorderRecord, previous string) (RecorderRecord, error) {
	if record.RecordSHA256 != "" || record.PreviousSHA256 != "" {
		return RecorderRecord{}, fmt.Errorf("recorder record is already linked or sealed")
	}
	if previous == "" {
		previous = strings.Repeat("0", 64)
	}
	if !sha256Value.MatchString(previous) {
		return RecorderRecord{}, fmt.Errorf("invalid previous recorder digest")
	}
	record.PreviousSHA256 = previous
	if err := validateRecorderPrintableASCII(record); err != nil {
		return RecorderRecord{}, err
	}
	digest, err := recorderRecordDigest(record)
	if err != nil {
		return RecorderRecord{}, err
	}
	record.RecordSHA256 = digest
	return record, nil
}

func recorderRecordDigest(record RecorderRecord) (string, error) {
	data, err := recorderRecordPreimage(record)
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(data)
	return hex.EncodeToString(digest[:]), nil
}

// recorderRecordPreimage is the portable v1 hash preimage. It is UTF-8 compact
// JSON in the field order declared below, with record_sha256 wholly omitted,
// no trailing newline, and HTML escaping disabled. All strings are restricted
// to printable ASCII before encoding, so implementations need only reproduce
// standard JSON quote/backslash/control escaping for ASCII input.
func recorderRecordPreimage(record RecorderRecord) ([]byte, error) {
	if err := validateRecorderPrintableASCII(record); err != nil {
		return nil, err
	}
	type preimage struct {
		Schema          string `json:"schema"`
		Type            string `json:"type"`
		RunID           string `json:"run_id"`
		InvocationNonce string `json:"invocation_nonce"`
		Ordinal         uint64 `json:"ordinal"`
		MonotonicNS     uint64 `json:"monotonic_ns"`
		PreviousSHA256  string `json:"previous_sha256"`

		RuntimeLockSHA256    string           `json:"runtime_lock_sha256,omitempty"`
		RecorderPolicySHA256 string           `json:"recorder_policy_sha256,omitempty"`
		RecorderImage        string           `json:"recorder_image,omitempty"`
		Platform             string           `json:"platform,omitempty"`
		Bridges              []RecorderBridge `json:"bridges,omitempty"`

		Phase   string           `json:"phase,omitempty"`
		Failure *RecorderFailure `json:"failure,omitempty"`

		Outcome  string                    `json:"outcome,omitempty"`
		Manifest *RecorderArtifactManifest `json:"manifest,omitempty"`
	}
	value := preimage{
		Schema: record.Schema, Type: record.Type, RunID: record.RunID, InvocationNonce: record.InvocationNonce,
		Ordinal: record.Ordinal, MonotonicNS: record.MonotonicNS, PreviousSHA256: record.PreviousSHA256,
		RuntimeLockSHA256: record.RuntimeLockSHA256, RecorderPolicySHA256: record.RecorderPolicySHA256,
		RecorderImage: record.RecorderImage, Platform: record.Platform, Bridges: record.Bridges,
		Phase: record.Phase, Failure: record.Failure, Outcome: record.Outcome, Manifest: record.Manifest,
	}
	return compactRecorderJSON(value)
}

func compactRecorderJSON(value any) ([]byte, error) {
	var output bytes.Buffer
	encoder := json.NewEncoder(&output)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, fmt.Errorf("encode canonical recorder JSON: %w", err)
	}
	data := output.Bytes()
	if len(data) == 0 || data[len(data)-1] != '\n' {
		return nil, fmt.Errorf("canonical recorder JSON encoder omitted delimiter")
	}
	return append([]byte(nil), data[:len(data)-1]...), nil
}

// DecodeRecorderTranscript decodes the deliberately small JSONL control
// stream. It rejects oversized input and records, blank lines, unknown or
// duplicate keys, noncanonical key aliases, and incomplete lifecycle streams.
func DecodeRecorderTranscript(reader io.Reader, expected RecorderExpectations) (*RecorderTranscript, error) {
	limited := io.LimitReader(reader, maxRecorderTranscriptBytes+1)
	scanner := bufio.NewScanner(limited)
	scanner.Buffer(make([]byte, 4096), maxRecorderRecordBytes+1)
	records := make([]RecorderRecord, 0, len(recorderLifecyclePhases)+2)
	totalBytes := 0
	for scanner.Scan() {
		line := append([]byte(nil), scanner.Bytes()...)
		totalBytes += len(line) + 1
		if totalBytes > maxRecorderTranscriptBytes {
			return nil, fmt.Errorf("recorder transcript exceeds bounded input contract")
		}
		if len(line) == 0 {
			return nil, fmt.Errorf("recorder transcript contains a blank record")
		}
		if len(line) > maxRecorderRecordBytes {
			return nil, fmt.Errorf("recorder record exceeds bounded input contract")
		}
		if len(records) == maxRecorderRecords {
			return nil, fmt.Errorf("recorder transcript contains too many records")
		}
		if err := rejectDuplicateJSONKeys(line); err != nil {
			return nil, fmt.Errorf("recorder record JSON: %w", err)
		}
		if err := validateRecorderRecordKeyShape(line); err != nil {
			return nil, fmt.Errorf("recorder record JSON shape: %w", err)
		}
		decoder := json.NewDecoder(bytes.NewReader(line))
		decoder.DisallowUnknownFields()
		var record RecorderRecord
		if err := decoder.Decode(&record); err != nil {
			return nil, fmt.Errorf("decode recorder record: %w", err)
		}
		if err := decoder.Decode(&struct{}{}); err != io.EOF {
			return nil, fmt.Errorf("recorder record contains trailing JSON")
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		if strings.Contains(err.Error(), "token too long") {
			return nil, fmt.Errorf("recorder record exceeds bounded input contract")
		}
		return nil, fmt.Errorf("read recorder transcript: %w", err)
	}
	if len(records) == 0 {
		return nil, fmt.Errorf("recorder transcript is empty")
	}
	transcript := &RecorderTranscript{Records: records}
	if err := transcript.Validate(expected); err != nil {
		return nil, err
	}
	return transcript, nil
}

func validateRecorderRecordKeyShape(line []byte) error {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(line, &object); err != nil {
		return err
	}
	var recordType string
	if err := json.Unmarshal(object["type"], &recordType); err != nil {
		return fmt.Errorf("record type is missing or not a string")
	}
	common := []string{"schema", "type", "run_id", "invocation_nonce", "ordinal", "monotonic_ns", "previous_sha256", "record_sha256"}
	switch recordType {
	case RecorderRecordReady:
		if err := requireExactJSONKeys(object, append(common, "runtime_lock_sha256", "recorder_policy_sha256", "recorder_image", "platform", "bridges")...); err != nil {
			return err
		}
		var bridges []map[string]json.RawMessage
		if err := json.Unmarshal(object["bridges"], &bridges); err != nil {
			return fmt.Errorf("bridges must be an array")
		}
		for index, bridge := range bridges {
			if err := requireExactJSONKeys(bridge, "role", "name", "ifindex"); err != nil {
				return fmt.Errorf("bridge[%d]: %w", index, err)
			}
		}
	case RecorderRecordPhase:
		var phase string
		if err := json.Unmarshal(object["phase"], &phase); err != nil {
			return fmt.Errorf("phase is missing or not a string")
		}
		keys := append(common, "phase")
		if phase == RecorderOutcomeAborted {
			keys = append(keys, "failure")
		}
		if err := requireExactJSONKeys(object, keys...); err != nil {
			return err
		}
		if phase == RecorderOutcomeAborted {
			var failure map[string]json.RawMessage
			if err := json.Unmarshal(object["failure"], &failure); err != nil {
				return fmt.Errorf("failure must be an object")
			}
			if err := requireExactJSONKeys(failure, "code", "message"); err != nil {
				return fmt.Errorf("failure: %w", err)
			}
		}
	case RecorderRecordFinalized:
		if err := requireExactJSONKeys(object, append(common, "outcome", "manifest")...); err != nil {
			return err
		}
		var manifest map[string]json.RawMessage
		if err := json.Unmarshal(object["manifest"], &manifest); err != nil {
			return fmt.Errorf("manifest must be an object")
		}
		if err := requireExactJSONKeys(manifest, "artifacts", "interfaces"); err != nil {
			return fmt.Errorf("manifest: %w", err)
		}
		var artifacts []map[string]json.RawMessage
		if err := json.Unmarshal(manifest["artifacts"], &artifacts); err != nil {
			return fmt.Errorf("manifest artifacts must be an array")
		}
		for index, artifact := range artifacts {
			if err := requireExactJSONKeys(artifact, "kind", "file", "sha256", "size_bytes"); err != nil {
				return fmt.Errorf("artifact[%d]: %w", index, err)
			}
		}
		var interfaces []map[string]json.RawMessage
		if err := json.Unmarshal(manifest["interfaces"], &interfaces); err != nil {
			return fmt.Errorf("manifest interfaces must be an array")
		}
		for index, iface := range interfaces {
			if err := requireExactJSONKeys(iface, "role", "name", "ifindex", "packets", "dropped_packets", "truncated_packets"); err != nil {
				return fmt.Errorf("interface[%d]: %w", index, err)
			}
		}
	default:
		return fmt.Errorf("unsupported record type %q", recordType)
	}
	return nil
}

func requireExactJSONKeys(object map[string]json.RawMessage, keys ...string) error {
	if len(object) != len(keys) {
		return fmt.Errorf("object has %d keys; want exactly %d", len(object), len(keys))
	}
	for _, key := range keys {
		if _, ok := object[key]; !ok {
			return fmt.Errorf("object misses required key %q", key)
		}
	}
	return nil
}

func (transcript RecorderTranscript) Validate(expected RecorderExpectations) error {
	if err := expected.validate(); err != nil {
		return fmt.Errorf("trusted recorder expectations: %w", err)
	}
	if len(transcript.Records) < 2 || len(transcript.Records) > maxRecorderRecords {
		return fmt.Errorf("recorder transcript has invalid record count")
	}
	ready := transcript.Records[0]
	if err := validateRecorderCommon(ready); err != nil {
		return fmt.Errorf("READY: %w", err)
	}
	if err := validateRecorderReady(ready); err != nil {
		return err
	}
	if ready.RunID != expected.RunID || ready.InvocationNonce != expected.InvocationNonce || ready.RuntimeLockSHA256 != expected.RuntimeLockSHA256 || ready.RecorderPolicySHA256 != expected.RecorderPolicySHA256 || ready.RecorderImage != expected.RecorderImage || ready.Platform != expected.Platform || !sameRecorderBridges(ready.Bridges, expected.Bridges) {
		return fmt.Errorf("READY record does not match trusted recorder expectations")
	}
	previousDigest := strings.Repeat("0", 64)
	previousTime := uint64(0)
	aborted := false
	phaseIndex := 0
	for index, record := range transcript.Records {
		if err := validateRecorderCommon(record); err != nil {
			return fmt.Errorf("recorder record[%d]: %w", index, err)
		}
		if record.RunID != ready.RunID || record.InvocationNonce != ready.InvocationNonce {
			return fmt.Errorf("recorder record[%d] changes invocation identity", index)
		}
		if record.Ordinal != uint64(index+1) {
			return fmt.Errorf("recorder record[%d] has nonconsecutive ordinal", index)
		}
		if record.MonotonicNS <= previousTime {
			return fmt.Errorf("recorder record[%d] has nonmonotonic time", index)
		}
		if record.PreviousSHA256 != previousDigest {
			return fmt.Errorf("recorder record[%d] breaks previous hash link", index)
		}
		digest, err := recorderRecordDigest(record)
		if err != nil {
			return err
		}
		if record.RecordSHA256 != digest {
			return fmt.Errorf("recorder record[%d] has invalid record hash", index)
		}
		previousDigest, previousTime = record.RecordSHA256, record.MonotonicNS

		switch {
		case index == 0:
			if record.Type != RecorderRecordReady {
				return fmt.Errorf("recorder transcript does not begin with READY")
			}
		case index == len(transcript.Records)-1:
			if record.Type != RecorderRecordFinalized {
				return fmt.Errorf("recorder transcript does not end with FINALIZED")
			}
			if err := validateRecorderFinalized(record, ready.Bridges, aborted, phaseIndex); err != nil {
				return err
			}
		default:
			if record.Type != RecorderRecordPhase {
				return fmt.Errorf("recorder record[%d] is not a phase record", index)
			}
			if aborted {
				return fmt.Errorf("recorder phase follows aborted terminal phase")
			}
			if record.Phase == RecorderOutcomeAborted {
				if record.Failure == nil || !recorderCode.MatchString(record.Failure.Code) || len(record.Failure.Message) == 0 || len(record.Failure.Message) > 512 || strings.TrimSpace(record.Failure.Message) != record.Failure.Message {
					return fmt.Errorf("aborted recorder phase has invalid bounded failure")
				}
				aborted = true
			} else {
				if phaseIndex >= len(recorderLifecyclePhases) || record.Phase != recorderLifecyclePhases[phaseIndex] || record.Failure != nil {
					return fmt.Errorf("recorder phase %q is out of sequence", record.Phase)
				}
				phaseIndex++
			}
			if err := rejectRecorderBindings(record); err != nil {
				return err
			}
		}
	}
	return nil
}

func validateRecorderCommon(record RecorderRecord) error {
	if err := validateRecorderPrintableASCII(record); err != nil {
		return err
	}
	if record.Schema != RecorderControlSchema || !runtimeRunID.MatchString(record.RunID) || !invocationNonce.MatchString(record.InvocationNonce) {
		return fmt.Errorf("invalid recorder schema or invocation identity")
	}
	if record.Ordinal == 0 || record.MonotonicNS == 0 || record.MonotonicNS > math.MaxInt64 || !sha256Value.MatchString(record.PreviousSHA256) || !sha256Value.MatchString(record.RecordSHA256) {
		return fmt.Errorf("invalid recorder ordering or hash-chain fields")
	}
	return nil
}

func (expected RecorderExpectations) validate() error {
	if !runtimeRunID.MatchString(expected.RunID) || !invocationNonce.MatchString(expected.InvocationNonce) || !sha256Value.MatchString(expected.RuntimeLockSHA256) || !sha256Value.MatchString(expected.RecorderPolicySHA256) || !digestReference.MatchString(expected.RecorderImage) || (expected.Platform != "linux/amd64" && expected.Platform != "linux/arm64") {
		return fmt.Errorf("incomplete immutable identity")
	}
	if err := validateRecorderBridges(expected.RunID, expected.Bridges); err != nil {
		return err
	}
	return validateASCIIStrings(expected.RunID, expected.InvocationNonce, expected.RuntimeLockSHA256, expected.RecorderPolicySHA256, expected.RecorderImage, expected.Platform)
}

func sameRecorderBridges(left, right []RecorderBridge) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func validateRecorderPrintableASCII(record RecorderRecord) error {
	values := []string{
		record.Schema, record.Type, record.RunID, record.InvocationNonce, record.PreviousSHA256, record.RecordSHA256,
		record.RuntimeLockSHA256, record.RecorderPolicySHA256, record.RecorderImage, record.Platform,
		record.Phase, record.Outcome,
	}
	for _, bridge := range record.Bridges {
		values = append(values, bridge.Role, bridge.Name)
	}
	if record.Failure != nil {
		values = append(values, record.Failure.Code, record.Failure.Message)
	}
	if record.Manifest != nil {
		for _, artifact := range record.Manifest.Artifacts {
			values = append(values, artifact.Kind, artifact.File, artifact.SHA256)
		}
		for _, counter := range record.Manifest.Interfaces {
			values = append(values, counter.Role, counter.Name)
		}
	}
	return validateASCIIStrings(values...)
}

func validateASCIIStrings(values ...string) error {
	for _, value := range values {
		for index := 0; index < len(value); index++ {
			if value[index] < 0x20 || value[index] > 0x7e {
				return fmt.Errorf("recorder string contains non-printable or non-ASCII byte")
			}
		}
	}
	return nil
}

func validateRecorderReady(record RecorderRecord) error {
	if record.Type != RecorderRecordReady || !sha256Value.MatchString(record.RuntimeLockSHA256) || !sha256Value.MatchString(record.RecorderPolicySHA256) || !digestReference.MatchString(record.RecorderImage) || (record.Platform != "linux/amd64" && record.Platform != "linux/arm64") {
		return fmt.Errorf("READY record lacks immutable recorder bindings")
	}
	if record.Phase != "" || record.Failure != nil || record.Outcome != "" || record.Manifest != nil {
		return fmt.Errorf("READY record contains fields from another record type")
	}
	return validateRecorderBridges(record.RunID, record.Bridges)
}

func validateRecorderBridges(runID string, bridges []RecorderBridge) error {
	wantNames, err := BridgeNames(runID)
	if err != nil {
		return err
	}
	wantRoles := []string{"client_net", "control_net", "data_net"}
	if len(bridges) != len(wantRoles) {
		return fmt.Errorf("recorder must bind exactly three bridges")
	}
	seenIfIndexes := map[uint32]bool{}
	for index, role := range wantRoles {
		bridge := bridges[index]
		if bridge.Role != role || bridge.Name != wantNames[role] || bridge.IfIndex == 0 || bridge.IfIndex > math.MaxInt32 || seenIfIndexes[bridge.IfIndex] {
			return fmt.Errorf("recorder bridge[%d] is not the canonical unique interface", index)
		}
		seenIfIndexes[bridge.IfIndex] = true
	}
	return nil
}

func rejectRecorderBindings(record RecorderRecord) error {
	if record.RuntimeLockSHA256 != "" || record.RecorderPolicySHA256 != "" || record.RecorderImage != "" || record.Platform != "" || len(record.Bridges) != 0 || record.Outcome != "" || record.Manifest != nil {
		return fmt.Errorf("phase record contains fields from another record type")
	}
	return nil
}

func validateRecorderFinalized(record RecorderRecord, bridges []RecorderBridge, aborted bool, phaseIndex int) error {
	if record.Phase != "" || record.Failure != nil || record.RuntimeLockSHA256 != "" || record.RecorderPolicySHA256 != "" || record.RecorderImage != "" || record.Platform != "" || len(record.Bridges) != 0 {
		return fmt.Errorf("FINALIZED record contains fields from another record type")
	}
	wantOutcome := RecorderOutcomeComplete
	if aborted {
		wantOutcome = RecorderOutcomeAborted
	} else if phaseIndex != len(recorderLifecyclePhases) {
		return fmt.Errorf("complete recorder transcript omitted lifecycle phases")
	}
	if record.Outcome != wantOutcome || record.Manifest == nil {
		return fmt.Errorf("FINALIZED outcome does not match recorder lifecycle")
	}
	return validateRecorderManifest(*record.Manifest, bridges, record.Outcome)
}

func validateRecorderManifest(manifest RecorderArtifactManifest, bridges []RecorderBridge, outcome string) error {
	if len(manifest.Artifacts) != 2 || len(manifest.Interfaces) != 3 {
		return fmt.Errorf("recorder manifest must contain two artifacts and three interfaces")
	}
	wantKinds := []string{"pcapng", "ledger"}
	wantMaximumSizes := []uint64{maxRecorderPCAPNGBytes, maxRecorderLedgerBytes}
	seenFiles := map[string]bool{}
	for index, artifact := range manifest.Artifacts {
		if artifact.Kind != wantKinds[index] || !recorderFile.MatchString(artifact.File) || filepath.Base(artifact.File) != artifact.File || !sha256Value.MatchString(artifact.SHA256) || artifact.SizeBytes == 0 || artifact.SizeBytes > wantMaximumSizes[index] || seenFiles[artifact.File] {
			return fmt.Errorf("recorder artifact[%d] violates bounded canonical manifest", index)
		}
		seenFiles[artifact.File] = true
	}
	for index, counter := range manifest.Interfaces {
		bridge := bridges[index]
		if counter.Role != bridge.Role || counter.Name != bridge.Name || counter.IfIndex != bridge.IfIndex || counter.Packets > maxRecorderCounter || counter.DroppedPackets > maxRecorderCounter || counter.TruncatedPackets > maxRecorderCounter {
			return fmt.Errorf("recorder interface counter[%d] does not match READY binding", index)
		}
		if outcome == RecorderOutcomeComplete && (counter.Packets == 0 || counter.DroppedPackets != 0 || counter.TruncatedPackets != 0) {
			return fmt.Errorf("complete recorder interface counter[%d] is empty or lossy", index)
		}
	}
	return nil
}
