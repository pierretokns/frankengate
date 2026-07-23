package main

import (
	"reflect"
	"strings"
	"testing"
)

func TestScenarioContractRejectsHostAndCloudEnvironment(t *testing.T) {
	base := scenario{
		Schema: "sealed-cli-cell-scenario/v1", RunID: "run-1", Client: "codex",
		Binary: "/opt/client/bin/codex", Args: []string{"--version"}, Env: map[string]string{}, ExpectedVersion: "0.144.5",
	}
	if err := validateScenario(base); err != nil {
		t.Fatalf("valid scenario: %v", err)
	}
	for _, key := range []string{"HOME", "PATH", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "AWS_ACCESS_KEY_ID", "AWS_PROFILE", "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CLIENT_SECRET", "DOCKER_HOST"} {
		mutated := base
		mutated.Env = map[string]string{key: "poison"}
		if err := validateScenario(mutated); err == nil {
			t.Fatalf("host/cloud environment %q unexpectedly allowed", key)
		}
	}
}

func TestScenarioEnvironmentAcceptsOnlyFakeCredentialsAndInternalGateways(t *testing.T) {
	accepted := map[string]string{
		"OPENAI_API_KEY":       sealedFakeCredential,
		"ANTHROPIC_API_KEY":    sealedFakeCredential,
		"ANTHROPIC_AUTH_TOKEN": sealedFakeCredential,
		"OPENAI_BASE_URL":      "http://bifrost-1:8080/openai/v1",
		"ANTHROPIC_BASE_URL":   "http://bifrost-3:8080/anthropic/",
		"DISABLE_TELEMETRY":    "1",
	}
	for key, value := range accepted {
		if err := validateScenarioEnvironment(key, value); err != nil {
			t.Fatalf("valid sealed value for %s rejected: %v", key, err)
		}
	}
	for key, value := range map[string]string{
		"OPENAI_API_KEY":       "sk-real-looking",
		"ANTHROPIC_AUTH_TOKEN": "real-looking",
		"OPENAI_BASE_URL":      "https://api.openai.com/v1",
		"ANTHROPIC_BASE_URL":   "http://169.254.169.254/latest/meta-data",
		"DISABLE_TELEMETRY":    "0",
		"NO_PROXY":             "*",
	} {
		if err := validateScenarioEnvironment(key, value); err == nil {
			t.Fatalf("unsafe value %s=%q unexpectedly accepted", key, value)
		}
	}
}

func TestBaseEnvironmentIsExactAndSecretFree(t *testing.T) {
	environment := baseEnvironment()
	want := []string{
		"CODEX_HOME=/cell/codex", "HOME=/cell/home", "LANG=C.UTF-8", "PATH=/opt/client/bin:/usr/local/bin:/usr/bin:/bin",
		"TMPDIR=/cell/tmp", "TZ=UTC", "XDG_CACHE_HOME=/cell/xdg-cache", "XDG_CONFIG_HOME=/cell/xdg-config", "XDG_DATA_HOME=/cell/xdg-data",
	}
	if strings.Join(environment, "\n") != strings.Join(want, "\n") {
		t.Fatalf("base environment drifted: %v", environment)
	}
	joined := strings.ToUpper(strings.Join(environment, "\n"))
	for _, forbidden := range []string{"PROXY=", "AWS_", "AZURE_", "GOOGLE_", "DOCKER_"} {
		if strings.Contains(joined, forbidden) {
			t.Fatalf("base environment contains %q", forbidden)
		}
	}
}

func TestScenarioBindsClientToExpectedReadOnlyBinary(t *testing.T) {
	for client, binary := range map[string]string{"codex": "/opt/client/bin/codex", "claude": "/opt/client/bin/claude"} {
		cfg := scenario{Schema: "sealed-cli-cell-scenario/v1", RunID: "run", Client: client, Binary: binary, Args: []string{"--version"}, Env: map[string]string{}, ExpectedVersion: "1.2.3"}
		if err := validateScenario(cfg); err != nil {
			t.Fatalf("%s: %v", client, err)
		}
		cfg.Binary = "/tmp/host-binary"
		if err := validateScenario(cfg); err == nil {
			t.Fatalf("%s accepted mutable binary", client)
		}
	}
}

func TestPinnedVersionMustBeExactSemver(t *testing.T) {
	for _, valid := range []string{"0.144.5", "2.1.214", "10.20.30"} {
		if !exactSemver(valid) {
			t.Fatalf("valid version rejected: %s", valid)
		}
	}
	for _, invalid := range []string{"", "latest", "v1.2.3", "1.2", "1.2.3-beta", "1.2.3 extra"} {
		if exactSemver(invalid) {
			t.Fatalf("floating or malformed version accepted: %s", invalid)
		}
	}
	capture := newBoundedCapture(32)
	_, _ = capture.Write([]byte("codex-cli 0.144.5\n"))
	if !capture.Contains("0.144.5") || capture.Contains("2.1.214") {
		t.Fatal("bounded version observation is incorrect")
	}
	if got, err := parseObservedVersion([]byte("codex-cli 0.144.5\n")); err != nil || got != "0.144.5" {
		t.Fatalf("parsed version = %q, %v", got, err)
	}
	for _, invalid := range []string{"codex 0.144.5 node 24.0.0", "codex 0.144.5.1", "no-version"} {
		if _, err := parseObservedVersion([]byte(invalid)); err == nil {
			t.Fatalf("ambiguous/malformed observed version accepted: %q", invalid)
		}
	}
}

func TestScenarioJSONRejectsDuplicateKeysAtAnyDepth(t *testing.T) {
	for _, input := range []string{
		`{"schema":"sealed-cli-cell-scenario/v1","schema":"duplicate"}`,
		`{"env":{"OPENAI_API_KEY":"one","OPENAI_API_KEY":"two"}}`,
		`[{"a":1,"a":2}]`,
	} {
		if err := rejectDuplicateJSONKeys([]byte(input)); err == nil {
			t.Fatalf("duplicate JSON unexpectedly accepted: %s", input)
		}
	}
	if err := rejectDuplicateJSONKeys([]byte(`{"env":{"OPENAI_API_KEY":"one"},"args":["--version"]}`)); err != nil {
		t.Fatalf("valid JSON rejected: %v", err)
	}
}

func TestCodexInferenceBoundaryScenarioIsClosedAndExact(t *testing.T) {
	base := scenario{
		Schema: "sealed-cli-cell-scenario/v2", Operation: "codex-inference-boundary",
		RunID: "run-1", Client: "codex", Binary: "/opt/client/bin/codex",
		Env: map[string]string{
			"OPENAI_API_KEY":  sealedFakeCredential,
			"OPENAI_BASE_URL": "http://bifrost-1:8080/openai/v1",
		},
		ExpectedVersion: "0.144.5", TimeoutMS: 30000,
	}
	if err := validateScenario(base); err != nil {
		t.Fatalf("valid inference-boundary scenario: %v", err)
	}
	mutations := []scenario{base, base, base, base, base, base, base, base}
	mutations[0].Operation = "arbitrary-command"
	mutations[1].Client = "claude"
	mutations[2].Args = []string{"exec", "attacker prompt"}
	mutations[3].Env = map[string]string{"OPENAI_API_KEY": sealedFakeCredential, "OPENAI_BASE_URL": "https://api.openai.com/v1"}
	mutations[4].Env = map[string]string{"OPENAI_API_KEY": sealedFakeCredential, "OPENAI_BASE_URL": "http://bifrost-1:8080/openai/v1", "EXTRA": "1"}
	mutations[5].Env = map[string]string{"OPENAI_BASE_URL": "http://bifrost-1:8080/openai/v1"}
	mutations[6].Env = map[string]string{"OPENAI_API_KEY": sealedFakeCredential, "OPENAI_BASE_URL": "http://bifrost-1:8080/openai/v1/"}
	mutations[7].Env = map[string]string{"OPENAI_API_KEY": sealedFakeCredential, "OPENAI_BASE_URL": "http://bifrost-1:8080/anthropic"}
	for index, mutated := range mutations {
		if err := validateScenario(mutated); err == nil {
			t.Fatalf("unsafe mutation %d accepted", index)
		}
	}
}

func TestCodexInferenceCommandHasNoScenarioControlledArguments(t *testing.T) {
	got := codexInferenceCommand("/opt/client/bin/codex")
	want := commandSpec{Binary: "/opt/client/bin/codex", Args: []string{
		"exec", "--strict-config", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only",
		"--color", "never", "--json", codexBoundaryPrompt,
	}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Codex inference invocation drifted: %#v", got)
	}
	joined := strings.Join(got.Args, " ")
	for _, forbidden := range []string{"--dangerously-bypass", "workspace-write", "danger-full-access", "sh -c", "bash -c"} {
		if strings.Contains(joined, forbidden) {
			t.Fatalf("inference invocation contains unsafe token %q", forbidden)
		}
	}
}

func TestInferenceOutputEvidenceIsBoundedDigestMetadata(t *testing.T) {
	bytes, digest, truncated := summarizeInferenceOutput([]byte("codex-jsonl\n"), true)
	if bytes != 12 || digest != "8d8c418f70cfda7aa01b43bca0fd05cb6b98a518f9567e8f73cf1f12e44de03f" || !truncated {
		t.Fatalf("output evidence = %d %q %v", bytes, digest, truncated)
	}
}

func TestCodexJSONLProvesTurnInitiationAndTerminalUsage(t *testing.T) {
	stream := strings.Join([]string{
		`{"type":"thread.started","thread_id":"019c-test"}`,
		`{"type":"turn.started"}`,
		`{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"SEALED_CODEX_BOUNDARY_OK"}}`,
		`{"type":"turn.completed","usage":{"input_tokens":12,"cached_input_tokens":0,"output_tokens":4}}`,
	}, "\n") + "\n"
	outcome, count, err := validateCodexJSONL([]byte(stream), 0)
	if err != nil || outcome != "completed" || count != 4 {
		t.Fatalf("valid pinned-like JSONL: outcome=%q count=%d err=%v", outcome, count, err)
	}
	failure := strings.Join([]string{
		`{"type":"thread.started","thread_id":"019c-test"}`,
		`{"type":"turn.started"}`,
		`{"type":"error","message":"request failed"}`,
		`{"type":"turn.failed","error":{"message":"request failed"}}`,
	}, "\n") + "\n"
	outcome, count, err = validateCodexJSONL([]byte(failure), 1)
	if err != nil || outcome != "transport_failure_after_turn_start" || count != 4 {
		t.Fatalf("valid transport-failure JSONL: outcome=%q count=%d err=%v", outcome, count, err)
	}
}

func TestCodexJSONLRejectsUsageAndConfigurationTheater(t *testing.T) {
	missingUsage := "{\"type\":\"thread.started\",\"thread_id\":\"019c-test\"}\n{\"type\":\"turn.started\"}\n{\"type\":\"turn.completed\"}\n"
	configError := "error: invalid configuration key model_provider\n"
	wrongOrder := "{\"type\":\"turn.started\"}\n{\"type\":\"thread.started\",\"thread_id\":\"019c-test\"}\n{\"type\":\"turn.failed\"}\n"
	for name, test := range map[string]struct {
		data string
		exit int
	}{
		"missing terminal usage": {missingUsage, 0},
		"configuration stderr":   {configError, 1},
		"wrong semantic order":   {wrongOrder, 1},
	} {
		if _, _, err := validateCodexJSONL([]byte(test.data), test.exit); err == nil {
			t.Fatalf("%s earned request-initiation evidence", name)
		}
	}
}
