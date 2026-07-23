package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

const maxRecorderExpectationsBytes = 16 << 10

type recorderEvidencePaths struct {
	Expectations string
	Transcript   string
	PCAPNG       string
	Ledger       string
}

type recorderInvocationExpectations struct {
	InvocationNonce string                    `json:"invocation_nonce"`
	Bridges         []contract.RecorderBridge `json:"bridges"`
}

func (paths recorderEvidencePaths) validate(required bool) error {
	values := []string{paths.Expectations, paths.Transcript, paths.PCAPNG, paths.Ledger}
	present := 0
	for _, value := range values {
		if value != "" {
			present++
			if !filepath.IsAbs(value) {
				return errors.New("external recorder evidence paths must be absolute")
			}
		}
	}
	if required && present != len(values) {
		return errors.New("runtime-lock/v2 requires expectations, transcript, pcapng, and ledger recorder evidence")
	}
	if !required && present != 0 {
		return errors.New("external recorder evidence is forbidden for runtime-lock/v1 smoke runs")
	}
	return nil
}

// verifyExternalRecorderEvidence is the runner's fail-closed acceptance path.
// Identity fields controlled by the runtime lock and runner are derived here;
// the expectations file supplies only the per-invocation nonce and the
// host-observed bridge identities.
func verifyExternalRecorderEvidence(paths recorderEvidencePaths, lock contract.RuntimeLock, runtimeLockData, policy []byte, nativePlatform string) error {
	expectationsData, err := readBoundedRegularFile(paths.Expectations, maxRecorderExpectationsBytes)
	if err != nil {
		return fmt.Errorf("read recorder expectations: %w", err)
	}
	var invocation recorderInvocationExpectations
	decoder := json.NewDecoder(bytes.NewReader(expectationsData))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&invocation); err != nil {
		return fmt.Errorf("decode recorder expectations: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("recorder expectations contain trailing JSON")
	}
	recorder, ok := lock.NetworkRecorderImage()
	if !ok {
		return errors.New("runtime lock does not expose a validated recorder image")
	}
	expected := contract.RecorderExpectations{
		RunID: lock.RunID, InvocationNonce: invocation.InvocationNonce,
		RuntimeLockSHA256:    contract.SHA256Hex(runtimeLockData),
		RecorderPolicySHA256: contract.SHA256Hex(policy), RecorderImage: recorder.Reference,
		Platform: nativePlatform, Bridges: invocation.Bridges,
	}
	transcriptFile, err := openBoundedFile(paths.Transcript, 1<<20)
	if err != nil {
		return fmt.Errorf("open recorder transcript: %w", err)
	}
	defer transcriptFile.Close()
	transcript, err := contract.DecodeRecorderTranscript(transcriptFile, expected)
	if err != nil {
		return fmt.Errorf("verify recorder transcript: %w", err)
	}
	final := transcript.Records[len(transcript.Records)-1]
	if final.Outcome != contract.RecorderOutcomeComplete {
		return fmt.Errorf("external recorder did not complete: outcome %q", final.Outcome)
	}
	pcapng, err := readBoundedRegularFile(paths.PCAPNG, 256<<20)
	if err != nil {
		return fmt.Errorf("read recorder pcapng: %w", err)
	}
	ledger, err := readBoundedRegularFile(paths.Ledger, 1<<20)
	if err != nil {
		return fmt.Errorf("read recorder ledger: %w", err)
	}
	if err := contract.VerifyRecorderArtifacts(*transcript, expected, pcapng, ledger); err != nil {
		return fmt.Errorf("verify external recorder artifacts: %w", err)
	}
	return nil
}

func openBoundedFile(path string, maximum int64) (io.ReadCloser, error) {
	file, err := openRegularNoSymlink(path)
	if err != nil {
		return nil, err
	}
	info, err := file.Stat()
	if err != nil || info.Size() <= 0 || info.Size() > maximum {
		file.Close()
		return nil, errors.New("artifact is empty or exceeds its bounded contract")
	}
	return file, nil
}

func openRegularNoSymlink(path string) (*os.File, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() {
		return nil, errors.New("artifact path is not a regular non-symlink file")
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	opened, err := file.Stat()
	if err != nil || !os.SameFile(info, opened) {
		file.Close()
		return nil, errors.New("artifact identity changed while opening")
	}
	return file, nil
}

func readBoundedRegularFile(path string, maximum int) ([]byte, error) {
	file, err := openBoundedFile(path, int64(maximum))
	if err != nil {
		return nil, err
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, int64(maximum)+1))
	if err != nil || len(data) == 0 || len(data) > maximum {
		return nil, errors.New("artifact is empty or exceeds its bounded contract")
	}
	return data, nil
}
