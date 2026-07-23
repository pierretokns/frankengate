package main

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

const validRuntimeLock = `{
  "schema":"sealed-lab-runtime-lock/v1",
  "run_id":"test-1",
  "source_lock_sha256":"SOURCE_HASH",
  "images":[
    {"id":"bifrost","reference":"registry.invalid/bifrost@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","platforms":["linux/amd64","linux/arm64"],"source":"git:abc"},
    {"id":"claude-runner","reference":"registry.invalid/claude@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","platforms":["linux/amd64","linux/arm64"],"source":"lock:claude","client_version":"2.1.214"},
    {"id":"codex-runner","reference":"registry.invalid/codex@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","platforms":["linux/amd64","linux/arm64"],"source":"lock:codex","client_version":"0.144.5"},
    {"id":"egress-sentinel","reference":"registry.invalid/sentinel@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","platforms":["linux/amd64","linux/arm64"],"source":"git:abc"}
  ]
}`

type fakeExecutor struct {
	calls    []string
	logCalls int
}

func (fake *fakeExecutor) Run(environment []string, stdout, _ io.Writer, _ string, args ...string) error {
	fake.calls = append(fake.calls, strings.Join(args, " "))
	joined := strings.Join(args, " ")
	switch {
	case strings.Contains(joined, "info --format"):
		_, _ = io.WriteString(stdout, "linux/arm64\n")
	case strings.Contains(joined, "buildx imagetools inspect"):
		_, _ = io.WriteString(stdout, `{"manifests":[{"platform":{"os":"linux","architecture":"amd64"}},{"platform":{"os":"linux","architecture":"arm64"}}]}`)
	case strings.Contains(joined, " config --format json"):
		_, _ = io.WriteString(stdout, resolvedComposeForTest())
	case strings.Contains(joined, " run ") && strings.HasSuffix(joined, "claude-runner"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-cli-cell-evidence/v1","run_id":"test-1","client":"claude","exit_code":0,"environment_names":["CODEX_HOME","HOME","LANG","PATH","TMPDIR","TZ","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME"],"residue_count":0,"client_version":"2.1.214","native_platform":"linux/arm64"}`)
	case strings.Contains(joined, " run ") && strings.HasSuffix(joined, "codex-runner"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-cli-cell-evidence/v2","run_id":"test-1","client":"codex","exit_code":1,"environment_names":["CODEX_HOME","HOME","LANG","OPENAI_API_KEY","OPENAI_BASE_URL","PATH","TMPDIR","TZ","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME"],"residue_count":0,"client_version":"0.144.5","native_platform":"linux/arm64","operation":"codex-inference-boundary","process_started":true,"request_initiated":true,"transport_outcome":"transport_failure_after_turn_start","jsonl_event_count":4,"inference_output_bytes":10,"inference_output_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gateway_base_url":"http://bifrost-1:8080/openai/v1"}`)
	case strings.Contains(joined, " run ") && strings.HasSuffix(joined, "network-probe"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-lab-network-probe/v1","known_dns":1,"unknown_dns_blocked":1,"known_host_trapped":1,"direct_ipv4_blocked":1,"direct_ipv6_blocked":1,"quic_blocked":1,"proxy_bypass_blocked":1}`)
	case strings.Contains(joined, " logs --no-color --no-log-prefix egress-sentinel"):
		fake.logCalls++
		if fake.logCalls > 1 {
			_, _ = io.WriteString(stdout, `{"schema":"sealed-lab-egress-event/v1","observed_at":"2026-07-21T00:00:00Z","run_id":"test-1","source":"172.30.10.10:1234","destination":"172.30.10.254:443","family":"ipv4","transport":"tcp","port":"443","classification":"forbidden-egress-attempt","bytes":1}`+"\n")
		}
	}
	return nil
}

func TestLifecycleUsesPinnedImagesRunsFreshCellsAndTearsDown(t *testing.T) {
	directory := t.TempDir()
	lockPath := filepath.Join(directory, "runtime.json")
	sourceLockPath, err := filepath.Abs(filepath.Join("..", "..", "images.lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	sourceData, err := os.ReadFile(sourceLockPath)
	if err != nil {
		t.Fatal(err)
	}
	runtimeLock := strings.Replace(validRuntimeLock, "SOURCE_HASH", sha256Hex(sourceData), 1)
	if err := os.WriteFile(lockPath, []byte(runtimeLock), 0o600); err != nil {
		t.Fatal(err)
	}
	composePath, err := filepath.Abs(filepath.Join("..", "..", "compose.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	fake := &fakeExecutor{}
	var stdout, stderr bytes.Buffer
	if err := run(fake, lockPath, sourceLockPath, composePath, "/reviewed/docker", "", recorderEvidencePaths{}, &stdout, &stderr); err != nil {
		t.Fatalf("lifecycle failed: %v\nstderr: %s", err, stderr.String())
	}
	var result lifecycleResult
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Schema != "sealed-lab-lifecycle-result/v2" || result.RunID != "test-1" || result.NativePlatform != "linux/arm64" || result.SourceLockSHA256 != sha256Hex(sourceData) || result.StartedAt == "" || result.CompletedAt == "" || !result.TeardownClean || result.NormalCellForbiddenEvents != 0 || result.AdversarialProbeRecordedEvents != 1 || result.PaidInferenceProof != "unproven-external-recorder-required" || len(result.Clients) != 2 || result.CodexInferenceBoundary == nil || !result.CodexInferenceBoundary.RequestInitiated {
		t.Fatalf("unexpected lifecycle result: %#v", result)
	}
	calls := strings.Join(fake.calls, "\n")
	for _, required := range []string{"info --format {{.OSType}}/{{.Architecture}}", "buildx imagetools inspect --raw", " config --format json", " up --detach --wait", " run --rm --no-deps claude-runner", " run --rm --no-deps codex-runner", " run --rm --no-deps network-probe", " logs --no-color --no-log-prefix egress-sentinel", " down --volumes --remove-orphans", " ps --all --quiet", "network ls --quiet --filter", "volume ls --quiet --filter"} {
		if !strings.Contains(calls, required) {
			t.Fatalf("lifecycle omitted %q\n%s", required, calls)
		}
	}
}

func TestNativePlatformEvidenceNormalizesDockerAliasesAndRejectsUnreviewedPlatforms(t *testing.T) {
	for input, want := range map[string]string{"linux/amd64": "linux/amd64", "linux/x86_64": "linux/amd64", "linux/arm64\n": "linux/arm64", "linux/aarch64": "linux/arm64"} {
		if got, err := validateNativePlatform(input); err != nil || got != want {
			t.Fatalf("valid native platform %q: got=%q want=%q err=%v", input, got, want, err)
		}
	}
	for _, invalid := range []string{"", "darwin/arm64", "linux/386", "linux/amd64\nlinux/arm64", "linux/amd64 (emulated)"} {
		if _, err := validateNativePlatform(invalid); err == nil {
			t.Fatalf("unsupported or ambiguous platform %q accepted", invalid)
		}
	}
}

func TestCellRuntimePlatformMustMatchNormalizedDaemonPlatform(t *testing.T) {
	valid := `{"schema":"sealed-cli-cell-evidence/v2","run_id":"run-1","client":"codex","exit_code":1,"environment_names":["CODEX_HOME","HOME","LANG","OPENAI_API_KEY","OPENAI_BASE_URL","PATH","TMPDIR","TZ","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME"],"residue_count":0,"client_version":"0.144.5","native_platform":"linux/arm64","operation":"codex-inference-boundary","process_started":true,"request_initiated":true,"transport_outcome":"transport_failure_after_turn_start","jsonl_event_count":4,"inference_output_bytes":10,"inference_output_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gateway_base_url":"http://bifrost-1:8080/openai/v1"}`
	if got, err := validateCellResult([]byte(valid), "run-1", "codex", "0.144.5", "linux/arm64"); err != nil || got.NativePlatform != "linux/arm64" {
		t.Fatalf("matching cell platform rejected: got=%#v err=%v", got, err)
	}
	for _, mutation := range []string{
		strings.Replace(valid, "linux/arm64", "linux/amd64", 1),
		strings.Replace(valid, "linux/arm64", "linux/aarch64", 1),
		strings.Replace(valid, `"PATH"`, `"HTTP_PROXY"`, 1),
		strings.Replace(valid, `"PATH",`, "", 1),
		strings.Replace(valid, `"request_initiated":true`, `"request_initiated":false`, 1),
		strings.Replace(valid, `"exit_code":1`, `"exit_code":124`, 1),
		strings.Replace(valid, `"exit_code":1`, `"exit_code":-1`, 1),
		strings.Replace(valid, `http://bifrost-1:8080/openai/v1`, `https://api.openai.com/v1`, 1),
	} {
		if _, err := validateCellResult([]byte(mutation), "run-1", "codex", "0.144.5", "linux/arm64"); err == nil {
			t.Fatalf("invalid cell platform evidence accepted: %s", mutation)
		}
	}
}

func TestNetworkProbeEvidenceRequiresEveryNegative(t *testing.T) {
	valid := `{"schema":"sealed-lab-network-probe/v1","known_dns":1,"unknown_dns_blocked":1,"known_host_trapped":1,"direct_ipv4_blocked":1,"direct_ipv6_blocked":1,"quic_blocked":1,"proxy_bypass_blocked":1}`
	if err := validateNetworkProbe([]byte(valid)); err != nil {
		t.Fatal(err)
	}
	for _, field := range []string{"known_dns", "unknown_dns_blocked", "known_host_trapped", "direct_ipv4_blocked", "direct_ipv6_blocked", "quic_blocked", "proxy_bypass_blocked"} {
		mutated := strings.Replace(valid, `"`+field+`":1`, `"`+field+`":0`, 1)
		if err := validateNetworkProbe([]byte(mutated)); err == nil {
			t.Fatalf("missing negative %s unexpectedly accepted", field)
		}
	}
}

func sha256Hex(data []byte) string {
	return contract.SHA256Hex(data)
}

func TestExactOrchestratorEnvironmentDropsProxyAndCloudCredentials(t *testing.T) {
	host := map[string]string{
		"HOME": "/safe/docker-home", "DOCKER_HOST": "unix:///safe/docker.sock",
		"HTTP_PROXY": "http://escape", "AWS_ACCESS_KEY_ID": "secret", "OPENAI_API_KEY": "secret",
	}
	environment := exactEnvironment(map[string]string{"BIFROST_IMAGE": "example@sha256:" + strings.Repeat("a", 64)}, func(key string) string { return host[key] })
	joined := strings.Join(environment, "\n")
	for _, required := range []string{"HOME=/safe/docker-home", "DOCKER_HOST=unix:///safe/docker.sock", "BIFROST_IMAGE="} {
		if !strings.Contains(joined, required) {
			t.Fatalf("missing %q from %s", required, joined)
		}
	}
	for _, forbidden := range []string{"HTTP_PROXY", "AWS_ACCESS_KEY_ID", "OPENAI_API_KEY"} {
		if strings.Contains(joined, forbidden) {
			t.Fatalf("orchestrator environment leaked %s", forbidden)
		}
	}
}

func TestEachRunGetsACompleteDeterministicAddressPlan(t *testing.T) {
	first := networkEnvironment("test-1")
	second := networkEnvironment("test-2")
	if len(first) != 28 || len(second) != 28 || strings.Join(first, "\n") == strings.Join(second, "\n") {
		t.Fatalf("invalid per-run address plans: first=%v second=%v", first, second)
	}
	joined := strings.Join(first, "\n")
	for _, key := range []string{"LAB_CLIENT_IPV4_SUBNET=", "LAB_DATA_IPV4_SUBNET=", "LAB_CONTROL_IPV4_SUBNET=", "LAB_DNS_IPV4=", "LAB_SENTINEL_IPV4=", "LAB_CLIENT_IPV6_SUBNET=", "LAB_DATA_IPV6_SUBNET=", "LAB_CONTROL_IPV6_SUBNET=", "LAB_DNS_IPV6=", "LAB_SENTINEL_IPV6="} {
		if !strings.Contains(joined, key) {
			t.Fatalf("address plan misses %s: %s", key, joined)
		}
	}
	for _, key := range []string{"LAB_CLIENT_BRIDGE=", "LAB_DATA_BRIDGE=", "LAB_CONTROL_BRIDGE="} {
		if !strings.Contains(joined, key) {
			t.Fatalf("address plan misses recorder bridge %s: %s", key, joined)
		}
	}
	for _, key := range []string{"LAB_BIFROST_1_CLIENT_IPV4=", "LAB_BIFROST_1_DATA_IPV4=", "LAB_BIFROST_2_CLIENT_IPV4=", "LAB_BIFROST_2_DATA_IPV4=", "LAB_BIFROST_3_CLIENT_IPV4=", "LAB_BIFROST_3_DATA_IPV4=", "LAB_HEALTH_IPV4="} {
		if !strings.Contains(joined, key) {
			t.Fatalf("address plan misses service address %s: %s", key, joined)
		}
	}
}

func TestOCIIndexAndSentinelJSONLFailClosed(t *testing.T) {
	if err := validateOCIIndex([]byte(`{"manifests":[{"platform":{"os":"linux","architecture":"amd64"}}]}`)); err == nil {
		t.Fatal("single-platform OCI index accepted")
	}
	valid := "{\"schema\":\"sealed-lab-egress-event/v1\",\"observed_at\":\"2026-07-21T00:00:00Z\",\"run_id\":\"run-1\",\"source\":\"172.30.10.10:1234\",\"destination\":\"172.30.10.254:443\",\"family\":\"ipv4\",\"transport\":\"tcp\",\"port\":\"443\",\"classification\":\"forbidden-egress-attempt\",\"bytes\":1}\n"
	if count, err := countSentinelEvents([]byte(valid+valid), "run-1"); err != nil || count != 2 {
		t.Fatalf("valid sentinel events: count=%d err=%v", count, err)
	}
	if _, err := countSentinelEvents([]byte(`{"schema":"unknown"}`), "run-1"); err == nil {
		t.Fatal("unknown sentinel event accepted")
	}
}

func resolvedComposeForTest() string {
	base := func(image string) map[string]any {
		return map[string]any{"image": image, "read_only": true, "cap_drop": []string{"ALL"}, "security_opt": []string{"no-new-privileges:true"}}
	}
	services := map[string]map[string]any{}
	alpine := "alpine:3.21.7@sha256:48b0309ca019d89d40f670aa1bc06e426dc0931948452e8491e3d65087abc07d"
	for _, name := range []string{"netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "netns-claude", "netns-codex"} {
		services[name] = base(alpine)
		services[name]["cap_add"] = []string{"NET_ADMIN"}
		services[name]["command"] = []string{"ip route del default; ip -6 route del default; test -z routes; ip route get dns"}
	}
	services["network-probe"] = base(alpine)
	services["controlled-dns"] = base("coredns/coredns:1.12.4@sha256:986f04c2e15e147d00bdd51e8c51bcef3644b13ff806be7d2ff1b261d6dfbae1")
	services["controlled-dns"]["cap_add"] = []string{"NET_BIND_SERVICE"}
	services["health-stub"] = base("hashicorp/http-echo:1.0.0@sha256:fcb75f691c8b0414d670ae570240cbf95502cc18a9ba57e982ecac589760a186")
	services["contract-stub"] = base("hashicorp/http-echo:1.0.0@sha256:fcb75f691c8b0414d670ae570240cbf95502cc18a9ba57e982ecac589760a186")
	services["postgres"] = base("postgres:16.9-alpine@sha256:7c688148e5e156d0e86df7ba8ae5a05a2386aaec1e2ad8e6d11bdf10504b1fb7")
	for _, name := range []string{"bifrost-1", "bifrost-2", "bifrost-3"} {
		services[name] = base("registry.invalid/bifrost@sha256:" + strings.Repeat("a", 64))
	}
	services["bifrost-1"]["network_mode"] = "service:netns-bifrost-1"
	services["bifrost-2"]["network_mode"] = "service:netns-bifrost-2"
	services["bifrost-3"]["network_mode"] = "service:netns-bifrost-3"
	services["claude-runner"] = base("registry.invalid/claude@sha256:" + strings.Repeat("b", 64))
	services["claude-runner"]["network_mode"] = "service:netns-claude"
	services["codex-runner"] = base("registry.invalid/codex@sha256:" + strings.Repeat("c", 64))
	services["codex-runner"]["network_mode"] = "service:netns-codex"
	services["network-probe"]["network_mode"] = "service:netns-codex"
	services["egress-sentinel"] = base("registry.invalid/sentinel@sha256:" + strings.Repeat("d", 64))
	services["egress-sentinel"]["command"] = []string{"-run-id=test-1"}
	bridges, _ := contract.BridgeNames("test-1")
	networks := map[string]any{}
	for _, name := range []string{"client_net", "control_net", "data_net"} {
		networks[name] = map[string]any{"internal": true, "enable_ipv6": true, "driver": "bridge", "driver_opts": map[string]string{"com.docker.network.bridge.name": bridges[name]}}
	}
	document := map[string]any{"services": services, "networks": networks}
	encoded, _ := json.Marshal(document)
	return string(encoded)
}
