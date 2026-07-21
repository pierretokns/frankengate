package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"syscall"
	"time"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
	"github.com/maximhq/bifrost/tests/conformance/lab/mantleservice"
)

type commandExecutor interface {
	Run(env []string, stdout, stderr io.Writer, name string, args ...string) error
}
type diagnosticExecutor interface {
	RunDiagnostic(context.Context, []string, io.Writer, io.Writer, string, ...string) error
}

type osExecutor struct{}

type diagnosticsPaths struct{ Artifact, RunID, SourceLockSHA256, RuntimeLockSHA256, Phase string }

type diagnosticCapture struct {
	data      bytes.Buffer
	limit     int
	truncated bool
}

func (capture *diagnosticCapture) Write(data []byte) (int, error) {
	original := len(data)
	remaining := capture.limit - capture.data.Len()
	if remaining < len(data) {
		capture.truncated = true
		if remaining < 0 {
			remaining = 0
		}
		data = data[:remaining]
	}
	_, _ = capture.data.Write(data)
	return original, nil
}

func (paths diagnosticsPaths) validate() error {
	if paths.Artifact != "" && !filepath.IsAbs(paths.Artifact) {
		return errors.New("failure diagnostic artifact path must be absolute")
	}
	if paths.Artifact != "" && paths.Phase != "" && (paths.RunID == "" || !regexp.MustCompile(`^[0-9a-f]{64}$`).MatchString(paths.SourceLockSHA256) || !regexp.MustCompile(`^[0-9a-f]{64}$`).MatchString(paths.RuntimeLockSHA256) || (paths.Phase != "failure-teardown" && paths.Phase != "pre-success-teardown")) {
		return errors.New("failure diagnostic artifact lacks lifecycle bindings")
	}
	return nil
}

func writeComposeDiagnostics(executor commandExecutor, environment []string, dockerBinary string, compose []string, paths diagnosticsPaths) error {
	if err := paths.validate(); err != nil {
		return err
	}
	if paths.Artifact != "" && paths.Phase == "" {
		return errors.New("failure diagnostic artifact lacks lifecycle phase")
	}
	if paths.Artifact == "" {
		return nil
	}
	dir := filepath.Dir(paths.Artifact)
	info, err := os.Lstat(dir)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return errors.New("diagnostic directory must be real")
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		item, err := os.Lstat(filepath.Join(dir, entry.Name()))
		if err != nil {
			return err
		}
		stat, ok := item.Sys().(*syscall.Stat_t)
		if !item.Mode().IsRegular() || item.Mode()&os.ModeSymlink != 0 || !ok || stat.Nlink != 1 {
			return fmt.Errorf("unsafe diagnostic directory entry %s", entry.Name())
		}
	}
	if _, err := os.Lstat(paths.Artifact); !errors.Is(err, os.ErrNotExist) {
		return errors.New("diagnostic artifact must be fresh")
	}
	type row struct {
		Service      string `json:"service"`
		State        string `json:"state"`
		Health       string `json:"health"`
		OOM          string `json:"oom"`
		OOMSource    string `json:"oom_source"`
		LogSHA256    string `json:"log_sha256,omitempty"`
		LogContent   string `json:"log_content"`
		ErrorClass   string `json:"error_class"`
		FailureClass string `json:"failure_class"`
		ExitCode     int    `json:"exit_code"`
		LogBytes     int    `json:"log_bytes"`
	}
	result := struct {
		Schema            string `json:"schema"`
		RunID             string `json:"run_id"`
		SourceLockSHA256  string `json:"source_lock_sha256"`
		RuntimeLockSHA256 string `json:"runtime_lock_sha256"`
		CapturedAt        string `json:"captured_at"`
		Phase             string `json:"phase"`
		Nonce             string `json:"nonce"`
		Capture           string `json:"capture"`
		StatusCapture     string `json:"status_capture"`
		StatusRowCount    int    `json:"status_row_count"`
		MissingStatusRows int    `json:"missing_status_rows"`
		Services          []row  `json:"services"`
	}{Schema: "sealed-lab-failure-diagnostics/v1", RunID: paths.RunID, SourceLockSHA256: paths.SourceLockSHA256, RuntimeLockSHA256: paths.RuntimeLockSHA256, CapturedAt: time.Now().UTC().Format(time.RFC3339Nano), Phase: paths.Phase, Capture: "metadata-only", StatusCapture: "ok"}
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return err
	}
	result.Nonce = hex.EncodeToString(nonce)
	services := []string{"postgres", "config-seed", "mantle-contract-service", "bifrost-1", "bifrost-2", "bifrost-3", "controlled-dns", "egress-sentinel", "codex-runner"}
	knownServices := map[string]bool{}
	for _, service := range []string{"postgres", "config-seed", "mantle-contract-service", "bifrost-1", "bifrost-2", "bifrost-3", "netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "netns-codex", "netns-claude", "health-stub", "contract-stub", "controlled-dns", "egress-sentinel", "codex-runner", "claude-runner", "network-probe"} {
		knownServices[service] = true
	}
	diagnosticServices := map[string]bool{}
	for _, service := range services {
		diagnosticServices[service] = true
	}
	aggregate, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	type psRow struct {
		ID       string `json:"ID"`
		Service  string `json:"Service"`
		State    string `json:"State"`
		Health   string `json:"Health"`
		ExitCode int    `json:"ExitCode"`
	}
	status := map[string]psRow{}
	psCtx, psStop := context.WithTimeout(aggregate, 5*time.Second)
	defer psStop()
	psCapture := &diagnosticCapture{limit: 256 << 10}
	psArgs := append(compose, "ps", "--all", "--format", "json")
	var psErr error
	if specialized, ok := executor.(diagnosticExecutor); ok {
		psErr = specialized.RunDiagnostic(psCtx, environment, psCapture, psCapture, dockerBinary, psArgs...)
	} else {
		return errors.New("diagnostic executor lacks context support")
	}
	psStop()
	if psCapture.truncated {
		result.StatusCapture = "oversize"
	} else if errors.Is(psErr, context.DeadlineExceeded) {
		result.StatusCapture = "timeout"
	} else if psErr != nil {
		result.StatusCapture = "command-error"
	} else {
		var rows []psRow
		if json.Unmarshal(psCapture.data.Bytes(), &rows) == nil {
			malformed := false
			seen := map[string]bool{}
			for _, item := range rows {
				if !knownServices[item.Service] || seen[item.Service] {
					malformed = true
					continue
				}
				seen[item.Service] = true
				if !regexp.MustCompile(`^[a-f0-9]{12,64}$`).MatchString(item.ID) || !regexp.MustCompile(`^[A-Za-z0-9_-]{1,32}$`).MatchString(item.State) {
					malformed = true
				}
				if diagnosticServices[item.Service] {
					status[item.Service] = item
				}
			}
			if malformed {
				result.StatusCapture = "malformed"
			}
		} else {
			result.StatusCapture = "malformed"
		}
	}
	result.StatusRowCount = len(status)
	for _, service := range services {
		ctx, stop := context.WithTimeout(aggregate, 5*time.Second)
		capture := &diagnosticCapture{limit: 256 << 10}
		args := append(compose, "logs", "--tail", "200", "--no-color", "--no-log-prefix", service)
		var commandErr error
		if specialized, ok := executor.(diagnosticExecutor); ok {
			commandErr = specialized.RunDiagnostic(ctx, environment, capture, capture, dockerBinary, args...)
		} else {
			stop()
			return errors.New("diagnostic executor lacks context support")
		}
		stop()
		state, health, oom, oomSource, errorClass, failureClass, exitCode := "unknown", "unknown", "unsupported", "unsupported", "none", "none", -1
		if item, ok := status[service]; ok {
			if regexp.MustCompile(`^[A-Za-z0-9_-]{1,32}$`).MatchString(item.State) {
				state = item.State
			}
			if regexp.MustCompile(`^[A-Za-z0-9_-]{1,32}$`).MatchString(item.Health) {
				health = item.Health
			}
			exitCode = item.ExitCode
			if regexp.MustCompile(`^[a-f0-9]{12,64}$`).MatchString(item.ID) {
				oomSource = "docker-inspect"
				inspectCtx, inspectStop := context.WithTimeout(aggregate, 5*time.Second)
				inspectCapture := &diagnosticCapture{limit: 32}
				inspectErr := executor.(diagnosticExecutor).RunDiagnostic(inspectCtx, environment, inspectCapture, inspectCapture, dockerBinary, "inspect", "--format", "{{json .State.OOMKilled}}", item.ID)
				inspectStop()
				if inspectErr == nil {
					switch strings.TrimSpace(inspectCapture.data.String()) {
					case "true":
						oom = "true"
					case "false":
						oom = "false"
					}
				}
			}
		}
		failed := serviceStatusFailed(state, health, exitCode)
		failureClass = classifySanitizedFailure(capture.data.Bytes(), failed)
		if _, ok := status[service]; !ok {
			failureClass = "missing-status-row"
			result.MissingStatusRows++
		}
		if commandErr != nil {
			state = "diagnostic-error"
			errorClass = "command-error"
			if errors.Is(commandErr, context.DeadlineExceeded) {
				errorClass = "timeout"
			}
		}
		digest := ""
		if !capture.truncated {
			sum := sha256.Sum256(capture.data.Bytes())
			digest = hex.EncodeToString(sum[:])
		}
		if capture.truncated {
			errorClass = "oversize"
		}
		result.Services = append(result.Services, row{Service: service, State: state, Health: health, OOM: oom, OOMSource: oomSource, ErrorClass: errorClass, FailureClass: failureClass, ExitCode: exitCode, LogBytes: capture.data.Len(), LogSHA256: digest, LogContent: "omitted-metadata-only"})
	}
	encoded, err := json.Marshal(result)
	if err != nil || len(encoded) > 1<<20 {
		return errors.New("structured diagnostics exceed bound")
	}
	temp, err := os.CreateTemp(dir, ".failure-diagnostics-*")
	if err != nil {
		return err
	}
	tempName := temp.Name()
	defer os.Remove(tempName)
	if err := temp.Chmod(0o600); err != nil {
		temp.Close()
		return err
	}
	if _, err := temp.Write(append(encoded, '\n')); err != nil {
		temp.Close()
		return err
	}
	if err := temp.Sync(); err != nil {
		temp.Close()
		return err
	}
	if err := temp.Close(); err != nil {
		return err
	}
	if err := os.Link(tempName, paths.Artifact); err != nil {
		return fmt.Errorf("publish fresh diagnostics: %w", err)
	}
	return nil
}

func classifySanitizedFailure(data []byte, failed bool) string {
	s := strings.ToLower(string(data))
	patterns := []struct {
		class string
		terms []string
	}{
		{"config-parse", []string{"invalid config", "config parse", "decode config", "unmarshal config"}},
		{"sqlite-cgo-disabled", []string{"sqlite", "cgo_enabled=0", "cgo disabled", "requires cgo"}},
		{"postgres-auth", []string{"password authentication failed", "authentication failed for user", "sqlstate 28p01"}},
		{"postgres-connect", []string{"connection refused", "could not connect to postgres", "dial tcp", "sqlstate 08001"}},
	}
	for _, pattern := range patterns {
		for _, term := range pattern.terms {
			if strings.Contains(s, term) {
				return pattern.class
			}
		}
	}
	if failed && strings.TrimSpace(s) != "" {
		return "generic-startup"
	}
	return "none"
}

func serviceStatusFailed(state, health string, exitCode int) bool {
	return exitCode > 0 || state == "dead" || state == "restarting" || health == "unhealthy"
}

type seedRecord struct {
	Schema   string `json:"schema"`
	Revision string `json:"revision"`
	Provider string `json:"provider"`
	Alias    string `json:"alias"`
	Model    string `json:"model"`
	TLS      string `json:"tls"`
}

func parseSeedRecord(data []byte) (seedRecord, error) {
	var record seedRecord
	if len(data) == 0 || len(data) > 4096 {
		return record, errors.New("config seed output exceeds exact record bound")
	}
	for _, key := range []string{"schema", "revision", "provider", "alias", "model", "tls"} {
		if bytes.Count(data, []byte(`"`+key+`"`)) != 1 {
			return record, errors.New("config seed record has missing or duplicate fields")
		}
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&record); err != nil {
		return record, fmt.Errorf("decode config seed record: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return record, errors.New("config seed output must contain exactly one JSON record")
	}
	if record != (seedRecord{Schema: "sealed-lab-config-seed/v1", Revision: "sealed-lab-c9-gpt55-v1", Provider: "bedrock_mantle", Alias: "gpt-5.5", Model: "openai.gpt-5.5", TLS: "private-ca-verified"}) {
		return record, errors.New("config seed record contract mismatch")
	}
	return record, nil
}

func (osExecutor) Run(env []string, stdout, stderr io.Writer, name string, args ...string) error {
	command := exec.Command(name, args...)
	command.Env = env
	command.Stdout = stdout
	command.Stderr = stderr
	return command.Run()
}
func (osExecutor) RunDiagnostic(ctx context.Context, env []string, stdout, stderr io.Writer, name string, args ...string) error {
	command := exec.CommandContext(ctx, name, args...)
	command.Env = env
	command.Stdout = stdout
	command.Stderr = stderr
	return command.Run()
}

type cellResult struct {
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

type lifecycleResult struct {
	Schema                         string      `json:"schema"`
	RunID                          string      `json:"run_id"`
	NativePlatform                 string      `json:"native_platform"`
	StartedAt                      string      `json:"started_at"`
	CompletedAt                    string      `json:"completed_at"`
	SourceLockSHA256               string      `json:"source_lock_sha256"`
	RuntimeLockSHA256              string      `json:"runtime_lock_sha256"`
	SeedConfigRevision             string      `json:"seed_config_revision"`
	Clients                        []string    `json:"clients"`
	NormalCellForbiddenEvents      int         `json:"normal_cell_forbidden_events"`
	AdversarialProbeRecordedEvents int         `json:"adversarial_probe_recorded_events"`
	PaidInferenceProof             string      `json:"paid_inference_proof"`
	TeardownClean                  bool        `json:"teardown_clean"`
	CodexInferenceBoundary         *cellResult `json:"codex_inference_boundary,omitempty"`
}

type networkProbeResult struct {
	Schema             string `json:"schema"`
	KnownDNS           int    `json:"known_dns"`
	UnknownDNSBlocked  int    `json:"unknown_dns_blocked"`
	KnownHostTrapped   int    `json:"known_host_trapped"`
	DirectIPv4Blocked  int    `json:"direct_ipv4_blocked"`
	DirectIPv6Blocked  int    `json:"direct_ipv6_blocked"`
	QUICBlocked        int    `json:"quic_blocked"`
	ProxyBypassBlocked int    `json:"proxy_bypass_blocked"`
}

func main() {
	var lockPath, sourceLockPath, composePath, dockerBinary, recorderPolicyPath string
	var diagnostics diagnosticsPaths
	var recorderEvidence recorderEvidencePaths
	flag.StringVar(&lockPath, "runtime-lock", "", "path to sealed-lab-runtime-lock/v1 or v2")
	flag.StringVar(&sourceLockPath, "source-lock", "", "path to committed sealed-lab-image-lock/v1")
	flag.StringVar(&composePath, "compose", "compose.yaml", "sealed lab Compose file")
	flag.StringVar(&dockerBinary, "docker", "docker", "reviewed Docker CLI path")
	flag.StringVar(&recorderPolicyPath, "recorder-policy", "", "absolute path to compiled recorder policy required by runtime-lock/v2")
	flag.StringVar(&recorderEvidence.Expectations, "recorder-expectations", "", "absolute path to trusted recorder invocation expectations")
	flag.StringVar(&recorderEvidence.Transcript, "recorder-transcript", "", "absolute path to recorder control JSONL")
	flag.StringVar(&recorderEvidence.PCAPNG, "recorder-pcapng", "", "absolute path to recorder PCAPNG evidence")
	flag.StringVar(&recorderEvidence.Ledger, "recorder-ledger", "", "absolute path to recorder canonical JSONL ledger")
	flag.StringVar(&diagnostics.Artifact, "failure-diagnostics-artifact", "", "absolute fresh file for structured pre-teardown diagnostics")
	flag.Parse()
	if err := run(osExecutor{}, lockPath, sourceLockPath, composePath, dockerBinary, recorderPolicyPath, recorderEvidence, diagnostics, os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "lab-runner:", err)
		os.Exit(1)
	}
}

func run(executor commandExecutor, lockPath, sourceLockPath, composePath, dockerBinary, recorderPolicyPath string, recorderEvidence recorderEvidencePaths, diagnostics diagnosticsPaths, stdout, stderr io.Writer) error {
	startedAt := time.Now().UTC()
	if lockPath == "" || !filepath.IsAbs(lockPath) || !filepath.IsAbs(sourceLockPath) || !filepath.IsAbs(composePath) || !filepath.IsAbs(dockerBinary) {
		return errors.New("runtime lock, source lock, Compose file, and Docker binary must be absolute paths")
	}
	if err := diagnostics.validate(); err != nil {
		return err
	}
	lockData, err := os.ReadFile(lockPath)
	if err != nil {
		return err
	}
	lock, err := contract.DecodeRuntimeLock(bytes.NewReader(lockData))
	if err != nil {
		return fmt.Errorf("runtime lock: %w", err)
	}
	if lock.IsRecorderCapable() && (recorderPolicyPath == "" || !filepath.IsAbs(recorderPolicyPath)) {
		return errors.New("runtime-lock/v2 requires an absolute recorder policy path")
	}
	if !lock.IsRecorderCapable() && recorderPolicyPath != "" {
		return errors.New("recorder policy is forbidden for runtime-lock/v1 smoke runs")
	}
	if err := recorderEvidence.validate(lock.IsRecorderCapable()); err != nil {
		return err
	}
	sourceData, err := os.ReadFile(sourceLockPath)
	if err != nil {
		return err
	}
	sourceLock, err := contract.DecodeLock(bytes.NewReader(sourceData))
	if err != nil {
		return fmt.Errorf("source lock: %w", err)
	}
	if contract.SHA256Hex(sourceData) != lock.SourceLockSHA256 {
		return errors.New("runtime lock does not bind the committed source lock")
	}
	if diagnostics.Artifact != "" {
		diagnostics.RunID = lock.RunID
		diagnostics.SourceLockSHA256 = contract.SHA256Hex(sourceData)
		diagnostics.RuntimeLockSHA256 = contract.SHA256Hex(lockData)
		diagnostics.Phase = "failure-teardown"
	}
	if err := validatePinnedClientVersions(*lock, *sourceLock); err != nil {
		return err
	}
	composeData, err := os.ReadFile(composePath)
	if err != nil {
		return err
	}
	if err := contract.ValidateComposeAgainstLock(composeData, *sourceLock); err != nil {
		return fmt.Errorf("compose contract: %w", err)
	}
	environment := exactEnvironment(lock.ComposeEnvironment(), os.Getenv)
	environment = append(environment, networkEnvironment(lock.RunID)...)
	sort.Strings(environment)
	var platformOutput bytes.Buffer
	if err := executor.Run(environment, &platformOutput, stderr, dockerBinary, "info", "--format", "{{.OSType}}/{{.Architecture}}"); err != nil {
		return fmt.Errorf("inspect native Docker platform: %w", err)
	}
	nativePlatform, err := validateNativePlatform(platformOutput.String())
	if err != nil {
		return err
	}
	for _, image := range lock.Images {
		var raw bytes.Buffer
		if err := executor.Run(environment, &raw, stderr, dockerBinary, "buildx", "imagetools", "inspect", "--raw", image.Reference); err != nil {
			return fmt.Errorf("inspect runtime image %s: %w", image.ID, err)
		}
		if err := validateOCIIndex(raw.Bytes()); err != nil {
			return fmt.Errorf("runtime image %s: %w", image.ID, err)
		}
	}
	if lock.IsRecorderCapable() {
		if err := verifyPinnedRecorderArtifacts(executor, environment, stderr, dockerBinary, recorderPolicyPath, nativePlatform, *lock); err != nil {
			return err
		}
	}
	projectName := "fg-lab-" + lock.RunID
	compose := []string{"compose", "--project-name", projectName, "--file", composePath, "--profile", "clients"}
	var resolvedCompose bytes.Buffer
	if err := executor.Run(environment, &resolvedCompose, stderr, dockerBinary, append(compose, "config", "--format", "json")...); err != nil {
		return fmt.Errorf("resolved Compose validation: %w", err)
	}
	if err := contract.ValidateResolvedCompose(resolvedCompose.Bytes(), *sourceLock, *lock); err != nil {
		return fmt.Errorf("resolved Compose contract: %w", err)
	}
	coreServices := []string{
		"postgres", "config-seed", "mantle-contract-service", "netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "bifrost-1", "bifrost-2", "bifrost-3",
		"health-stub", "contract-stub", "controlled-dns", "egress-sentinel", "netns-codex", "netns-claude",
	}
	teardownClean := false
	tornDown := false
	diagnosticsCaptured := false
	var diagnosticsErr error
	captureDiagnostics := func() {
		if diagnosticsCaptured {
			return
		}
		diagnosticsCaptured = true
		if diagnosticsErr = writeComposeDiagnostics(executor, environment, dockerBinary, compose, diagnostics); diagnosticsErr != nil {
			fmt.Fprintln(stderr, "lab-runner diagnostics:", diagnosticsErr)
		}
	}
	defer func() {
		if !tornDown {
			captureDiagnostics()
			_ = executor.Run(environment, io.Discard, stderr, dockerBinary, append(compose, "down", "--volumes", "--remove-orphans", "--timeout", "10")...)
		}
	}()
	upArgs := append(append([]string{}, compose...), "up", "--detach", "--wait")
	upArgs = append(upArgs, coreServices...)
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, upArgs...); err != nil {
		return fmt.Errorf("start sealed lab: %w", err)
	}
	var seedLogs bytes.Buffer
	if err := executor.Run(environment, &seedLogs, stderr, dockerBinary, append(compose, "logs", "--no-color", "--no-log-prefix", "config-seed")...); err != nil {
		return errors.New("config seed revision was not observed from completed seed service")
	}
	seedEvidence, err := parseSeedRecord(seedLogs.Bytes())
	if err != nil {
		return err
	}
	clients := []string{"claude", "codex"}
	cellPlatforms := make([]string, 0, len(clients))
	var codexBoundary *cellResult
	for _, client := range clients {
		var raw bytes.Buffer
		args := append(append([]string{}, compose...), "run", "--rm", "--no-deps", client+"-runner")
		if err := executor.Run(environment, &raw, stderr, dockerBinary, args...); err != nil {
			return fmt.Errorf("run %s cell: %w", client, err)
		}
		cellEvidence, err := validateCellResult(raw.Bytes(), lock.RunID, client, pinnedVersion(*lock, client), nativePlatform)
		if err != nil {
			return fmt.Errorf("%s cell evidence: %w", client, err)
		}
		cellPlatforms = append(cellPlatforms, cellEvidence.NativePlatform)
		if client == "codex" {
			copy := cellEvidence
			codexBoundary = &copy
		}
	}
	var mantleLogs bytes.Buffer
	if err := executor.Run(environment, &mantleLogs, stderr, dockerBinary, append(compose, "logs", "--no-color", "--no-log-prefix", "mantle-contract-service")...); err != nil {
		return fmt.Errorf("read Mantle contract transcript: %w", err)
	}
	if codexBoundary == nil {
		return fmt.Errorf("Codex boundary evidence is absent")
	}
	if err := validateMantleTranscript(mantleLogs.Bytes(), lock.RunID); err != nil {
		return fmt.Errorf("join Codex/Bifrost boundary to Mantle transcript: %w", err)
	}
	var sentinelLogs bytes.Buffer
	if err := executor.Run(environment, &sentinelLogs, stderr, dockerBinary, append(compose, "logs", "--no-color", "--no-log-prefix", "egress-sentinel")...); err != nil {
		return fmt.Errorf("read egress recorder: %w", err)
	}
	forbidden, err := countSentinelEvents(sentinelLogs.Bytes(), lock.RunID)
	if err != nil {
		return err
	}
	if forbidden != 0 {
		return fmt.Errorf("sealed client cells emitted %d forbidden egress events", forbidden)
	}
	var probeOutput bytes.Buffer
	probeArgs := append(append([]string{}, compose...), "run", "--rm", "--no-deps", "network-probe")
	if err := executor.Run(environment, &probeOutput, stderr, dockerBinary, probeArgs...); err != nil {
		return fmt.Errorf("run adversarial network probe: %w", err)
	}
	if err := validateNetworkProbe(probeOutput.Bytes()); err != nil {
		return err
	}
	probeEvents := 0
	for attempt := 0; attempt < 5 && probeEvents == 0; attempt++ {
		var logs bytes.Buffer
		if err := executor.Run(environment, &logs, stderr, dockerBinary, append(compose, "logs", "--no-color", "--no-log-prefix", "egress-sentinel")...); err != nil {
			return fmt.Errorf("read adversarial egress recorder: %w", err)
		}
		probeEvents, err = countSentinelEvents(logs.Bytes(), lock.RunID)
		if err != nil {
			return err
		}
		if probeEvents == 0 {
			time.Sleep(100 * time.Millisecond)
		}
	}
	if probeEvents == 0 {
		return errors.New("known-host adversarial probe was not observed by the external sentinel")
	}
	diagnostics.Phase = "pre-success-teardown"
	captureDiagnostics()
	if diagnosticsErr != nil {
		return diagnosticsErr
	}
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, append(compose, "down", "--volumes", "--remove-orphans", "--timeout", "10")...); err != nil {
		return fmt.Errorf("teardown sealed lab: %w", err)
	}
	tornDown = true
	if err := verifyTeardownInventory(executor, environment, stderr, dockerBinary, compose, projectName); err != nil {
		return err
	}
	teardownClean = true
	digest := contract.SHA256Hex(lockData)
	if lock.IsRecorderCapable() {
		policy, err := readBoundedRegularFile(recorderPolicyPath, maxRecorderPolicyBytes)
		if err != nil {
			return fmt.Errorf("read recorder policy for evidence binding: %w", err)
		}
		if err := verifyExternalRecorderEvidence(recorderEvidence, *lock, lockData, policy, nativePlatform); err != nil {
			return err
		}
	}
	return json.NewEncoder(stdout).Encode(lifecycleResult{
		Schema: "sealed-lab-lifecycle-result/v2", RunID: lock.RunID, NativePlatform: cellPlatforms[0],
		StartedAt: startedAt.Format(time.RFC3339Nano), CompletedAt: time.Now().UTC().Format(time.RFC3339Nano),
		SourceLockSHA256: lock.SourceLockSHA256, RuntimeLockSHA256: digest, SeedConfigRevision: seedEvidence.Revision,
		Clients: clients, NormalCellForbiddenEvents: forbidden, AdversarialProbeRecordedEvents: probeEvents,
		PaidInferenceProof: "unproven-external-recorder-required", TeardownClean: teardownClean,
		CodexInferenceBoundary: codexBoundary,
	})
}

func validateMantleTranscript(data []byte, runID string) error {
	matched := 0
	for _, line := range bytes.Split(data, []byte{'\n'}) {
		line = bytes.TrimSpace(line)
		if len(line) == 0 || line[0] != '{' {
			continue
		}
		var record mantleservice.TranscriptRecord
		if json.Unmarshal(line, &record) != nil || record.Schema != mantleservice.TranscriptSchema {
			continue
		}
		if record.Sequence == 1 && record.Method == "POST" && record.Host == mantleservice.IntegrationHost && record.Path == "/openai/v1/responses" && record.Model == "openai.gpt-5.5" && record.Stream && record.Status == 200 && record.Authorization == "synthetic-bearer" && record.RunID == runID && sha256Value.MatchString(record.BodySHA256) {
			matched++
		}
	}
	if matched != 1 {
		return fmt.Errorf("expected exactly one run-correlated successful GPT-5.5 Responses hop, got %d", matched)
	}
	return nil
}

func validateNativePlatform(raw string) (string, error) {
	platform := strings.TrimSpace(raw)
	switch platform {
	case "linux/amd64", "linux/x86_64":
		return "linux/amd64", nil
	case "linux/arm64", "linux/aarch64":
		return "linux/arm64", nil
	default:
		return "", fmt.Errorf("Docker daemon platform %q is not a supported native evidence platform", platform)
	}
}

func exactEnvironment(images map[string]string, getenv func(string) string) []string {
	environment := []string{"PATH=/usr/bin:/bin", "TZ=UTC"}
	// These values configure the external Docker orchestrator only. They are not
	// passed to, mounted into, or inherited by any sealed runner cell.
	for _, key := range []string{"HOME", "DOCKER_CONFIG", "DOCKER_CONTEXT", "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"} {
		if value := getenv(key); value != "" {
			environment = append(environment, key+"="+value)
		}
	}
	for key, value := range images {
		environment = append(environment, key+"="+value)
	}
	sort.Strings(environment)
	return environment
}

func networkEnvironment(runID string) []string {
	digest := sha256.Sum256([]byte(runID))
	first := 100 + int(digest[0])%100
	second := int(digest[1])
	v6 := fmt.Sprintf("%x%x", digest[0], digest[1])
	bridges, _ := contract.BridgeNames(runID) // RuntimeLock validation already proves runID.
	return []string{
		"LAB_RUN_ID=" + runID,
		"LAB_CLIENT_BRIDGE=" + bridges["client_net"],
		"LAB_CONTROL_BRIDGE=" + bridges["control_net"],
		"LAB_DATA_BRIDGE=" + bridges["data_net"],
		fmt.Sprintf("LAB_CLIENT_IPV4_SUBNET=10.%d.%d.0/24", first, second),
		fmt.Sprintf("LAB_DATA_IPV4_SUBNET=10.%d.%d.0/24", first+1, second),
		fmt.Sprintf("LAB_CONTROL_IPV4_SUBNET=10.%d.%d.0/24", first+2, second),
		fmt.Sprintf("LAB_DNS_IPV4=10.%d.%d.53", first, second),
		fmt.Sprintf("LAB_SENTINEL_IPV4=10.%d.%d.254", first, second),
		fmt.Sprintf("LAB_CLIENT_IPV6_SUBNET=fd00:bf:%s:10::/64", v6),
		fmt.Sprintf("LAB_DATA_IPV6_SUBNET=fd00:bf:%s:20::/64", v6),
		fmt.Sprintf("LAB_CONTROL_IPV6_SUBNET=fd00:bf:%s:30::/64", v6),
		fmt.Sprintf("LAB_DNS_IPV6=fd00:bf:%s:10::53", v6),
		fmt.Sprintf("LAB_SENTINEL_IPV6=fd00:bf:%s:10::fe", v6),
		fmt.Sprintf("LAB_BIFROST_1_CLIENT_IPV4=10.%d.%d.11", first, second),
		fmt.Sprintf("LAB_BIFROST_1_CLIENT_IPV6=fd00:bf:%s:10::11", v6),
		fmt.Sprintf("LAB_BIFROST_1_DATA_IPV4=10.%d.%d.11", first+1, second),
		fmt.Sprintf("LAB_BIFROST_1_DATA_IPV6=fd00:bf:%s:20::11", v6),
		fmt.Sprintf("LAB_BIFROST_2_CLIENT_IPV4=10.%d.%d.12", first, second),
		fmt.Sprintf("LAB_BIFROST_2_CLIENT_IPV6=fd00:bf:%s:10::12", v6),
		fmt.Sprintf("LAB_BIFROST_2_DATA_IPV4=10.%d.%d.12", first+1, second),
		fmt.Sprintf("LAB_BIFROST_2_DATA_IPV6=fd00:bf:%s:20::12", v6),
		fmt.Sprintf("LAB_BIFROST_3_CLIENT_IPV4=10.%d.%d.13", first, second),
		fmt.Sprintf("LAB_BIFROST_3_CLIENT_IPV6=fd00:bf:%s:10::13", v6),
		fmt.Sprintf("LAB_BIFROST_3_DATA_IPV4=10.%d.%d.13", first+1, second),
		fmt.Sprintf("LAB_BIFROST_3_DATA_IPV6=fd00:bf:%s:20::13", v6),
		fmt.Sprintf("LAB_HEALTH_IPV4=10.%d.%d.20", first, second),
		fmt.Sprintf("LAB_HEALTH_IPV6=fd00:bf:%s:10::20", v6),
		fmt.Sprintf("LAB_MANTLE_IPV4=10.%d.%d.20", first+1, second),
		fmt.Sprintf("LAB_MANTLE_IPV6=fd00:bf:%s:20::20", v6),
		fmt.Sprintf("LAB_CONTRACT_IPV4=10.%d.%d.20", first+2, second),
		fmt.Sprintf("LAB_CONTRACT_IPV6=fd00:bf:%s:30::20", v6),
	}
}

func pinnedVersion(lock contract.RuntimeLock, client string) string {
	want := client + "-runner"
	for _, image := range lock.Images {
		if image.ID == want {
			return image.ClientVersion
		}
	}
	return ""
}

func validatePinnedClientVersions(runtime contract.RuntimeLock, source contract.Lock) error {
	want := map[string]string{}
	for _, cli := range source.CLIPackages {
		switch cli.ID {
		case "claude-code-production":
			want["claude-runner"] = cli.Version
		case "codex-production":
			want["codex-runner"] = cli.Version
		}
	}
	for _, image := range runtime.Images {
		if version, isRunner := want[image.ID]; isRunner && image.ClientVersion != version {
			return fmt.Errorf("runtime image %s version %q does not match source lock %q", image.ID, image.ClientVersion, version)
		}
	}
	return nil
}

func validateCellResult(data []byte, runID, client, version, daemonPlatform string) (cellResult, error) {
	decoder := json.NewDecoder(io.LimitReader(bytes.NewReader(data), 1<<20))
	decoder.DisallowUnknownFields()
	var result cellResult
	if err := decoder.Decode(&result); err != nil {
		return cellResult{}, err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return cellResult{}, errors.New("cell emitted more than one JSON record")
	}
	if result.Client != client || result.ResidueCount != 0 || result.ClientVersion == "" {
		return cellResult{}, errors.New("cell result violates the sealed contract")
	}
	if client == "codex" {
		validOutcome := result.ExitCode == 0 && result.TransportOutcome == "completed"
		if result.Schema != "sealed-cli-cell-evidence/v2" || result.Operation != "codex-inference-boundary" || !result.ProcessStarted || !result.RequestInitiated || !validOutcome || result.EventCount < 3 || result.OutputBytes <= 0 || !sha256Value.MatchString(result.OutputSHA256) || result.OutputTruncated || !internalCellGateway.MatchString(result.GatewayBaseURL) {
			return cellResult{}, errors.New("Codex cell did not prove the sealed inference invocation boundary")
		}
		if !validInferenceCellEnvironment(result.Environment) {
			return cellResult{}, errors.New("Codex cell environment does not match the sealed inference-cell allowlist")
		}
	} else {
		if result.Schema != "sealed-cli-cell-evidence/v1" || result.ExitCode != 0 || result.Operation != "" || result.ProcessStarted || result.RequestInitiated || result.TransportOutcome != "" || result.EventCount != 0 || result.OutputBytes != 0 || result.OutputSHA256 != "" || result.OutputTruncated || result.GatewayBaseURL != "" {
			return cellResult{}, errors.New("version cell result violates the sealed contract")
		}
		if !validVersionCellEnvironment(result.Environment) {
			return cellResult{}, errors.New("cell result environment does not match the sealed version-cell allowlist")
		}
	}
	if version != "" && result.ClientVersion != version {
		return cellResult{}, errors.New("cell version does not match runtime lock")
	}
	if result.RunID != runID || runID == "" {
		return cellResult{}, errors.New("cell result is not bound to lifecycle run identity")
	}
	if result.NativePlatform != daemonPlatform || (result.NativePlatform != "linux/amd64" && result.NativePlatform != "linux/arm64") {
		return cellResult{}, errors.New("cell runtime architecture does not match the native Docker daemon platform")
	}
	return result, nil
}

var sha256Value = regexp.MustCompile(`^[0-9a-f]{64}$`)
var internalCellGateway = regexp.MustCompile(`^http://bifrost-[123]:8080/openai/v1/?$`)

func validInferenceCellEnvironment(names []string) bool {
	want := []string{"CODEX_HOME", "HOME", "LANG", "OPENAI_API_KEY", "OPENAI_BASE_URL", "PATH", "TMPDIR", "TZ", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"}
	if len(names) != len(want) {
		return false
	}
	for index := range want {
		if names[index] != want[index] {
			return false
		}
	}
	return true
}

func validVersionCellEnvironment(names []string) bool {
	want := []string{"CODEX_HOME", "HOME", "LANG", "PATH", "TMPDIR", "TZ", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"}
	if len(names) != len(want) {
		return false
	}
	for index := range want {
		if names[index] != want[index] {
			return false
		}
	}
	return true
}

func validateNetworkProbe(data []byte) error {
	decoder := json.NewDecoder(io.LimitReader(bytes.NewReader(data), 1<<20))
	decoder.DisallowUnknownFields()
	var result networkProbeResult
	if err := decoder.Decode(&result); err != nil {
		return fmt.Errorf("network probe JSON: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("network probe emitted more than one JSON record")
	}
	if result.Schema != "sealed-lab-network-probe/v1" || result.KnownDNS != 1 || result.UnknownDNSBlocked != 1 ||
		result.KnownHostTrapped != 1 || result.DirectIPv4Blocked != 1 || result.DirectIPv6Blocked != 1 ||
		result.QUICBlocked != 1 || result.ProxyBypassBlocked != 1 {
		return errors.New("network probe did not prove every escape negative")
	}
	return nil
}

func validateOCIIndex(data []byte) error {
	var index struct {
		Manifests []struct {
			Platform struct {
				OS           string `json:"os"`
				Architecture string `json:"architecture"`
			} `json:"platform"`
		} `json:"manifests"`
	}
	decoder := json.NewDecoder(io.LimitReader(bytes.NewReader(data), 4<<20))
	if err := decoder.Decode(&index); err != nil {
		return err
	}
	seen := map[string]bool{}
	for _, manifest := range index.Manifests {
		seen[manifest.Platform.OS+"/"+manifest.Platform.Architecture] = true
	}
	if !seen["linux/amd64"] || !seen["linux/arm64"] {
		return errors.New("OCI index does not contain linux/amd64 and linux/arm64")
	}
	return nil
}

func countSentinelEvents(data []byte, runID string) (int, error) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	count := 0
	for {
		var event struct {
			Schema         string    `json:"schema"`
			ObservedAt     time.Time `json:"observed_at"`
			RunID          string    `json:"run_id"`
			Source         string    `json:"source"`
			Destination    string    `json:"destination"`
			Family         string    `json:"family"`
			Transport      string    `json:"transport"`
			Port           string    `json:"port"`
			Classification string    `json:"classification"`
			Bytes          int       `json:"bytes"`
		}
		if err := decoder.Decode(&event); err != nil {
			if err == io.EOF {
				return count, nil
			}
			return 0, fmt.Errorf("invalid egress recorder JSONL: %w", err)
		}
		if event.Schema != "sealed-lab-egress-event/v1" || event.RunID != runID || event.ObservedAt.IsZero() ||
			!validSentinelEndpoints(event.Source, event.Destination, event.Family, event.Port) ||
			(event.Transport != "tcp" && event.Transport != "udp") || !allowedSentinelPort(event.Transport, event.Port) ||
			event.Bytes < 0 || event.Classification != "forbidden-egress-attempt" {
			return 0, errors.New("invalid egress recorder event")
		}
		count++
	}
}

func validSentinelEndpoints(source, destination, family, port string) bool {
	sourceHost, _, sourceErr := net.SplitHostPort(source)
	destinationHost, destinationPort, destinationErr := net.SplitHostPort(destination)
	sourceIP, destinationIP := net.ParseIP(sourceHost), net.ParseIP(destinationHost)
	if sourceErr != nil || destinationErr != nil || sourceIP == nil || destinationIP == nil || destinationPort != port {
		return false
	}
	if family == "ipv4" {
		return sourceIP.To4() != nil && destinationIP.To4() != nil
	}
	return family == "ipv6" && sourceIP.To4() == nil && destinationIP.To4() == nil
}

func allowedSentinelPort(transport, port string) bool {
	if transport == "udp" {
		return port == "53" || port == "443"
	}
	return port == "80" || port == "443" || port == "3128" || port == "8080"
}

func verifyTeardownInventory(executor commandExecutor, environment []string, stderr io.Writer, dockerBinary string, compose []string, projectName string) error {
	queries := [][]string{
		append(append([]string{}, compose...), "ps", "--all", "--quiet"),
		{"ps", "--all", "--quiet", "--filter", "label=com.docker.compose.project=" + projectName},
		{"network", "ls", "--quiet", "--filter", "label=com.docker.compose.project=" + projectName},
		{"volume", "ls", "--quiet", "--filter", "label=com.docker.compose.project=" + projectName},
	}
	for _, query := range queries {
		var output bytes.Buffer
		if err := executor.Run(environment, &output, stderr, dockerBinary, query...); err != nil {
			return fmt.Errorf("teardown inventory %q: %w", strings.Join(query, " "), err)
		}
		if strings.TrimSpace(output.String()) != "" {
			return fmt.Errorf("sealed lab teardown left resources for %q", strings.Join(query, " "))
		}
	}
	return nil
}
