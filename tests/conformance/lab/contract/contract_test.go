package contract

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type testSeedManifest struct {
	Schema string `json:"schema"`
	Files  []struct {
		Source string `json:"source"`
		Target string `json:"target"`
		SHA256 string `json:"sha256"`
	} `json:"files"`
}

type testScenario struct {
	Schema          string `json:"schema"`
	Client          string `json:"client"`
	ExpectedVersion string `json:"expected_version"`
}

func TestCommittedLabContract(t *testing.T) {
	root := filepath.Join("..")
	lockFile, err := os.Open(filepath.Join(root, "images.lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	defer lockFile.Close()
	lock, err := DecodeLock(lockFile)
	if err != nil {
		t.Fatalf("image lock: %v", err)
	}
	compose, err := os.ReadFile(filepath.Join(root, "compose.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	if err := ValidateComposeAgainstLock(compose, *lock); err != nil {
		t.Fatalf("compose contract: %v", err)
	}
	corefile, err := os.ReadFile(filepath.Join(root, "dns", "Corefile"))
	if err != nil {
		t.Fatal(err)
	}
	if err := ValidateDNSCorefile(corefile); err != nil {
		t.Fatalf("DNS policy: %v", err)
	}
	for file, capabilities := range map[string]bool{"pricing.json": false, "model-parameters.json": true} {
		data, err := os.ReadFile(filepath.Join(root, "fixtures", file))
		if err != nil {
			t.Fatal(err)
		}
		if err := ValidateBootstrapFixture(data, capabilities); err != nil {
			t.Fatalf("%s: %v", file, err)
		}
	}
}

func TestPrefetchProducesLockedContentEvidenceWithoutLifecycleScripts(t *testing.T) {
	root := filepath.Join("..")
	dockerfile, err := os.ReadFile(filepath.Join(root, "Dockerfile.prefetch"))
	if err != nil {
		t.Fatal(err)
	}
	text := string(dockerfile)
	for _, required := range []string{"--package-lock-only", "--ignore-scripts", "verify-tree.mjs", "client-files.sha256", "resolved-dependencies.json", "prefetch-artifacts.sha256"} {
		if !strings.Contains(text, required) {
			t.Fatalf("prefetch Dockerfile misses %q", required)
		}
	}
	verifier, err := os.ReadFile(filepath.Join(root, "prefetch", "verify-tree.mjs"))
	if err != nil {
		t.Fatal(err)
	}
	for _, required := range []string{"lockfileVersion", "integrity", "sha512-", "installed dependency absent from package lock"} {
		if !strings.Contains(string(verifier), required) {
			t.Fatalf("prefetch verifier misses %q", required)
		}
	}
}

func TestBootstrapFixturesRejectCostAndIdentityDrift(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "fixtures", "pricing.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, mutation := range []struct{ old, new string }{
		{"\"input_cost_per_token\": 0", "\"input_cost_per_token\": 0.0001"},
		{"\"provider\": \"bedrock_mantle\"", "\"provider\": \"openai\""},
		{"\"mode\": \"responses\"", "\"mode\": \"chat\""},
	} {
		mutated := strings.Replace(string(data), mutation.old, mutation.new, 1)
		if err := ValidateBootstrapFixture([]byte(mutated), false); err == nil {
			t.Fatalf("unsafe bootstrap mutation unexpectedly validated: %s", mutation.new)
		}
	}
}

func TestLabContractRejectsAdversarialRelaxation(t *testing.T) {
	compose, err := os.ReadFile(filepath.Join("..", "compose.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	for _, mutation := range []struct{ name, old, new string }{
		{"floating image", "16.9-alpine@sha256:7c688148e5e156d0e86df7ba8ae5a05a2386aaec1e2ad8e6d11bdf10504b1fb7", "latest"},
		{"host network", "networks: [client_net]", "network_mode: host"},
		{"docker socket", "/scenario/scenario.json", "/var/run/docker.sock"},
		{"published port", "user: \"65532:65532\"", "ports: [\"8080:8080\"]"},
		{"external network", "internal: true", "external: true"},
		{"localstack", "health-stub", "localstack"},
		{"remove controlled DNS", "\n  controlled-dns:\n", "\n  removed-dns:\n"},
		{"remove sentinel", "\n  egress-sentinel:\n", "\n  removed-sentinel:\n"},
		{"inject AWS credential", "user: \"65532:65532\"", "environment: {AWS_ACCESS_KEY_ID: leaked}\n  user: \"65532:65532\""},
		{"remove default-route assertion", "ip route | awk '$$1 == \"default\"'", "ip route | awk '$$1 == \"anything\"'"},
	} {
		t.Run(mutation.name, func(t *testing.T) {
			mutated := strings.Replace(string(compose), mutation.old, mutation.new, 1)
			if mutated == string(compose) {
				t.Fatal("test mutation did not apply")
			}
			if err := ValidateCompose([]byte(mutated)); err == nil {
				t.Fatal("unsafe compose mutation unexpectedly validated")
			}
		})
	}
}

func TestDNSPolicyRejectsEscapeAndCoverageLoss(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "dns", "Corefile"))
	if err != nil {
		t.Fatal(err)
	}
	for _, mutation := range []struct{ name, old, new string }{
		{"public forwarder", "hosts {", "forward . 1.1.1.1\n    hosts {"},
		{"fallthrough", "hosts {", "hosts {\n        fallthrough"},
		{"lost Mantle trap", "bedrock-mantle.us-east-1.api.aws", "missing.example"},
		{"lost IPv6 trap", "{$LAB_SENTINEL_IPV6}", "{$MISSING_SENTINEL_IPV6}"},
	} {
		t.Run(mutation.name, func(t *testing.T) {
			mutated := strings.Replace(string(data), mutation.old, mutation.new, 1)
			if mutated == string(data) {
				t.Fatal("test mutation did not apply")
			}
			if err := ValidateDNSCorefile([]byte(mutated)); err == nil {
				t.Fatal("unsafe DNS mutation unexpectedly validated")
			}
		})
	}
}

func TestImageLockRejectsFloatingAndMissingPlatform(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "images.lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, mutation := range []struct{ old, new string }{
		{"@sha256:986f04c2e15e147d00bdd51e8c51bcef3644b13ff806be7d2ff1b261d6dfbae1", ":latest"},
		{"\"linux/amd64\", \"linux/arm64\"", "\"linux/amd64\""},
		{"\"version\": \"0.144.5\"", "\"version\": \"latest\""},
	} {
		mutated := strings.Replace(string(data), mutation.old, mutation.new, 1)
		if _, err := DecodeLock(strings.NewReader(mutated)); err == nil {
			t.Fatal("unsafe image-lock mutation unexpectedly validated")
		}
	}
}

func TestRuntimeLockRequiresAllProducedMultiArchDigests(t *testing.T) {
	valid := `{
  "schema":"sealed-lab-runtime-lock/v1",
  "run_id":"run-1",
  "source_lock_sha256":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
  "images":[
    {"id":"bifrost","reference":"registry.invalid/bifrost@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","platforms":["linux/amd64","linux/arm64"],"source":"git:abc"},
    {"id":"claude-runner","reference":"registry.invalid/claude@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","platforms":["linux/amd64","linux/arm64"],"source":"lock:claude","client_version":"2.1.214"},
    {"id":"codex-runner","reference":"registry.invalid/codex@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","platforms":["linux/amd64","linux/arm64"],"source":"lock:codex","client_version":"0.144.5"},
    {"id":"egress-sentinel","reference":"registry.invalid/sentinel@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","platforms":["linux/amd64","linux/arm64"],"source":"git:abc"}
  ]
}`
	lock, err := DecodeRuntimeLock(strings.NewReader(valid))
	if err != nil {
		t.Fatalf("valid runtime lock: %v", err)
	}
	if got := lock.ComposeEnvironment(); got["CODEX_RUNNER_IMAGE"] == "" || got["BIFROST_IMAGE"] == "" || len(got) != 4 {
		t.Fatalf("incomplete compose environment: %v", got)
	}
	for _, mutation := range []struct{ old, new string }{
		{"registry.invalid/bifrost@sha256:", "registry.invalid/bifrost:latest#"},
		{"\"linux/amd64\",\"linux/arm64\"", "\"linux/amd64\""},
		{"\"id\":\"codex-runner\"", "\"id\":\"unknown-runner\""},
		{"\"source\":\"git:abc\"", "\"source\":\"\""},
		{"\"client_version\":\"0.144.5\"", "\"client_version\":\"latest\""},
		{"\"run_id\":\"run-1\"", "\"run_id\":\"../../escape\""},
	} {
		candidate := strings.Replace(valid, mutation.old, mutation.new, 1)
		if _, err := DecodeRuntimeLock(strings.NewReader(candidate)); err == nil {
			t.Fatalf("unsafe runtime-lock mutation unexpectedly validated: %s", mutation.old)
		}
	}
}

func TestClientSeedsAreHashBoundAndDisableExternalTraffic(t *testing.T) {
	for _, client := range []string{"claude", "codex"} {
		root := filepath.Join("..", "seed", client)
		manifestBytes, err := os.ReadFile(filepath.Join(root, "manifest.json"))
		if err != nil {
			t.Fatal(err)
		}
		var manifest testSeedManifest
		if err := json.Unmarshal(manifestBytes, &manifest); err != nil || manifest.Schema != "sealed-cli-seed/v1" || len(manifest.Files) != 1 {
			t.Fatalf("invalid %s seed manifest: %v", client, err)
		}
		entry := manifest.Files[0]
		data, err := os.ReadFile(filepath.Join(root, entry.Source))
		if err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(data)
		if hex.EncodeToString(digest[:]) != entry.SHA256 {
			t.Fatalf("%s seed digest drift", client)
		}
		text := string(data)
		if client == "codex" {
			for _, required := range []string{"bedrock_mantle/gpt-5.6-sol", "http://bifrost-1:8080/openai/v1", "check_for_update_on_startup = false", "request_max_retries = 0", "stream_max_retries = 0"} {
				if !strings.Contains(text, required) {
					t.Fatalf("Codex seed misses %q", required)
				}
			}
		} else {
			for _, required := range []string{"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_AUTOUPDATER", "DISABLE_ERROR_REPORTING", "DISABLE_TELEMETRY"} {
				if !strings.Contains(text, required) {
					t.Fatalf("Claude seed misses %q", required)
				}
			}
		}
	}
}

func TestVersionScenariosMatchPinnedCLIPackages(t *testing.T) {
	lockFile, err := os.Open(filepath.Join("..", "images.lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	defer lockFile.Close()
	lock, err := DecodeLock(lockFile)
	if err != nil {
		t.Fatal(err)
	}
	versions := make(map[string]string, len(lock.CLIPackages))
	for _, cli := range lock.CLIPackages {
		switch cli.ID {
		case "claude-code-production":
			versions["claude"] = cli.Version
		case "codex-production":
			versions["codex"] = cli.Version
		}
	}
	for _, client := range []string{"claude", "codex"} {
		data, err := os.ReadFile(filepath.Join("..", "scenario", client+"-version.json"))
		if err != nil {
			t.Fatal(err)
		}
		var scenario testScenario
		if err := json.Unmarshal(data, &scenario); err != nil {
			t.Fatal(err)
		}
		if scenario.Schema != "sealed-cli-cell-scenario/v1" || scenario.Client != client || scenario.ExpectedVersion != versions[client] {
			t.Fatalf("%s version scenario does not match image lock: %#v, want %q", client, scenario, versions[client])
		}
	}
}
