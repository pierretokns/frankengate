package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	cellRoot      = "/cell"
	maxScenario   = 1 << 20
	maxSeedFile   = 1 << 20
	maxSeedFiles  = 64
	maxSeedTotal  = 8 << 20
	defaultMaxRun = 5 * time.Minute
)

const sealedFakeCredential = "sealed-lab-not-a-real-credential"

const codexBoundaryPrompt = "Reply with exactly deterministic mantle response. Do not use tools or execute commands. SEALED_CODEX_RUN_ID:"

var internalBaseURL = regexp.MustCompile(`^http://bifrost-[123]:8080/(?:openai/v1|anthropic)(?:/)?$`)
var exactOpenAIBaseURL = regexp.MustCompile(`^http://bifrost-[123]:8080/openai/v1$`)
var exactRunID = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,47}$`)
var observedSemver = regexp.MustCompile(`(?:^|[^0-9.])([0-9]+\.[0-9]+\.[0-9]+)(?:[^0-9.]|$)`)

type scenario struct {
	Schema          string            `json:"schema"`
	Operation       string            `json:"operation,omitempty"`
	RunID           string            `json:"run_id"`
	Client          string            `json:"client"`
	Binary          string            `json:"binary"`
	Args            []string          `json:"args"`
	Env             map[string]string `json:"env"`
	ExpectedVersion string            `json:"expected_version"`
	TimeoutMS       int               `json:"timeout_ms"`
}

type seedManifest struct {
	Schema string     `json:"schema"`
	Files  []seedFile `json:"files"`
}

type seedFile struct {
	Source string `json:"source"`
	Target string `json:"target"`
	SHA256 string `json:"sha256"`
}

type evidence struct {
	Schema           string   `json:"schema"`
	RunID            string   `json:"run_id"`
	Client           string   `json:"client"`
	ExitCode         int      `json:"exit_code"`
	Environment      []string `json:"environment_names"`
	ResidueCount     int      `json:"residue_count"`
	ClientVersion    string   `json:"client_version"`
	NativePlatform   string   `json:"native_platform"`
	Operation        string   `json:"operation,omitempty"`
	ProcessStarted   bool     `json:"process_started,omitempty"`
	RequestInitiated bool     `json:"request_initiated,omitempty"`
	TransportOutcome string   `json:"transport_outcome,omitempty"`
	EventCount       int      `json:"jsonl_event_count,omitempty"`
	OutputBytes      int      `json:"inference_output_bytes,omitempty"`
	OutputSHA256     string   `json:"inference_output_sha256,omitempty"`
	OutputTruncated  bool     `json:"inference_output_truncated,omitempty"`
	GatewayBaseURL   string   `json:"gateway_base_url,omitempty"`
}

type commandSpec struct {
	Binary string
	Args   []string
}

type commandResult struct {
	Stdout          []byte
	Stderr          []byte
	StdoutTruncated bool
	StderrTruncated bool
	ExitCode        int
}

type boundedCapture struct {
	mu        sync.Mutex
	data      []byte
	remaining int
	truncated bool
}

func newBoundedCapture(limit int) *boundedCapture { return &boundedCapture{remaining: limit} }

func (capture *boundedCapture) Write(data []byte) (int, error) {
	capture.mu.Lock()
	defer capture.mu.Unlock()
	if capture.remaining > 0 {
		keep := len(data)
		if keep > capture.remaining {
			keep = capture.remaining
		}
		capture.data = append(capture.data, data[:keep]...)
		capture.remaining -= keep
		if keep < len(data) {
			capture.truncated = true
		}
	} else if len(data) > 0 {
		capture.truncated = true
	}
	return len(data), nil
}

func (capture *boundedCapture) Truncated() bool {
	capture.mu.Lock()
	defer capture.mu.Unlock()
	return capture.truncated
}

func (capture *boundedCapture) Contains(value string) bool {
	capture.mu.Lock()
	defer capture.mu.Unlock()
	return bytes.Contains(capture.data, []byte(value))
}

func (capture *boundedCapture) Bytes() []byte {
	capture.mu.Lock()
	defer capture.mu.Unlock()
	return append([]byte(nil), capture.data...)
}

func main() {
	runID := os.Getenv("LAB_RUN_ID")
	os.Clearenv()
	if err := run(runID); err != nil {
		fmt.Fprintln(os.Stderr, "cell-init:", err)
		os.Exit(1)
	}
}

func run(lifecycleRunID string) error {
	path := "/scenario/scenario.json"
	data, err := os.ReadFile(path)
	if err != nil || len(data) > maxScenario {
		return errors.New("invalid scenario input")
	}
	if err := rejectDuplicateJSONKeys(data); err != nil {
		return err
	}
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	var cfg scenario
	if err := decoder.Decode(&cfg); err != nil {
		return fmt.Errorf("decode scenario: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("scenario contains trailing JSON")
	}
	if !exactRunID.MatchString(lifecycleRunID) {
		return errors.New("missing or invalid lifecycle run identity")
	}
	cfg.RunID = lifecycleRunID
	if err := validateScenario(cfg); err != nil {
		return err
	}
	if err := prepareCell(cfg.Client); err != nil {
		return err
	}
	defer clearCell()

	environment := baseEnvironment()
	for key, value := range cfg.Env {
		environment = append(environment, key+"="+value)
	}
	sort.Strings(environment)
	timeout := defaultMaxRun
	if cfg.TimeoutMS > 0 {
		timeout = time.Duration(cfg.TimeoutMS) * time.Millisecond
	}
	versionSpec := commandSpec{Binary: cfg.Binary, Args: []string{"--version"}}
	versionResult, err := execute(versionSpec, environment, timeout)
	if err != nil {
		return err
	}
	if versionResult.ExitCode != 0 {
		return fmt.Errorf("client version command exited %d", versionResult.ExitCode)
	}
	if versionResult.StdoutTruncated || versionResult.StderrTruncated {
		return errors.New("client version output exceeds capture bound")
	}
	versionOutput := append(append([]byte(nil), versionResult.Stdout...), versionResult.Stderr...)
	version, err := parseObservedVersion(versionOutput)
	if err != nil || version != cfg.ExpectedVersion {
		return fmt.Errorf("client version output %q does not exactly match pinned version %q", version, cfg.ExpectedVersion)
	}

	operation := cfg.Operation
	if operation == "" {
		operation = "version"
	}
	exitCode := versionResult.ExitCode
	var inferenceOutput []byte
	outputTruncated := false
	processStarted := false
	requestInitiated := false
	transportOutcome := ""
	eventCount := 0
	if operation == "codex-inference-boundary" {
		spec := codexInferenceCommand(cfg.Binary, cfg.RunID)
		var inferenceResult commandResult
		inferenceResult, err = execute(spec, environment, timeout)
		if err != nil {
			return err
		}
		processStarted = true
		inferenceOutput = inferenceResult.Stdout
		outputTruncated = inferenceResult.StdoutTruncated
		exitCode = inferenceResult.ExitCode
		if inferenceResult.StderrTruncated {
			return errors.New("Codex inference stderr exceeds capture bound")
		}
		transportOutcome, eventCount, err = validateCodexJSONL(inferenceOutput, exitCode)
		if err != nil {
			return fmt.Errorf("Codex inference JSONL: %w", err)
		}
		requestInitiated = true
	}
	if err := clearCell(); err != nil {
		return err
	}
	residue := countEntries(cellRoot)
	names := make([]string, 0, len(environment))
	for _, item := range environment {
		names = append(names, strings.SplitN(item, "=", 2)[0])
	}
	resultSchema := "sealed-cli-cell-evidence/v1"
	evidenceOperation := ""
	if cfg.Schema == "sealed-cli-cell-scenario/v2" {
		resultSchema = "sealed-cli-cell-evidence/v2"
		evidenceOperation = operation
	}
	result := evidence{
		Schema: resultSchema, RunID: cfg.RunID, Client: cfg.Client,
		ExitCode: exitCode, Environment: names, ResidueCount: residue, ClientVersion: version,
		NativePlatform: runtime.GOOS + "/" + runtime.GOARCH, Operation: evidenceOperation,
		ProcessStarted: processStarted, RequestInitiated: requestInitiated,
	}
	if processStarted {
		result.OutputBytes, result.OutputSHA256, result.OutputTruncated = summarizeInferenceOutput(inferenceOutput, outputTruncated)
		result.GatewayBaseURL = cfg.Env["OPENAI_BASE_URL"]
		result.TransportOutcome = transportOutcome
		result.EventCount = eventCount
	}
	return json.NewEncoder(os.Stdout).Encode(result)
}

func summarizeInferenceOutput(output []byte, truncated bool) (int, string, bool) {
	digest := sha256.Sum256(output)
	return len(output), hex.EncodeToString(digest[:]), truncated
}

func codexInferenceCommand(binary, runID string) commandSpec {
	return commandSpec{Binary: binary, Args: []string{
		"exec", "--strict-config", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only",
		"--color", "never", "--json", codexBoundaryPrompt + runID,
	}}
}

func execute(spec commandSpec, environment []string, timeout time.Duration) (commandResult, error) {
	command := exec.Command(spec.Binary, spec.Args...)
	command.Env = environment
	command.Dir = filepath.Join(cellRoot, "home")
	stdout := newBoundedCapture(1 << 20)
	stderr := newBoundedCapture(1 << 20)
	command.Stdout = io.MultiWriter(os.Stderr, stdout)
	command.Stderr = io.MultiWriter(os.Stderr, stderr)
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := command.Start(); err != nil {
		return commandResult{}, err
	}
	done := make(chan error, 1)
	go func() { done <- command.Wait() }()
	exitCode := 0
	select {
	case waitErr := <-done:
		if waitErr != nil {
			var exitErr *exec.ExitError
			if errors.As(waitErr, &exitErr) {
				exitCode = exitErr.ExitCode()
			} else {
				return commandResult{}, waitErr
			}
		}
	case <-time.After(timeout):
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGTERM)
		time.Sleep(2 * time.Second)
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGKILL)
		<-done
		exitCode = 124
	}
	return commandResult{Stdout: stdout.Bytes(), Stderr: stderr.Bytes(), StdoutTruncated: stdout.Truncated(), StderrTruncated: stderr.Truncated(), ExitCode: exitCode}, nil
}

func validateCodexJSONL(data []byte, exitCode int) (string, int, error) {
	if len(data) == 0 || len(data) > 1<<20 || exitCode < 0 || exitCode == 124 {
		return "", 0, errors.New("missing, oversized, or timed-out Codex event stream")
	}
	scanner := bufio.NewScanner(bytes.NewReader(data))
	scanner.Buffer(make([]byte, 4096), 1<<20)
	types := make([]string, 0, 16)
	completedHasUsage := false
	failedHasError := false
	terminalCount := 0
	responseMarkerSeen := false
	allowedTypes := map[string]bool{
		"thread.started": true, "turn.started": true, "turn.completed": true, "turn.failed": true,
		"item.started": true, "item.updated": true, "item.completed": true, "error": true,
	}
	for scanner.Scan() {
		line := bytes.TrimSpace(scanner.Bytes())
		if len(line) == 0 {
			continue
		}
		if err := rejectDuplicateJSONKeys(line); err != nil {
			return "", 0, fmt.Errorf("invalid event JSON: %w", err)
		}
		var event map[string]json.RawMessage
		if err := json.Unmarshal(line, &event); err != nil {
			return "", 0, fmt.Errorf("invalid event JSON: %w", err)
		}
		var eventType string
		if err := json.Unmarshal(event["type"], &eventType); err != nil || eventType == "" {
			return "", 0, errors.New("event is missing a string type")
		}
		if !allowedTypes[eventType] {
			return "", 0, fmt.Errorf("unsupported Codex event type %q", eventType)
		}
		if len(types) == 0 {
			var threadID string
			if eventType != "thread.started" || json.Unmarshal(event["thread_id"], &threadID) != nil || threadID == "" {
				return "", 0, errors.New("first event is not a bound thread.started")
			}
		} else if len(types) == 1 && eventType != "turn.started" {
			return "", 0, errors.New("second event is not turn.started")
		}
		if eventType == "turn.completed" {
			terminalCount++
			var usage map[string]json.RawMessage
			if json.Unmarshal(event["usage"], &usage) == nil && len(usage) > 0 {
				var inputTokens, outputTokens int64
				if json.Unmarshal(usage["input_tokens"], &inputTokens) == nil && json.Unmarshal(usage["output_tokens"], &outputTokens) == nil && inputTokens >= 0 && outputTokens >= 0 {
					completedHasUsage = true
				}
			}
		}
		if eventType == "turn.failed" {
			terminalCount++
			var failure struct {
				Message string `json:"message"`
			}
			if json.Unmarshal(event["error"], &failure) == nil && failure.Message != "" {
				failedHasError = true
			}
		}
		if eventType == "item.completed" {
			var item struct {
				Type string `json:"type"`
				Text string `json:"text"`
			}
			if json.Unmarshal(event["item"], &item) == nil && item.Type == "agent_message" && item.Text == "deterministic mantle response" {
				responseMarkerSeen = true
			}
		}
		types = append(types, eventType)
		if len(types) > 4096 {
			return "", 0, errors.New("event stream exceeds event-count bound")
		}
	}
	if err := scanner.Err(); err != nil {
		return "", 0, err
	}
	if len(types) < 3 || types[0] != "thread.started" || types[1] != "turn.started" || terminalCount != 1 {
		return "", 0, errors.New("event stream does not prove turn initiation")
	}
	terminal := types[len(types)-1]
	if exitCode == 0 {
		if terminal != "turn.completed" || !completedHasUsage || !responseMarkerSeen {
			return "", 0, errors.New("successful process lacks terminal turn.completed usage")
		}
		return "completed", len(types), nil
	}
	if terminal != "turn.failed" || !failedHasError {
		return "", 0, errors.New("failed process lacks terminal turn.failed")
	}
	return "transport_failure_after_turn_start", len(types), nil
}

func parseObservedVersion(output []byte) (string, error) {
	matches := observedSemver.FindAllSubmatch(output, -1)
	if len(matches) != 1 {
		return "", fmt.Errorf("version output must contain exactly one semantic version")
	}
	return string(matches[0][1]), nil
}

func validateScenario(cfg scenario) error {
	if (cfg.Schema != "sealed-cli-cell-scenario/v1" && cfg.Schema != "sealed-cli-cell-scenario/v2") || cfg.RunID == "" || (cfg.Client != "codex" && cfg.Client != "claude") {
		return errors.New("invalid scenario identity")
	}
	wantBinary := map[string]string{"codex": "/opt/client/bin/codex", "claude": "/opt/client/bin/claude"}[cfg.Client]
	if cfg.Binary != wantBinary || !exactSemver(cfg.ExpectedVersion) || cfg.TimeoutMS < 0 || cfg.TimeoutMS > int((15*time.Minute)/time.Millisecond) {
		return errors.New("invalid scenario process contract")
	}
	if cfg.Schema == "sealed-cli-cell-scenario/v1" {
		if cfg.Operation != "" || len(cfg.Args) != 1 || cfg.Args[0] != "--version" {
			return errors.New("v1 scenarios are limited to the version operation")
		}
	} else if cfg.Operation != "codex-inference-boundary" || cfg.Client != "codex" || len(cfg.Args) != 0 {
		return errors.New("v2 scenarios are limited to the fixed Codex inference-boundary operation")
	}
	for _, arg := range cfg.Args {
		if len(arg) > 1<<16 || strings.IndexByte(arg, 0) >= 0 {
			return errors.New("invalid argument")
		}
	}
	for key, value := range cfg.Env {
		if err := validateScenarioEnvironment(key, value); err != nil {
			return fmt.Errorf("scenario environment key %q is not allowed", key)
		}
	}
	if cfg.Schema == "sealed-cli-cell-scenario/v2" {
		if len(cfg.Env) != 2 || cfg.Env["OPENAI_API_KEY"] != sealedFakeCredential || !exactOpenAIBaseURL.MatchString(cfg.Env["OPENAI_BASE_URL"]) {
			return errors.New("Codex inference-boundary scenarios require only the sealed credential and internal OpenAI gateway")
		}
	}
	return nil
}

func exactSemver(value string) bool {
	if value == "" || len(value) > 128 {
		return false
	}
	parts := strings.Split(value, ".")
	if len(parts) != 3 {
		return false
	}
	for _, part := range parts {
		if part == "" {
			return false
		}
		for _, character := range part {
			if character < '0' || character > '9' {
				return false
			}
		}
	}
	return true
}

func validateScenarioEnvironment(key, value string) error {
	if len(value) > 1<<16 || strings.IndexByte(value, 0) >= 0 {
		return errors.New("invalid environment value")
	}
	switch key {
	case "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN":
		if value != sealedFakeCredential {
			return errors.New("only the sealed fake credential is allowed")
		}
	case "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL":
		if !internalBaseURL.MatchString(value) {
			return errors.New("base URL must target an internal gateway service")
		}
	case "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_AUTOUPDATER", "DISABLE_ERROR_REPORTING", "DISABLE_TELEMETRY":
		if value != "1" {
			return errors.New("safety switches must be enabled")
		}
	default:
		return errors.New("unknown environment key")
	}
	return nil
}

func baseEnvironment() []string {
	return []string{
		"CODEX_HOME=/cell/codex", "HOME=/cell/home", "LANG=C.UTF-8", "PATH=/opt/client/bin:/usr/local/bin:/usr/bin:/bin",
		"TMPDIR=/cell/tmp", "TZ=UTC", "XDG_CACHE_HOME=/cell/xdg-cache", "XDG_CONFIG_HOME=/cell/xdg-config", "XDG_DATA_HOME=/cell/xdg-data",
	}
}

func prepareCell(client string) error {
	if err := clearCell(); err != nil {
		return err
	}
	for _, directory := range []string{"home", "codex", "tmp", "xdg-cache", "xdg-config", "xdg-data"} {
		if err := os.MkdirAll(filepath.Join(cellRoot, directory), 0o700); err != nil {
			return err
		}
	}
	manifestPath := filepath.Join("/opt/seed", client, "manifest.json")
	data, err := os.ReadFile(manifestPath)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	var manifest seedManifest
	if err := rejectDuplicateJSONKeys(data); err != nil {
		return err
	}
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&manifest); err != nil || manifest.Schema != "sealed-cli-seed/v1" {
		return errors.New("invalid seed manifest")
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("seed manifest contains trailing JSON")
	}
	if len(manifest.Files) > maxSeedFiles {
		return errors.New("seed manifest contains too many files")
	}
	seenSources := make(map[string]struct{}, len(manifest.Files))
	seenTargets := make(map[string]struct{}, len(manifest.Files))
	totalSize := int64(0)
	for _, file := range manifest.Files {
		if _, exists := seenSources[file.Source]; exists {
			return errors.New("seed manifest contains a duplicate source")
		}
		if _, exists := seenTargets[file.Target]; exists {
			return errors.New("seed manifest contains a duplicate target")
		}
		seenSources[file.Source] = struct{}{}
		seenTargets[file.Target] = struct{}{}
		size, err := seedSourceSize(client, file.Source)
		if err != nil {
			return err
		}
		totalSize += size
		if totalSize > maxSeedTotal {
			return errors.New("seed manifest exceeds aggregate size limit")
		}
		if err := copySeed(client, file); err != nil {
			return err
		}
	}
	return nil
}

func seedSourceSize(client, sourcePath string) (int64, error) {
	if sourcePath == "" || filepath.IsAbs(sourcePath) || filepath.Clean(sourcePath) != sourcePath || strings.HasPrefix(sourcePath, "..") {
		return 0, errors.New("unsafe seed path")
	}
	info, err := os.Lstat(filepath.Join("/opt/seed", client, sourcePath))
	if err != nil || !info.Mode().IsRegular() || info.Size() > maxSeedFile {
		return 0, errors.New("invalid seed source")
	}
	return info.Size(), nil
}

func rejectDuplicateJSONKeys(data []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	var walk func() error
	walk = func() error {
		token, err := decoder.Token()
		if err != nil {
			return err
		}
		delim, ok := token.(json.Delim)
		if !ok {
			return nil
		}
		switch delim {
		case '{':
			seen := map[string]bool{}
			for decoder.More() {
				keyToken, err := decoder.Token()
				if err != nil {
					return err
				}
				key, ok := keyToken.(string)
				if !ok || seen[key] {
					return errors.New("duplicate or invalid JSON object key")
				}
				seen[key] = true
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		case '[':
			for decoder.More() {
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		default:
			return errors.New("unexpected JSON delimiter")
		}
	}
	if err := walk(); err != nil {
		return err
	}
	if _, err := decoder.Token(); err != io.EOF {
		return errors.New("trailing JSON")
	}
	return nil
}

func copySeed(client string, file seedFile) error {
	for _, path := range []string{file.Source, file.Target} {
		if path == "" || filepath.IsAbs(path) || filepath.Clean(path) != path || strings.HasPrefix(path, "..") {
			return errors.New("unsafe seed path")
		}
	}
	source := filepath.Join("/opt/seed", client, file.Source)
	info, err := os.Lstat(source)
	if err != nil || !info.Mode().IsRegular() || info.Size() > maxSeedFile {
		return errors.New("invalid seed source")
	}
	data, err := os.ReadFile(source)
	if err != nil {
		return err
	}
	digest := sha256.Sum256(data)
	if hex.EncodeToString(digest[:]) != file.SHA256 {
		return errors.New("seed digest mismatch")
	}
	target := filepath.Join(cellRoot, file.Target)
	if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
		return err
	}
	return os.WriteFile(target, data, 0o600)
}

func countEntries(root string) int {
	count := 0
	_ = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err == nil && info != nil && filepath.Clean(root) != filepath.Clean(path) {
			count++
		}
		return nil
	})
	return count
}

func clearCell() error {
	entries, err := os.ReadDir(cellRoot)
	if os.IsNotExist(err) {
		return os.MkdirAll(cellRoot, 0o700)
	}
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if err := os.RemoveAll(filepath.Join(cellRoot, entry.Name())); err != nil {
			return err
		}
	}
	return nil
}
