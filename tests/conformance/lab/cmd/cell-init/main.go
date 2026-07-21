package main

import (
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

var internalBaseURL = regexp.MustCompile(`^http://bifrost-[123]:8080/(?:openai/v1|anthropic)(?:/)?$`)
var exactRunID = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,47}$`)
var observedSemver = regexp.MustCompile(`(?:^|[^0-9.])([0-9]+\.[0-9]+\.[0-9]+)(?:[^0-9.]|$)`)

type scenario struct {
	Schema          string            `json:"schema"`
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
	Schema        string   `json:"schema"`
	RunID         string   `json:"run_id"`
	Client        string   `json:"client"`
	ExitCode      int      `json:"exit_code"`
	Environment   []string `json:"environment_names"`
	ResidueCount  int      `json:"residue_count"`
	ClientVersion string   `json:"client_version"`
}

type boundedCapture struct {
	mu        sync.Mutex
	data      []byte
	remaining int
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
	}
	return len(data), nil
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
	command := exec.Command(cfg.Binary, cfg.Args...)
	command.Env = environment
	command.Dir = filepath.Join(cellRoot, "home")
	output := newBoundedCapture(1 << 20)
	command.Stdout = io.MultiWriter(os.Stderr, output)
	command.Stderr = io.MultiWriter(os.Stderr, output)
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := command.Start(); err != nil {
		return err
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
				return waitErr
			}
		}
	case <-time.After(timeout):
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGTERM)
		time.Sleep(2 * time.Second)
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGKILL)
		<-done
		exitCode = 124
	}
	version, err := parseObservedVersion(output.Bytes())
	if err != nil || version != cfg.ExpectedVersion {
		return fmt.Errorf("client version output %q does not exactly match pinned version %q", version, cfg.ExpectedVersion)
	}
	if err := clearCell(); err != nil {
		return err
	}
	residue := countEntries(cellRoot)
	names := make([]string, 0, len(environment))
	for _, item := range environment {
		names = append(names, strings.SplitN(item, "=", 2)[0])
	}
	return json.NewEncoder(os.Stdout).Encode(evidence{
		Schema: "sealed-cli-cell-evidence/v1", RunID: cfg.RunID, Client: cfg.Client,
		ExitCode: exitCode, Environment: names, ResidueCount: residue, ClientVersion: version,
	})
}

func parseObservedVersion(output []byte) (string, error) {
	matches := observedSemver.FindAllSubmatch(output, -1)
	if len(matches) != 1 {
		return "", fmt.Errorf("version output must contain exactly one semantic version")
	}
	return string(matches[0][1]), nil
}

func validateScenario(cfg scenario) error {
	if cfg.Schema != "sealed-cli-cell-scenario/v1" || cfg.RunID == "" || (cfg.Client != "codex" && cfg.Client != "claude") {
		return errors.New("invalid scenario identity")
	}
	wantBinary := map[string]string{"codex": "/opt/client/bin/codex", "claude": "/opt/client/bin/claude"}[cfg.Client]
	if cfg.Binary != wantBinary || len(cfg.Args) == 0 || len(cfg.Args) > 64 || !exactSemver(cfg.ExpectedVersion) || cfg.TimeoutMS < 0 || cfg.TimeoutMS > int((15*time.Minute)/time.Millisecond) {
		return errors.New("invalid scenario process contract")
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
