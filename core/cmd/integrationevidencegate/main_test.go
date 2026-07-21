package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestIntegrationEvidenceGateCommandStdoutJSONLAndStderrLogs(t *testing.T) {
	if os.Getenv("GO_INTEGRATION_GATE_HELPER") == "1" {
		for i, arg := range os.Args {
			if arg == "--" {
				os.Args = append([]string{os.Args[0]}, os.Args[i+1:]...)
				break
			}
		}
		main()
		return
	}

	junitPath := filepath.Join(t.TempDir(), "gate.xml")
	inputPath := filepath.Join("..", "..", "evidence", "testdata", "integration", "negative", "paid-inference.jsonl")
	cmd := exec.Command(
		os.Args[0],
		"-test.run=TestIntegrationEvidenceGateCommandStdoutJSONLAndStderrLogs",
		"--",
		"-input", inputPath,
		"-now", "2026-01-02T03:04:05Z",
		"-junit", junitPath,
	)
	cmd.Env = append(os.Environ(), "GO_INTEGRATION_GATE_HELPER=1")
	out, err := cmd.Output()
	if err == nil {
		t.Fatal("expected command to fail paid inference fixture")
	}
	exitErr, ok := err.(*exec.ExitError)
	if !ok {
		t.Fatalf("unexpected command error: %T %v", err, err)
	}
	if !strings.Contains(string(exitErr.Stderr), "integration evidence gate failed") {
		t.Fatalf("expected failure log on stderr, got %q", string(exitErr.Stderr))
	}
	for i, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		var value map[string]any
		if err := json.Unmarshal([]byte(line), &value); err != nil {
			t.Fatalf("stdout line %d is not JSON: %v\nstdout:\n%s\nstderr:\n%s", i+1, err, string(out), string(exitErr.Stderr))
		}
	}
	junit, err := os.ReadFile(junitPath)
	if err != nil {
		t.Fatalf("expected junit file: %v", err)
	}
	if !strings.Contains(string(junit), "IE_PAID_INFERENCE") {
		t.Fatalf("junit projection missing diagnostic code:\n%s", string(junit))
	}
}
