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

func TestRuntimeV3AttestationMutants(t *testing.T) {
	digests := []string{strings.Repeat("a", 64), strings.Repeat("b", 64)}
	makeRunner := func(id, version string) RuntimeImage {
		client := strings.TrimSuffix(id, "-runner")
		observed := version
		if client == "codex" {
			observed = "codex-cli " + version
		}
		a := []CLIImageAttestation{{"sealed-cli-image-attestation/v1", client, "linux/amd64", "sha256:" + digests[0], version, observed, 0, "x86_64"}, {"sealed-cli-image-attestation/v1", client, "linux/arm64", "sha256:" + digests[1], version, observed, 0, "aarch64"}}
		raw, _ := json.Marshal(a)
		raw = append(raw, '\n')
		return RuntimeImage{ID: id, Reference: "x@sha256:" + strings.Repeat("c", 64), Platforms: []string{"linux/amd64", "linux/arm64"}, Source: "lock:x", ClientVersion: version, ChildDigests: []PlatformDigest{{"linux/amd64", digests[0]}, {"linux/arm64", digests[1]}}, AttestationSHA256: SHA256Hex(raw), Attestations: a}
	}
	base := RuntimeLock{Schema: RuntimeLockSchemaV3, RunID: "run-1", SourceLockSHA256: strings.Repeat("d", 64), Images: []RuntimeImage{{ID: "bifrost", Reference: "x@sha256:" + strings.Repeat("1", 64), Platforms: []string{"linux/amd64", "linux/arm64"}, Source: "git:x"}, makeRunner("claude-runner", "2.1.214"), makeRunner("codex-runner", "0.144.5"), {ID: "egress-sentinel", Reference: "x@sha256:" + strings.Repeat("2", 64), Platforms: []string{"linux/amd64", "linux/arm64"}, Source: "git:x"}}}
	if err := base.Validate(); err != nil {
		t.Fatal(err)
	}
	for _, mutate := range []func(*RuntimeLock){func(l *RuntimeLock) { l.Images[1].Attestations = nil }, func(l *RuntimeLock) { l.Images[1].AttestationSHA256 = strings.Repeat("e", 64) }, func(l *RuntimeLock) { l.Images[1].Attestations[0].ObservedVersion = "prefix 2.1.214 suffix" }, func(l *RuntimeLock) { l.Images[2].Attestations[0].ObservedVersion = "codex-cli 0.144.50" }} {
		candidate := base
		candidate.Images = append([]RuntimeImage(nil), base.Images...)
		candidate.Images[1].Attestations = append([]CLIImageAttestation(nil), base.Images[1].Attestations...)
		candidate.Images[2].Attestations = append([]CLIImageAttestation(nil), base.Images[2].Attestations...)
		mutate(&candidate)
		if candidate.Validate() == nil {
			t.Fatal("runtime v3 mutant accepted")
		}
	}
}

func TestNativeCLIPackageMatrixMutants(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "images.lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	var base Lock
	if json.Unmarshal(data, &base) != nil || base.Validate() != nil {
		t.Fatal("source lock invalid")
	}
	for _, mutate := range []func(*Lock){func(l *Lock) { l.NativeCLIPackages = nil }, func(l *Lock) {
		l.NativeCLIPackages[0], l.NativeCLIPackages[1] = l.NativeCLIPackages[1], l.NativeCLIPackages[0]
	}, func(l *Lock) { l.NativeCLIPackages[0].ID = "wrong" }, func(l *Lock) { l.NativeCLIPackages[0].Tarball += "/wrong" }, func(l *Lock) { l.NativeCLIPackages[0].Integrity = "sha512-AAAA" }} {
		candidate := base
		candidate.NativeCLIPackages = append([]NativeCLIPackage(nil), base.NativeCLIPackages...)
		mutate(&candidate)
		if candidate.Validate() == nil {
			t.Fatal("native package mutant accepted")
		}
	}
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
	for _, required := range []string{"--package-lock-only", "--ignore-scripts", `npm pack "${CLI_PACKAGE}@${CLI_VERSION}"`, `node /usr/local/lib/verify-sri.mjs /mirror/*.tgz "$CLI_INTEGRITY"`, `node /usr/local/lib/verify-root-lock.mjs /opt/client/package-lock.json "$CLI_PACKAGE" "$CLI_VERSION" "$CLI_INTEGRITY"`, "npm ci --prefix /opt/client --ignore-scripts --omit=dev", "verify-tree.mjs", "client-files.sha256", "resolved-dependencies.json", "prefetch-artifacts.sha256"} {
		if !strings.Contains(text, required) {
			t.Fatalf("prefetch Dockerfile misses %q", required)
		}
	}
	for _, required := range []string{`select-claude-native.mjs`, `@openai/codex)`, `npm_config_platform="$TARGETOS"`, `target-platform.json`} {
		if !strings.Contains(text, required) {
			t.Fatalf("target-native prefetch misses %q", required)
		}
	}
	if strings.Contains(text, "install.cjs") {
		t.Fatal("prefetch executes broad package installer")
	}
	if strings.Count(text, "npm install ") != 1 || strings.Contains(text, "npm install --global") {
		t.Fatal("prefetch must use one lock-generation install and materialize only through npm ci")
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

func TestBridgeNamesUseFullLinuxInterfaceBudgetAndAreRunBound(t *testing.T) {
	first, err := BridgeNames("run-1")
	if err != nil {
		t.Fatal(err)
	}
	second, err := BridgeNames("run-2")
	if err != nil {
		t.Fatal(err)
	}
	seen := map[string]bool{}
	for _, role := range []string{"client_net", "control_net", "data_net"} {
		name := first[role]
		if len(name) != 15 || seen[name] || name == second[role] {
			t.Fatalf("bridge name is not unique, full-width, and run-bound: role=%s name=%q second=%q", role, name, second[role])
		}
		seen[name] = true
	}
	if names, err := BridgeNames("../../escape"); err == nil || names != nil {
		t.Fatal("invalid run id produced bridge names")
	}
}

func TestRuntimeLockV2DeclaresAndVerifiesExternalRecorderImageBinaryAndPolicy(t *testing.T) {
	policy := []byte("compiled recorder policy v1")
	amd64Binary, arm64Binary := []byte("static recorder binary amd64"), []byte("static recorder binary arm64")
	valid := `{
  "schema":"sealed-lab-runtime-lock/v2",
  "run_id":"run-1",
  "source_lock_sha256":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
	  "recorder_policy_sha256":"` + SHA256Hex(policy) + `",
  "images":[
    {"id":"bifrost","reference":"registry.invalid/bifrost@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","platforms":["linux/amd64","linux/arm64"],"source":"git:abc"},
    {"id":"claude-runner","reference":"registry.invalid/claude@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","platforms":["linux/amd64","linux/arm64"],"source":"lock:claude","client_version":"2.1.214"},
    {"id":"codex-runner","reference":"registry.invalid/codex@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","platforms":["linux/amd64","linux/arm64"],"source":"lock:codex","client_version":"0.144.5"},
    {"id":"egress-sentinel","reference":"registry.invalid/sentinel@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","platforms":["linux/amd64","linux/arm64"],"source":"git:abc"},
	    {"id":"network-recorder","reference":"registry.invalid/recorder@sha256:1111111111111111111111111111111111111111111111111111111111111111","platforms":["linux/amd64","linux/arm64"],"source":"git:3333333333333333333333333333333333333333","binary_digests":[{"platform":"linux/amd64","sha256":"` + SHA256Hex(amd64Binary) + `"},{"platform":"linux/arm64","sha256":"` + SHA256Hex(arm64Binary) + `"}]}
  ]
}`
	lock, err := DecodeRuntimeLock(strings.NewReader(valid))
	if err != nil {
		t.Fatal(err)
	}
	if !lock.IsRecorderCapable() {
		t.Fatal("v2 lock did not enable recorder capability")
	}
	recorder, ok := lock.NetworkRecorderImage()
	if !ok || recorder.ID != "network-recorder" || len(lock.ComposeEnvironment()) != 4 {
		t.Fatalf("invalid recorder isolation: recorder=%#v ok=%v env=%v", recorder, ok, lock.ComposeEnvironment())
	}
	if err := lock.VerifyRecorderArtifacts(policy, "linux/amd64", amd64Binary); err != nil {
		t.Fatal(err)
	}
	if err := lock.VerifyRecorderArtifacts(policy, "linux/arm64", arm64Binary); err != nil {
		t.Fatal(err)
	}
	if err := lock.VerifyRecorderArtifacts(policy, "linux/amd64", arm64Binary); err == nil {
		t.Fatal("arm64 recorder bytes accepted for amd64")
	}
	if err := lock.VerifyRecorderArtifacts(nil, "linux/amd64", amd64Binary); err == nil {
		t.Fatal("empty recorder policy accepted")
	}
	if err := lock.VerifyRecorderArtifacts(append(policy, '!'), "linux/amd64", amd64Binary); err == nil {
		t.Fatal("mutated recorder policy bytes accepted")
	}
	if err := lock.VerifyRecorderArtifacts(policy, "linux/amd64", append(amd64Binary, '!')); err == nil {
		t.Fatal("mutated recorder binary bytes accepted")
	}
	if err := lock.VerifyRecorderArtifacts(policy, "linux/s390x", amd64Binary); err == nil {
		t.Fatal("unlocked recorder platform accepted")
	}
	for _, candidate := range []string{
		strings.Replace(valid, `"recorder_policy_sha256":"`+SHA256Hex(policy)+`"`, `"recorder_policy_sha256":""`, 1),
		strings.Replace(valid, `"binary_digests":[{"platform":"linux/amd64","sha256":"`+SHA256Hex(amd64Binary)+`"},{"platform":"linux/arm64","sha256":"`+SHA256Hex(arm64Binary)+`"}]`, `"binary_digests":[]`, 1),
		strings.Replace(valid, `"platform":"linux/arm64"`, `"platform":"linux/amd64"`, 1),
		strings.Replace(valid, `"sha256":"`+SHA256Hex(arm64Binary)+`"`, `"sha256":""`, 1),
		strings.Replace(valid, `"source":"git:`+strings.Repeat("3", 40)+`"`, `"source":"git:main"`, 1),
		strings.Replace(valid, `"id":"network-recorder"`, `"id":"egress-sentinel"`, 1),
		strings.Replace(valid, `"schema":"sealed-lab-runtime-lock/v2"`, `"schema":"sealed-lab-runtime-lock/v1"`, 1),
	} {
		if _, err := DecodeRuntimeLock(strings.NewReader(candidate)); err == nil {
			t.Fatal("unsafe v2 recorder lock mutation accepted")
		}
	}
	for _, candidate := range []string{
		strings.Replace(valid, `"schema":"sealed-lab-runtime-lock/v2"`, `"schema":"sealed-lab-runtime-lock/v2","schema":"sealed-lab-runtime-lock/v2"`, 1),
		strings.Replace(valid, `"recorder_policy_sha256":"`+SHA256Hex(policy)+`"`, `"recorder_policy_sha256":"`+SHA256Hex(policy)+`","recorder_policy_sha256":"`+SHA256Hex(policy)+`"`, 1),
		strings.Replace(valid, `"binary_digests":[`, `"binary_digests":[],"binary_digests":[`, 1),
		strings.Replace(valid, `"schema":"sealed-lab-runtime-lock/v2"`, `"Schema":"sealed-lab-runtime-lock/v2"`, 1),
		strings.Replace(valid, `"binary_digests":[`, `"Binary_Digests":[`, 1),
		strings.Replace(valid, `"schema":"sealed-lab-runtime-lock/v2"`, `"schema":"sealed-lab-runtime-lock/v2","Schema":"sealed-lab-runtime-lock/v2"`, 1),
	} {
		if _, err := DecodeRuntimeLock(strings.NewReader(candidate)); err == nil {
			t.Fatal("duplicate runtime-lock key accepted")
		}
	}
	if _, ok := (RuntimeLock{Schema: RuntimeLockSchemaV2}).NetworkRecorderImage(); ok {
		t.Fatal("unvalidated v2 lock exposed a recorder image")
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
		if err := json.Unmarshal(manifestBytes, &manifest); err != nil || manifest.Schema != "sealed-cli-seed/v1" || len(manifest.Files) == 0 {
			t.Fatalf("invalid %s seed manifest: %v", client, err)
		}
		var text string
		for _, entry := range manifest.Files {
			data, err := os.ReadFile(filepath.Join(root, entry.Source))
			if err != nil {
				t.Fatal(err)
			}
			digest := sha256.Sum256(data)
			if hex.EncodeToString(digest[:]) != entry.SHA256 {
				t.Fatalf("%s seed digest drift", client)
			}
			text += string(data)
			if entry.Source == "model-catalog.json" && (!strings.Contains(string(data), `"use_responses_lite":true`) || !strings.Contains(string(data), `"slug":"bedrock_mantle/gpt-5.5"`)) {
				t.Fatal("Codex catalog does not force Responses Lite")
			}
		}
		if client == "codex" {
			for _, required := range []string{"bedrock_mantle/gpt-5.5", "http://bifrost-1:8080/openai/v1", "responses_websockets = false", "responses_websockets_v2 = false", "requires_openai_auth = false", `env_http_headers = { "x-sealed-codex-run-id" = "LAB_RUN_ID" }`, "model_catalog_json", "request_max_retries = 0", "stream_max_retries = 0"} {
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
