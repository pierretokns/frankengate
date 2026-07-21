package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

type commandExecutor interface {
	Run(env []string, stdout, stderr io.Writer, name string, args ...string) error
}

type osExecutor struct{}

func (osExecutor) Run(env []string, stdout, stderr io.Writer, name string, args ...string) error {
	command := exec.Command(name, args...)
	command.Env = env
	command.Stdout = stdout
	command.Stderr = stderr
	return command.Run()
}

type cellResult struct {
	Schema        string `json:"schema"`
	RunID         string `json:"run_id"`
	Client        string `json:"client"`
	ExitCode      int    `json:"exit_code"`
	ResidueCount  int    `json:"residue_count"`
	ClientVersion string `json:"client_version"`
}

type lifecycleResult struct {
	Schema                         string   `json:"schema"`
	RunID                          string   `json:"run_id"`
	RuntimeLockSHA256              string   `json:"runtime_lock_sha256"`
	Clients                        []string `json:"clients"`
	NormalCellForbiddenEvents      int      `json:"normal_cell_forbidden_events"`
	AdversarialProbeRecordedEvents int      `json:"adversarial_probe_recorded_events"`
	PaidInferenceRequests          int      `json:"paid_inference_requests"`
	TeardownClean                  bool     `json:"teardown_clean"`
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
	var lockPath, sourceLockPath, composePath, dockerBinary string
	flag.StringVar(&lockPath, "runtime-lock", "", "path to sealed-lab-runtime-lock/v1")
	flag.StringVar(&sourceLockPath, "source-lock", "", "path to committed sealed-lab-image-lock/v1")
	flag.StringVar(&composePath, "compose", "compose.yaml", "sealed lab Compose file")
	flag.StringVar(&dockerBinary, "docker", "docker", "reviewed Docker CLI path")
	flag.Parse()
	if err := run(osExecutor{}, lockPath, sourceLockPath, composePath, dockerBinary, os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "lab-runner:", err)
		os.Exit(1)
	}
}

func run(executor commandExecutor, lockPath, sourceLockPath, composePath, dockerBinary string, stdout, stderr io.Writer) error {
	if lockPath == "" || !filepath.IsAbs(lockPath) || !filepath.IsAbs(sourceLockPath) || !filepath.IsAbs(composePath) || !filepath.IsAbs(dockerBinary) {
		return errors.New("runtime lock, source lock, Compose file, and Docker binary must be absolute paths")
	}
	lockData, err := os.ReadFile(lockPath)
	if err != nil {
		return err
	}
	lock, err := contract.DecodeRuntimeLock(bytes.NewReader(lockData))
	if err != nil {
		return fmt.Errorf("runtime lock: %w", err)
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
	if err := validatePinnedClientVersions(*lock, *sourceLock); err != nil {
		return err
	}
	composeData, err := os.ReadFile(composePath)
	if err != nil {
		return err
	}
	if err := contract.ValidateCompose(composeData); err != nil {
		return fmt.Errorf("compose contract: %w", err)
	}
	environment := exactEnvironment(lock.ComposeEnvironment(), os.Getenv)
	environment = append(environment, networkEnvironment(lock.RunID)...)
	sort.Strings(environment)
	for _, image := range lock.Images {
		var raw bytes.Buffer
		if err := executor.Run(environment, &raw, stderr, dockerBinary, "buildx", "imagetools", "inspect", "--raw", image.Reference); err != nil {
			return fmt.Errorf("inspect runtime image %s: %w", image.ID, err)
		}
		if err := validateOCIIndex(raw.Bytes()); err != nil {
			return fmt.Errorf("runtime image %s: %w", image.ID, err)
		}
	}
	compose := []string{"compose", "--project-name", "fg-lab-" + lock.RunID, "--file", composePath, "--profile", "clients"}
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, append(compose, "config", "--quiet")...); err != nil {
		return fmt.Errorf("resolved Compose validation: %w", err)
	}
	coreServices := []string{
		"postgres", "netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "bifrost-1", "bifrost-2", "bifrost-3",
		"health-stub", "controlled-dns", "egress-sentinel", "netns-codex", "netns-claude",
	}
	teardownClean := false
	tornDown := false
	defer func() {
		if !tornDown {
			_ = executor.Run(environment, io.Discard, stderr, dockerBinary, append(compose, "down", "--volumes", "--remove-orphans", "--timeout", "10")...)
		}
	}()
	upArgs := append(append([]string{}, compose...), "up", "--detach", "--wait")
	upArgs = append(upArgs, coreServices...)
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, upArgs...); err != nil {
		return fmt.Errorf("start sealed lab: %w", err)
	}
	clients := []string{"claude", "codex"}
	for _, client := range clients {
		var raw bytes.Buffer
		args := append(append([]string{}, compose...), "run", "--rm", "--no-deps", client+"-runner")
		if err := executor.Run(environment, &raw, stderr, dockerBinary, args...); err != nil {
			return fmt.Errorf("run %s cell: %w", client, err)
		}
		if err := validateCellResult(raw.Bytes(), lock.RunID, client, pinnedVersion(*lock, client)); err != nil {
			return fmt.Errorf("%s cell evidence: %w", client, err)
		}
	}
	var sentinelLogs bytes.Buffer
	if err := executor.Run(environment, &sentinelLogs, stderr, dockerBinary, append(compose, "logs", "--no-color", "--no-log-prefix", "egress-sentinel")...); err != nil {
		return fmt.Errorf("read egress recorder: %w", err)
	}
	forbidden, err := countSentinelEvents(sentinelLogs.Bytes())
	if err != nil {
		return err
	}
	if forbidden != 0 {
		return fmt.Errorf("sealed version cells emitted %d forbidden egress events", forbidden)
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
		probeEvents, err = countSentinelEvents(logs.Bytes())
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
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, append(compose, "down", "--volumes", "--remove-orphans", "--timeout", "10")...); err != nil {
		return fmt.Errorf("teardown sealed lab: %w", err)
	}
	tornDown = true
	var remaining bytes.Buffer
	if err := executor.Run(environment, &remaining, stderr, dockerBinary, append(compose, "ps", "--all", "--quiet")...); err != nil {
		return fmt.Errorf("teardown inventory: %w", err)
	}
	teardownClean = strings.TrimSpace(remaining.String()) == ""
	if !teardownClean {
		return errors.New("sealed lab teardown left containers behind")
	}
	digest := contract.SHA256Hex(lockData)
	return json.NewEncoder(stdout).Encode(lifecycleResult{
		Schema: "sealed-lab-lifecycle-result/v1", RunID: lock.RunID, RuntimeLockSHA256: digest,
		Clients: clients, NormalCellForbiddenEvents: forbidden, AdversarialProbeRecordedEvents: probeEvents,
		PaidInferenceRequests: 0, TeardownClean: teardownClean,
	})
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
	return []string{
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

func validateCellResult(data []byte, runID, client, version string) error {
	decoder := json.NewDecoder(io.LimitReader(bytes.NewReader(data), 1<<20))
	decoder.DisallowUnknownFields()
	var result cellResult
	if err := decoder.Decode(&result); err != nil {
		return err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("cell emitted more than one JSON record")
	}
	if result.Schema != "sealed-cli-cell-evidence/v1" || result.Client != client || result.ExitCode != 0 || result.ResidueCount != 0 || result.ClientVersion == "" {
		return errors.New("cell result violates the sealed contract")
	}
	if version != "" && result.ClientVersion != version {
		return errors.New("cell version does not match runtime lock")
	}
	// Compose scenarios have stable per-client run IDs; the lifecycle run ID is
	// carried by the runtime lock and intentionally does not overwrite them.
	if result.RunID == "" || runID == "" {
		return errors.New("missing run identity")
	}
	return nil
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

func countSentinelEvents(data []byte) (int, error) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	count := 0
	for {
		var event struct {
			Schema         string `json:"schema"`
			Classification string `json:"classification"`
		}
		if err := decoder.Decode(&event); err != nil {
			if err == io.EOF {
				return count, nil
			}
			return 0, fmt.Errorf("invalid egress recorder JSONL: %w", err)
		}
		if event.Schema != "sealed-lab-egress-event/v1" || event.Classification != "forbidden-egress-attempt" {
			return 0, errors.New("invalid egress recorder event")
		}
		count++
	}
}
