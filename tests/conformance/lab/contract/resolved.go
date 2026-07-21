package contract

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
)

type resolvedCompose struct {
	Services map[string]resolvedService `json:"services"`
	Networks map[string]resolvedNetwork `json:"networks"`
}

type resolvedService struct {
	Image         string            `json:"image"`
	Privileged    bool              `json:"privileged"`
	ReadOnly      bool              `json:"read_only"`
	NetworkMode   string            `json:"network_mode"`
	CapAdd        []string          `json:"cap_add"`
	CapDrop       []string          `json:"cap_drop"`
	SecurityOpt   []string          `json:"security_opt"`
	Command       []string          `json:"command"`
	Ports         []json.RawMessage `json:"ports"`
	Volumes       []resolvedMount   `json:"volumes"`
	Environment   map[string]any    `json:"environment"`
	ExternalLinks []string          `json:"external_links"`
	Devices       []json.RawMessage `json:"devices"`
	IPC           string            `json:"ipc"`
	PID           string            `json:"pid"`
	UserNS        string            `json:"userns_mode"`
}

type resolvedMount struct {
	Type   string `json:"type"`
	Source string `json:"source"`
	Target string `json:"target"`
}

type resolvedNetwork struct {
	Internal   bool              `json:"internal"`
	EnableIPv6 bool              `json:"enable_ipv6"`
	External   bool              `json:"external"`
	Driver     string            `json:"driver"`
	DriverOpts map[string]string `json:"driver_opts"`
}

// ValidateResolvedCompose validates Docker Compose's normalized JSON output.
// This is the runtime sealing gate; raw YAML checks are only an early lint.
func ValidateResolvedCompose(data []byte, source Lock, runtime RuntimeLock) error {
	decoder := json.NewDecoder(io.LimitReader(bytes.NewReader(data), 4<<20))
	var document resolvedCompose
	if err := decoder.Decode(&document); err != nil {
		return fmt.Errorf("decode resolved Compose: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return fmt.Errorf("resolved Compose contains trailing JSON")
	}
	requiredServices := []string{
		"bifrost-1", "bifrost-2", "bifrost-3", "claude-runner", "codex-runner", "contract-stub", "controlled-dns",
		"egress-sentinel", "health-stub", "netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3",
		"netns-claude", "netns-codex", "network-probe", "postgres",
	}
	for _, name := range requiredServices {
		service, exists := document.Services[name]
		if !exists {
			return fmt.Errorf("resolved Compose misses service %q", name)
		}
		if err := validateResolvedService(name, service); err != nil {
			return err
		}
	}
	wantModes := map[string]string{
		"bifrost-1": "service:netns-bifrost-1", "bifrost-2": "service:netns-bifrost-2", "bifrost-3": "service:netns-bifrost-3",
		"claude-runner": "service:netns-claude", "codex-runner": "service:netns-codex", "network-probe": "service:netns-codex",
	}
	for name, mode := range wantModes {
		if document.Services[name].NetworkMode != mode {
			return fmt.Errorf("service %q network mode %q does not match %q", name, document.Services[name].NetworkMode, mode)
		}
	}
	for _, name := range []string{"netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "netns-claude", "netns-codex"} {
		command := strings.Join(document.Services[name].Command, "\n")
		for _, required := range []string{"ip route del", "ip -6 route del", "test -z", "ip route get"} {
			if !strings.Contains(command, required) {
				return fmt.Errorf("service %q command misses route-isolation assertion %q", name, required)
			}
		}
	}
	if len(document.Networks) != 3 {
		return fmt.Errorf("resolved Compose must contain exactly three networks")
	}
	for _, name := range []string{"client_net", "control_net", "data_net"} {
		if _, ok := document.Networks[name]; !ok {
			return fmt.Errorf("resolved Compose misses required network %q", name)
		}
	}
	bridgeNames, err := BridgeNames(runtime.RunID)
	if err != nil {
		return err
	}
	seenBridges := map[string]bool{}
	for name, network := range document.Networks {
		if !network.Internal || !network.EnableIPv6 || network.External {
			return fmt.Errorf("network %q is not internal dual-stack", name)
		}
		bridge := network.DriverOpts["com.docker.network.bridge.name"]
		if network.Driver != "bridge" || bridge != bridgeNames[name] || len(network.DriverOpts) != 1 || seenBridges[bridge] {
			return fmt.Errorf("network %q does not use its unique run-bound bridge", name)
		}
		seenBridges[bridge] = true
	}
	wantImages := make(map[string]string)
	for _, image := range source.Images {
		switch image.ID {
		case "alpine-netns":
			for _, service := range []string{"netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "netns-claude", "netns-codex", "network-probe"} {
				wantImages[service] = image.Reference
			}
		case "coredns":
			wantImages["controlled-dns"] = image.Reference
		case "health-stub":
			wantImages["health-stub"] = image.Reference
			wantImages["contract-stub"] = image.Reference
		case "postgres":
			wantImages["postgres"] = image.Reference
		}
	}
	for _, image := range runtime.Images {
		switch image.ID {
		case "bifrost":
			for _, service := range []string{"bifrost-1", "bifrost-2", "bifrost-3"} {
				wantImages[service] = image.Reference
			}
		case "claude-runner":
			wantImages["claude-runner"] = image.Reference
		case "codex-runner":
			wantImages["codex-runner"] = image.Reference
		case "egress-sentinel":
			wantImages["egress-sentinel"] = image.Reference
		}
	}
	for service, image := range wantImages {
		if document.Services[service].Image != image {
			return fmt.Errorf("service %q image %q does not match lock %q", service, document.Services[service].Image, image)
		}
	}
	sentinel := document.Services["egress-sentinel"]
	if !containsExact(sentinel.Command, "-run-id="+runtime.RunID) {
		return fmt.Errorf("egress sentinel is not bound to lifecycle run %q", runtime.RunID)
	}
	return nil
}

func validateResolvedService(name string, service resolvedService) error {
	if service.Privileged || !service.ReadOnly || len(service.Ports) != 0 || len(service.ExternalLinks) != 0 || len(service.Devices) != 0 || service.IPC != "" || service.PID != "" || service.UserNS != "" {
		return fmt.Errorf("service %q violates read-only/no-publish/no-privilege policy", name)
	}
	if !containsFold(service.CapDrop, "ALL") || !containsExact(service.SecurityOpt, "no-new-privileges:true") {
		return fmt.Errorf("service %q lacks capability/security hardening", name)
	}
	allowedCaps := map[string][]string{
		"controlled-dns":  {"NET_BIND_SERVICE"},
		"netns-bifrost-1": {"NET_ADMIN"}, "netns-bifrost-2": {"NET_ADMIN"}, "netns-bifrost-3": {"NET_ADMIN"},
		"netns-claude": {"NET_ADMIN"}, "netns-codex": {"NET_ADMIN"},
	}
	gotCaps := append([]string(nil), service.CapAdd...)
	wantCaps := append([]string(nil), allowedCaps[name]...)
	sort.Strings(gotCaps)
	sort.Strings(wantCaps)
	if strings.Join(gotCaps, "\x00") != strings.Join(wantCaps, "\x00") {
		return fmt.Errorf("service %q has unexpected added capabilities %v", name, gotCaps)
	}
	if service.NetworkMode == "host" || strings.HasPrefix(service.NetworkMode, "container:") {
		return fmt.Errorf("service %q uses forbidden network mode %q", name, service.NetworkMode)
	}
	for _, mount := range service.Volumes {
		joined := strings.ToLower(mount.Source + " " + mount.Target)
		if mount.Type != "tmpfs" || strings.Contains(joined, "docker.sock") || strings.Contains(joined, "/var/run/docker") {
			return fmt.Errorf("service %q has non-tmpfs or Docker mount %+v", name, mount)
		}
	}
	for key := range service.Environment {
		upper := strings.ToUpper(key)
		for _, forbidden := range []string{"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "AWS_ACCESS_KEY", "AWS_SECRET", "AWS_SESSION", "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CLIENT_SECRET", "DOCKER_HOST"} {
			if strings.Contains(upper, forbidden) {
				return fmt.Errorf("service %q environment contains forbidden key %q", name, key)
			}
		}
	}
	return nil
}

func containsExact(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}

func containsFold(values []string, want string) bool {
	for _, value := range values {
		if strings.EqualFold(value, want) {
			return true
		}
	}
	return false
}
