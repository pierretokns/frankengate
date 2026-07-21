package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
	"github.com/maximhq/bifrost/tests/conformance/lab/mantleservice"
)

func TestNetworkEnvironmentCoversEveryComposeStaticIPWithinRunSubnet(t *testing.T) {
	items := networkEnvironment("test-1")
	env := map[string]string{}
	for _, item := range items {
		key, value, _ := strings.Cut(item, "=")
		env[key] = value
	}
	compose, err := os.ReadFile(filepath.Join("..", "..", "compose.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	variable := regexp.MustCompile(`\$\{(LAB_[A-Z0-9_]*(?:IPV4|IPV6)[A-Z0-9_]*)`)
	for _, match := range variable.FindAllStringSubmatch(string(compose), -1) {
		key := match[1]
		if _, ok := env[key]; !ok {
			t.Fatalf("networkEnvironment omits Compose variable %s", key)
		}
	}
	if err := validateNetworkAddressPlan(env); err != nil {
		t.Fatal(err)
	}
	candidate := make(map[string]string, len(env))
	for key, value := range env {
		candidate[key] = value
	}
	candidate["LAB_MANTLE_IPV4"] = candidate["LAB_BIFROST_1_DATA_IPV4"]
	if err := validateNetworkAddressPlan(candidate); err == nil {
		t.Fatal("duplicate data-network IPv4 address was accepted")
	}
}

func validateNetworkAddressPlan(env map[string]string) error {
	seen := map[string]string{}
	for key, value := range env {
		if strings.Contains(key, "SUBNET") || (!strings.Contains(key, "IPV4") && !strings.Contains(key, "IPV6")) {
			continue
		}
		role := "CLIENT"
		if strings.Contains(key, "DATA") || strings.Contains(key, "MANTLE") {
			role = "DATA"
		}
		if strings.Contains(key, "CONTROL") || strings.Contains(key, "CONTRACT") {
			role = "CONTROL"
		}
		family := "IPV4"
		if strings.Contains(key, "IPV6") {
			family = "IPV6"
		}
		_, subnet, err := net.ParseCIDR(env["LAB_"+role+"_"+family+"_SUBNET"])
		if err != nil {
			return err
		}
		ip := net.ParseIP(value)
		if ip == nil || !subnet.Contains(ip) {
			return fmt.Errorf("%s=%s is outside %s", key, value, subnet)
		}
		identity := role + "/" + family + "/" + ip.String()
		if previous, exists := seen[identity]; exists {
			return fmt.Errorf("%s duplicates %s at %s", key, previous, identity)
		}
		seen[identity] = key
	}
	return nil
}

func TestRunnerConsumesActualMantleHandlerTranscript(t *testing.T) {
	var transcript bytes.Buffer
	handler, err := mantleservice.NewIntegrationHandler(&transcript)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "https://"+mantleservice.IntegrationHost+"/openai/v1/responses", strings.NewReader(`{"model":"openai.gpt-5.5","input":"SEALED_CODEX_RUN_ID:test-1","stream":true}`))
	req.Host = mantleservice.IntegrationHost
	req.Header.Set("Authorization", "Bearer synthetic-mantle-contract")
	req.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(httptest.NewRecorder(), req)
	if err := validateMantleTranscript(transcript.Bytes(), "test-1"); err != nil {
		t.Fatal(err)
	}
	var valid mantleservice.TranscriptRecord
	if err := json.Unmarshal(bytes.TrimSpace(transcript.Bytes()), &valid); err != nil {
		t.Fatal(err)
	}
	mutations := []func(*mantleservice.TranscriptRecord){
		func(r *mantleservice.TranscriptRecord) { r.Stream = false },
		func(r *mantleservice.TranscriptRecord) { r.Sequence = 2 },
		func(r *mantleservice.TranscriptRecord) { r.Authorization = "none" },
		func(r *mantleservice.TranscriptRecord) { r.RunID = "other-run" },
	}
	for index, mutate := range mutations {
		candidate := valid
		mutate(&candidate)
		encoded, _ := json.Marshal(candidate)
		if err := validateMantleTranscript(append(encoded, '\n'), "test-1"); err == nil {
			t.Fatalf("unsafe transcript mutation %d accepted: %s", index, encoded)
		}
	}
}

func TestValidateCodexIngressTranscriptRejectsContractMutants(t *testing.T) {
	valid := codexIngressRecord{
		Schema: "sealed-codex-bifrost-ingress/v1", RunID: "test-1", InputRunID: "test-1", Method: "POST",
		Path: "/openai/v1/responses", Model: "bedrock_mantle/gpt-5.5", Stream: true,
		LiteHeaderCount: 1, LiteHeaderValue: "true", FirstInputType: "additional_tools",
		FirstInputRole: "developer", FirstInputToolCount: 1, BodyBytes: 512,
		BodySHA256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
	}
	boundary := &cellResult{RunID: "test-1", Client: "codex", ExitCode: 0, ProcessStarted: true, RequestInitiated: true, TransportOutcome: "completed", EventCount: 4, OutputBytes: 10, OutputSHA256: valid.BodySHA256}
	encode := func(record codexIngressRecord) []byte {
		data, err := json.Marshal(record)
		if err != nil {
			t.Fatal(err)
		}
		return append(data, '\n')
	}
	if _, err := validateCodexIngressTranscript(encode(valid), "test-1", boundary); err != nil {
		t.Fatal(err)
	}
	mutations := []func(*codexIngressRecord){
		func(r *codexIngressRecord) { r.Method = "GET" },
		func(r *codexIngressRecord) { r.InputRunID = "other-run" },
		func(r *codexIngressRecord) { r.Path = "/v1/responses" },
		func(r *codexIngressRecord) { r.Model = "openai/gpt-5.5" },
		func(r *codexIngressRecord) { r.Stream = false },
		func(r *codexIngressRecord) { r.LiteHeaderCount = 2 },
		func(r *codexIngressRecord) { r.LiteHeaderValue = "false" },
		func(r *codexIngressRecord) { r.WebsocketUpgrade = true },
		func(r *codexIngressRecord) { r.TopLevelInstructions = true },
		func(r *codexIngressRecord) { r.TopLevelTools = true },
		func(r *codexIngressRecord) { r.ParallelToolCalls = true },
		func(r *codexIngressRecord) { r.FirstInputType = "message" },
		func(r *codexIngressRecord) { r.FirstInputRole = "user" },
		func(r *codexIngressRecord) { r.FirstInputToolCount = 0 },
		func(r *codexIngressRecord) { r.BodyBytes = 0 },
		func(r *codexIngressRecord) { r.BodySHA256 = "raw-body-forbidden" },
	}
	for index, mutate := range mutations {
		candidate := valid
		mutate(&candidate)
		if _, err := validateCodexIngressTranscript(encode(candidate), "test-1", boundary); err == nil {
			t.Fatalf("unsafe ingress mutation %d accepted", index)
		}
	}
	if _, err := validateCodexIngressTranscript(append(encode(valid), encode(valid)...), "test-1", boundary); err == nil {
		t.Fatal("duplicate ingress record accepted")
	}
	wrongRun := valid
	wrongRun.RunID = "other-run"
	if _, err := validateCodexIngressTranscript(encode(wrongRun), "test-1", boundary); err == nil {
		t.Fatal("wrong-run ingress record accepted")
	}
	badBoundary := *boundary
	badBoundary.TransportOutcome = "failed"
	if _, err := validateCodexIngressTranscript(encode(valid), "test-1", &badBoundary); err == nil {
		t.Fatal("failed Codex terminal evidence accepted")
	}
}

func TestParseCodexIngressRejectionsPreservesOnlyAllowlistedMetadata(t *testing.T) {
	valid := `{"schema":"sealed-codex-bifrost-ingress-rejected/v1","run_id":"test-1","reason":"lite_predicate_mismatch","body_bounded":true,"json_unique":true,"json_decoded":true,"method_ok":true,"model_ok":true,"stream_ok":true,"lite_header_ok":true,"no_websocket_upgrade":true,"instructions_absent":true,"top_level_tools_absent":true,"parallel_false_present":true,"input_present":true,"first_input_type_ok":true,"first_input_role_ok":true,"tool_count_ok":true,"tool_shapes_ok":false,"tool_types":["custom","tool_search"],"invalid_tool_indices":[1],"input_run_id_count":1,"input_run_id_matches":true,"raw_body":"Bearer secret"}`
	records := parseCodexIngressRejections([]byte(valid+"\n"), "test-1", 4)
	if len(records) != 1 || records[0].ToolShapesOK || !records[0].InputRunIDMatches || !reflect.DeepEqual(records[0].ToolTypes, []string{"custom", "tool_search"}) || !reflect.DeepEqual(records[0].InvalidToolIndices, []int{1}) {
		t.Fatalf("rejection metadata not preserved: %#v", records)
	}
	encoded, _ := json.Marshal(records)
	if bytes.Contains(encoded, []byte("Bearer")) || bytes.Contains(encoded, []byte("raw_body")) {
		t.Fatalf("unallowlisted content survived: %s", encoded)
	}
	mutants := []string{
		strings.Replace(valid, `"run_id":"test-1"`, `"run_id":"other"`, 1),
		strings.Replace(valid, `"reason":"lite_predicate_mismatch"`, `"reason":"Bearer secret"`, 1),
		strings.Replace(valid, `"input_run_id_count":1`, `"input_run_id_count":99`, 1),
		strings.Replace(valid, `"custom"`, `"bearer_secret_value"`, 1),
		strings.Replace(valid, `"invalid_tool_indices":[1]`, `"invalid_tool_indices":[128]`, 1),
	}
	for index, mutant := range mutants {
		if got := parseCodexIngressRejections([]byte(mutant+"\n"), "test-1", 4); len(got) != 0 {
			t.Fatalf("unsafe rejection mutant %d accepted: %#v", index, got)
		}
	}
}

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
	failUp   bool
}

type executorFunc func([]string, io.Writer, io.Writer, string, ...string) error

func (fn executorFunc) Run(env []string, stdout, stderr io.Writer, name string, args ...string) error {
	return fn(env, stdout, stderr, name, args...)
}
func (fn executorFunc) RunDiagnostic(ctx context.Context, env []string, stdout, stderr io.Writer, name string, args ...string) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return fn(env, stdout, stderr, name, args...)
	}
}

type deadlineExecutor struct{ deadlines int }

func boundDiagnostic(path string) diagnosticsPaths {
	return diagnosticsPaths{Artifact: path, RunID: "test-1", SourceLockSHA256: strings.Repeat("a", 64), RuntimeLockSHA256: strings.Repeat("b", 64), Phase: "failure-teardown"}
}

func (executor *deadlineExecutor) Run(_ []string, _ io.Writer, _ io.Writer, _ string, _ ...string) error {
	return nil
}
func (executor *deadlineExecutor) RunDiagnostic(ctx context.Context, _ []string, _ io.Writer, _ io.Writer, _ string, _ ...string) error {
	deadline, ok := ctx.Deadline()
	if !ok || time.Until(deadline) > 5*time.Second {
		return errors.New("missing diagnostic deadline")
	}
	executor.deadlines++
	return context.DeadlineExceeded
}

func TestComposeDiagnosticsAreBoundedNewRegularFiles(t *testing.T) {
	directory := t.TempDir()
	path := filepath.Join(directory, "failure-diagnostics.json")
	executor := executorFunc(func(_ []string, stdout, stderr io.Writer, _ string, args ...string) error {
		_, _ = io.WriteString(stdout, "Authorization: Bearer secret PEM -----BEGIN PRIVATE KEY----- "+strings.Join(args, " "))
		return nil
	})
	if err := writeComposeDiagnostics(executor, nil, "/docker", []string{"compose"}, boundDiagnostic(path)); err != nil {
		t.Fatal(err)
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm() != 0o600 || info.Size() == 0 {
		t.Fatalf("invalid diagnostic %s: %v %#v", path, err, info)
	}
	data, _ := os.ReadFile(path)
	if bytes.Contains(data, []byte("Bearer")) || bytes.Contains(data, []byte("PRIVATE KEY")) {
		t.Fatal("structured diagnostics leaked raw secret content")
	}
	if err := writeComposeDiagnostics(executor, nil, "/docker", []string{"compose"}, boundDiagnostic(path)); err == nil {
		t.Fatal("stale artifact was preserved or overwritten")
	}
	unsafeDir := t.TempDir()
	target := filepath.Join(unsafeDir, "target")
	_ = os.WriteFile(target, []byte("x"), 0o600)
	if err := os.Symlink(target, filepath.Join(unsafeDir, "link")); err != nil {
		t.Fatal(err)
	}
	if err := writeComposeDiagnostics(executor, nil, "/docker", []string{"compose"}, boundDiagnostic(filepath.Join(unsafeDir, "new.json"))); err == nil {
		t.Fatal("symlink directory entry accepted")
	}
	hardDir := t.TempDir()
	first := filepath.Join(hardDir, "first")
	_ = os.WriteFile(first, []byte("x"), 0o600)
	if err := os.Link(first, filepath.Join(hardDir, "second")); err != nil {
		t.Fatal(err)
	}
	if err := writeComposeDiagnostics(executor, nil, "/docker", []string{"compose"}, boundDiagnostic(filepath.Join(hardDir, "new.json"))); err == nil {
		t.Fatal("hardlink directory entry accepted")
	}
	if err := (diagnosticsPaths{Artifact: "relative"}).validate(); err == nil {
		t.Fatal("relative artifact accepted")
	}
	if err := (diagnosticsPaths{}).validate(); err != nil {
		t.Fatal(err)
	}
	oversizedDir := t.TempDir()
	oversized := executorFunc(func(_ []string, stdout, _ io.Writer, _ string, _ ...string) error {
		_, _ = stdout.Write(bytes.Repeat([]byte{'x'}, (256<<10)+1))
		return nil
	})
	largePath := filepath.Join(oversizedDir, "failure.json")
	if err := writeComposeDiagnostics(oversized, nil, "/docker", []string{"compose"}, boundDiagnostic(largePath)); err != nil {
		t.Fatal(err)
	}
	largeData, _ := os.ReadFile(largePath)
	if bytes.Contains(largeData, bytes.Repeat([]byte{'x'}, 64)) {
		t.Fatal("oversized content was not reduced to metadata")
	}
	deadlineDir := t.TempDir()
	deadline := &deadlineExecutor{}
	if err := writeComposeDiagnostics(deadline, nil, "/docker", []string{"compose"}, boundDiagnostic(filepath.Join(deadlineDir, "failure.json"))); err != nil {
		t.Fatal(err)
	}
	if deadline.deadlines != 11 {
		t.Fatalf("expected bounded version and ps plus nine log commands, got %d", deadline.deadlines)
	}
}

func TestSanitizedFailureClassificationMutants(t *testing.T) {
	cases := []struct {
		input  string
		failed bool
		want   string
	}{
		{"CONFIG Parse failed", false, "config-parse"},
		{"SQLite driver requires CGO", false, "sqlite-cgo-disabled"},
		{"SQLSTATE 28P01", false, "postgres-auth"},
		{"could not connect to POSTGRES", false, "postgres-connect"},
		{"unexpected startup panic", true, "generic-startup"},
		{"healthy startup chatter", false, "none"},
		{"", true, "none"},
	}
	for _, test := range cases {
		if got := classifySanitizedFailure([]byte(test.input), test.failed); got != test.want {
			t.Errorf("%q: got %q want %q", test.input, got, test.want)
		}
	}
}

func TestSuccessfulOneShotServiceIsNotFailed(t *testing.T) {
	if serviceStatusFailed("exited", "unknown", 0) {
		t.Fatal("expected exited/0 config seed was classified as failed")
	}
	if got := classifySanitizedFailure([]byte("seed completed normally"), serviceStatusFailed("exited", "unknown", 0)); got != "none" {
		t.Fatalf("normal one-shot log got %q", got)
	}
	for _, test := range []struct {
		state, health string
		exit          int
	}{{"exited", "unknown", 1}, {"dead", "unknown", 0}, {"restarting", "unknown", 0}, {"running", "unhealthy", 0}} {
		if !serviceStatusFailed(test.state, test.health, test.exit) {
			t.Errorf("failed status accepted: %#v", test)
		}
	}
}

func TestConfigSeedRecordRequiresOneExactJSONRecord(t *testing.T) {
	valid := `{"schema":"sealed-lab-config-seed/v1","revision":"sealed-lab-c9-gpt55-v1","provider":"bedrock_mantle","alias":"gpt-5.5","model":"openai.gpt-5.5","tls":"private-ca-verified"}`
	if _, err := parseSeedRecord([]byte(valid + "\n")); err != nil {
		t.Fatal(err)
	}
	mutants := []string{
		`prefix ` + valid,
		valid + "\n" + valid,
		`{"schema":"sealed-lab-config-seed/v1","revision":"sealed-lab-c9-gpt55-v1"}`,
		strings.Replace(valid, `"provider":"bedrock_mantle"`, `"provider":"bedrock"`, 1),
		strings.Replace(valid, `"tls":"private-ca-verified"`, `"tls":"insecure"`, 1),
		strings.TrimSuffix(valid, "}") + `,"extra":true}`,
		strings.TrimSuffix(valid, "}") + `,"revision":"sealed-lab-c9-gpt55-v1"}`,
		valid + strings.Repeat(" ", 4096),
	}
	for _, mutant := range mutants {
		if _, err := parseSeedRecord([]byte(mutant)); err == nil {
			t.Errorf("accepted mutant %q", mutant)
		}
	}
}

func TestDiagnosticsRejectDuplicateStatusAndInspectOOM(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "failure.json")
	executor := executorFunc(func(_ []string, stdout, stderr io.Writer, _ string, args ...string) error {
		joined := strings.Join(args, " ")
		switch {
		case strings.Contains(joined, " ps --all --format json"):
			_, _ = io.WriteString(stdout, `[{"Service":"postgres","ID":"aaaaaaaaaaaa","State":"exited","ExitCode":1},{"Service":"postgres","ID":"bbbbbbbbbbbb","State":"running","ExitCode":0}]`)
		case strings.HasPrefix(joined, "inspect --format"):
			_, _ = io.WriteString(stdout, "true\n")
		case strings.Contains(joined, "logs --tail 200") && strings.HasSuffix(joined, "postgres"):
			_, _ = io.WriteString(stdout, "password authentication failed")
		}
		return nil
	})
	if err := writeComposeDiagnostics(executor, nil, "/docker", []string{"compose"}, boundDiagnostic(path)); err != nil {
		t.Fatal(err)
	}
	var got struct {
		StatusCapture  string `json:"status_capture"`
		StatusRowCount int    `json:"status_row_count"`
		Missing        int    `json:"missing_status_rows"`
		Services       []struct {
			Service      string `json:"service"`
			OOM          string `json:"oom"`
			FailureClass string `json:"failure_class"`
		} `json:"services"`
	}
	data, _ := os.ReadFile(path)
	if err := json.Unmarshal(data, &got); err != nil {
		t.Fatal(err)
	}
	if got.StatusCapture != "malformed" || got.StatusRowCount != 1 || got.Missing != 8 {
		t.Fatalf("bad status summary: %s", data)
	}
	if got.Services[0].Service != "postgres" || got.Services[0].OOM != "true" || got.Services[0].FailureClass != "postgres-auth" {
		t.Fatalf("bad postgres classification: %s", data)
	}
	if got.Services[1].FailureClass != "missing-status-row" {
		t.Fatalf("missing status not classified: %s", data)
	}
}

func TestDiagnosticsAcceptCompleteKnownComposeStatus(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "failure.json")
	names := []string{"postgres", "config-seed", "mantle-contract-service", "bifrost-1", "bifrost-2", "bifrost-3", "netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "netns-codex", "netns-claude", "health-stub", "contract-stub", "controlled-dns", "egress-sentinel", "codex-runner", "claude-runner", "network-probe"}
	rows := make([]map[string]any, 0, len(names))
	for index, name := range names {
		rows = append(rows, map[string]any{"Service": name, "ID": fmt.Sprintf("%012x", index+1), "State": "running", "Health": "healthy", "ExitCode": 0})
	}
	statusJSON, _ := json.Marshal(rows)
	executor := executorFunc(func(_ []string, stdout, stderr io.Writer, _ string, args ...string) error {
		joined := strings.Join(args, " ")
		if strings.Contains(joined, " ps --all --format json") {
			_, _ = stdout.Write(statusJSON)
			_, _ = io.WriteString(stderr, "compose mode warning\n")
		}
		if strings.HasPrefix(joined, "inspect --format") {
			_, _ = io.WriteString(stdout, "false\n")
		}
		if strings.Contains(joined, "logs --tail 200") {
			_, _ = io.WriteString(stdout, "healthy startup chatter")
		}
		return nil
	})
	if err := writeComposeDiagnostics(executor, nil, "/docker", []string{"compose"}, boundDiagnostic(path)); err != nil {
		t.Fatal(err)
	}
	var got struct {
		Status      string `json:"status_capture"`
		Format      string `json:"status_format"`
		Rows        int    `json:"status_row_count"`
		Records     int    `json:"status_record_count"`
		StderrBytes int    `json:"status_stderr_bytes"`
		Missing     int    `json:"missing_status_rows"`
		Services    []struct {
			Failure string `json:"failure_class"`
		} `json:"services"`
	}
	data, _ := os.ReadFile(path)
	if err := json.Unmarshal(data, &got); err != nil {
		t.Fatal(err)
	}
	if got.Status != "ok" || got.Format != "legacy-json-array" || got.Rows != 9 || got.Records != 18 || got.StderrBytes == 0 || got.Missing != 0 || len(got.Services) != 9 {
		t.Fatalf("full Compose status rejected: %s", data)
	}
	for _, service := range got.Services {
		if service.Failure != "none" {
			t.Fatalf("healthy logs classified as failure: %s", data)
		}
	}
}

func TestComposePSAcceptsArrayAndJSONL(t *testing.T) {
	row1 := `{"ID":"aaaaaaaaaaaa","Service":"postgres","State":"running","Health":"healthy","ExitCode":0}`
	row2 := `{"ID":"bbbbbbbbbbbb","Service":"config-seed","State":"exited","Health":"","ExitCode":0}`
	for _, input := range []string{"[" + row1 + "," + row2 + "]", row1 + "\n" + row2 + "\n"} {
		rows, _, err := decodeComposePS([]byte(input))
		if err != nil || len(rows) != 2 {
			t.Fatalf("status format rejected: %v %#v", err, rows)
		}
	}
	mutants := []string{"", row1 + "\nnot-json", "[] trailing", strings.Replace(row1, `"ID":`, `"ID":"cccccccccccc","ID":`, 1), strings.Replace(row1, `"ExitCode":0`, `"ExitCode":-1`, 1), strings.Replace(row1, `,"ExitCode":0`, "", 1), strings.Replace(row1, `"ExitCode":0`, `"ExitCode":"0"`, 1), strings.TrimSuffix(row1, "}") + `,"Mystery":true}`}
	for _, input := range mutants {
		if _, _, err := decodeComposePS([]byte(input)); err == nil {
			t.Fatalf("malformed status accepted: %q", input)
		}
	}
	many := "[" + strings.TrimSuffix(strings.Repeat(row1+",", 33), ",") + "]"
	if _, _, err := decodeComposePS([]byte(many)); err == nil {
		t.Fatal("oversized row set accepted")
	}
}

func TestOCIIndexMustMatchAttestedChildren(t *testing.T) {
	a, b := strings.Repeat("a", 64), strings.Repeat("b", 64)
	image := contract.RuntimeImage{ChildDigests: []contract.PlatformDigest{{Platform: "linux/amd64", SHA256: a}, {Platform: "linux/arm64", SHA256: b}}}
	valid := []byte(`{"manifests":[{"digest":"sha256:` + a + `","platform":{"os":"linux","architecture":"amd64"}},{"digest":"sha256:` + b + `","platform":{"os":"linux","architecture":"arm64"}}]}`)
	if err := validateOCIIndexForImage(valid, image); err != nil {
		t.Fatal(err)
	}
	for _, bad := range [][]byte{bytes.Replace(valid, []byte("sha256:"+a), []byte("sha256:"+strings.Repeat("c", 64)), 1), bytes.Replace(valid, []byte(`"amd64"`), []byte(`"arm64"`), 1), append(valid, []byte(` {}`)...)} {
		if validateOCIIndexForImage(bad, image) == nil {
			t.Fatal("OCI index mutant accepted")
		}
	}
}

func (fake *fakeExecutor) Run(environment []string, stdout, _ io.Writer, _ string, args ...string) error {
	fake.calls = append(fake.calls, strings.Join(args, " "))
	joined := strings.Join(args, " ")
	if fake.failUp && strings.Contains(joined, " up --detach --wait") {
		return errors.New("synthetic up failure")
	}
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
		_, _ = io.WriteString(stdout, `{"schema":"sealed-cli-cell-evidence/v2","run_id":"test-1","client":"codex","exit_code":0,"environment_names":["CODEX_HOME","HOME","LANG","OPENAI_API_KEY","OPENAI_BASE_URL","PATH","TMPDIR","TZ","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME"],"residue_count":0,"client_version":"0.144.5","native_platform":"linux/arm64","operation":"codex-inference-boundary","process_started":true,"request_initiated":true,"transport_outcome":"completed","jsonl_event_count":4,"inference_output_bytes":10,"inference_output_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gateway_base_url":"http://bifrost-1:8080/openai/v1"}`)
	case strings.Contains(joined, " run ") && strings.HasSuffix(joined, "network-probe"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-lab-network-probe/v1","known_dns":1,"unknown_dns_blocked":1,"known_host_trapped":1,"direct_ipv4_blocked":1,"direct_ipv6_blocked":1,"quic_blocked":1,"proxy_bypass_blocked":1}`)
	case strings.Contains(joined, " logs --no-color --no-log-prefix mantle-contract-service"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-mantle-upstream-transcript/v1","sequence":1,"method":"POST","host":"bedrock-mantle.us-east-1.api.aws","path":"/openai/v1/responses","model":"openai.gpt-5.5","stream":true,"body_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":200,"authorization_class":"synthetic-bearer","run_id":"test-1"}`+"\n")
	case strings.Contains(joined, " logs --no-color --no-log-prefix bifrost-1"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-codex-bifrost-ingress/v1","run_id":"test-1","input_run_id":"test-1","method":"POST","path":"/openai/v1/responses","model":"bedrock_mantle/gpt-5.5","stream":true,"lite_header_count":1,"lite_header_value":"true","websocket_upgrade":false,"top_level_instructions":false,"top_level_tools":false,"parallel_tool_calls":false,"first_input_type":"additional_tools","first_input_role":"developer","first_input_tool_count":1,"body_bytes":512,"body_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`+"\n")
	case strings.Contains(joined, " logs --no-color --no-log-prefix config-seed"):
		_, _ = io.WriteString(stdout, `{"schema":"sealed-lab-config-seed/v1","revision":"sealed-lab-c9-gpt55-v1","provider":"bedrock_mantle","alias":"gpt-5.5","model":"openai.gpt-5.5","tls":"private-ca-verified"}`+"\n")
	case strings.Contains(joined, " logs --no-color --no-log-prefix egress-sentinel"):
		fake.logCalls++
		if fake.logCalls > 1 {
			_, _ = io.WriteString(stdout, `{"schema":"sealed-lab-egress-event/v1","observed_at":"2026-07-21T00:00:00Z","run_id":"test-1","source":"172.30.10.10:1234","destination":"172.30.10.254:443","family":"ipv4","transport":"tcp","port":"443","classification":"forbidden-egress-attempt","bytes":1}`+"\n")
		}
	}
	return nil
}
func (fake *fakeExecutor) RunDiagnostic(ctx context.Context, environment []string, stdout, stderr io.Writer, name string, args ...string) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return fake.Run(environment, stdout, stderr, name, args...)
	}
}

func TestFailureDiagnosticsPrecedeTeardownAndDoNotContaminateStdout(t *testing.T) {
	directory := t.TempDir()
	sourceLockPath, _ := filepath.Abs(filepath.Join("..", "..", "images.lock.v1.json"))
	sourceData, _ := os.ReadFile(sourceLockPath)
	lockPath := filepath.Join(directory, "runtime.json")
	_ = os.WriteFile(lockPath, []byte(strings.Replace(validRuntimeLock, "SOURCE_HASH", sha256Hex(sourceData), 1)), 0o600)
	composePath, _ := filepath.Abs(filepath.Join("..", "..", "compose.yaml"))
	diagnosticPath := filepath.Join(directory, "failure.json")
	fake := &fakeExecutor{failUp: true}
	var stdout, stderr bytes.Buffer
	err := run(fake, lockPath, sourceLockPath, composePath, "/reviewed/docker", "", recorderEvidencePaths{}, diagnosticsPaths{Artifact: diagnosticPath}, &stdout, &stderr)
	if err == nil || !strings.Contains(err.Error(), "synthetic up failure") {
		t.Fatalf("primary error was not preserved: %v", err)
	}
	if stdout.Len() != 0 {
		t.Fatalf("failure diagnostics contaminated lifecycle stdout: %q", stdout.String())
	}
	calls := strings.Join(fake.calls, "\n")
	psIndex := strings.Index(calls, " ps --all --format json")
	logIndex := strings.Index(calls, " logs --tail 200")
	downIndex := strings.Index(calls, " down --volumes")
	if psIndex < 0 || logIndex < psIndex || downIndex < logIndex {
		t.Fatalf("diagnostics were not captured in ps/logs/down order:\n%s", calls)
	}
	if _, err := os.Stat(diagnosticPath); err != nil {
		t.Fatal(err)
	}
	var diagnostic map[string]any
	data, _ := os.ReadFile(diagnosticPath)
	if json.Unmarshal(data, &diagnostic) != nil || diagnostic["run_id"] != "test-1" || diagnostic["source_lock_sha256"] != sha256Hex(sourceData) || diagnostic["runtime_lock_sha256"] == "" || diagnostic["phase"] != "failure-teardown" || diagnostic["nonce"] == "" || diagnostic["captured_at"] == "" {
		t.Fatalf("unbound failure diagnostics: %s", data)
	}
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
	if err := run(fake, lockPath, sourceLockPath, composePath, "/reviewed/docker", "", recorderEvidencePaths{}, diagnosticsPaths{}, &stdout, &stderr); err != nil {
		t.Fatalf("lifecycle failed: %v\nstderr: %s", err, stderr.String())
	}
	var result lifecycleResult
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Schema != "sealed-lab-lifecycle-result/v2" || result.SeedConfigRevision != "sealed-lab-c9-gpt55-v1" || result.RunID != "test-1" || result.NativePlatform != "linux/arm64" || result.SourceLockSHA256 != sha256Hex(sourceData) || result.StartedAt == "" || result.CompletedAt == "" || !result.TeardownClean || result.NormalCellForbiddenEvents != 0 || result.AdversarialProbeRecordedEvents != 1 || result.PaidInferenceProof != "unproven-external-recorder-required" || len(result.Clients) != 2 || result.CodexInferenceBoundary == nil || !result.CodexInferenceBoundary.RequestInitiated {
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
	valid := `{"schema":"sealed-cli-cell-evidence/v2","run_id":"run-1","client":"codex","exit_code":0,"environment_names":["CODEX_HOME","HOME","LANG","OPENAI_API_KEY","OPENAI_BASE_URL","PATH","TMPDIR","TZ","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME"],"residue_count":0,"client_version":"0.144.5","native_platform":"linux/arm64","operation":"codex-inference-boundary","process_started":true,"request_initiated":true,"transport_outcome":"completed","jsonl_event_count":4,"inference_output_bytes":10,"inference_output_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gateway_base_url":"http://bifrost-1:8080/openai/v1"}`
	if got, err := validateCellResult([]byte(valid), "run-1", "codex", "0.144.5", "linux/arm64"); err != nil || got.NativePlatform != "linux/arm64" {
		t.Fatalf("matching cell platform rejected: got=%#v err=%v", got, err)
	}
	for _, mutation := range []string{
		strings.Replace(valid, "linux/arm64", "linux/amd64", 1),
		strings.Replace(valid, "linux/arm64", "linux/aarch64", 1),
		strings.Replace(valid, `"PATH"`, `"HTTP_PROXY"`, 1),
		strings.Replace(valid, `"PATH",`, "", 1),
		strings.Replace(valid, `"request_initiated":true`, `"request_initiated":false`, 1),
		strings.Replace(valid, `"exit_code":0`, `"exit_code":124`, 1),
		strings.Replace(valid, `"exit_code":0`, `"exit_code":-1`, 1),
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
	if len(first) != 32 || len(second) != 32 || strings.Join(first, "\n") == strings.Join(second, "\n") {
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
	for _, key := range []string{"LAB_BIFROST_1_CLIENT_IPV4=", "LAB_BIFROST_1_DATA_IPV4=", "LAB_BIFROST_2_CLIENT_IPV4=", "LAB_BIFROST_2_DATA_IPV4=", "LAB_BIFROST_3_CLIENT_IPV4=", "LAB_BIFROST_3_DATA_IPV4=", "LAB_HEALTH_IPV4=", "LAB_MANTLE_IPV4=", "LAB_CONTRACT_IPV4="} {
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
	for _, name := range []string{"bifrost-1", "bifrost-2", "bifrost-3", "config-seed", "mantle-contract-service"} {
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
