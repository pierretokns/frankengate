package contract

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestResolvedComposeIsStructurallyBoundToLocks(t *testing.T) {
	document, source, runtime := resolvedFixture()
	data, _ := json.Marshal(document)
	if err := ValidateResolvedCompose(data, source, runtime); err != nil {
		t.Fatal(err)
	}
	mutations := []struct {
		name   string
		mutate func(*resolvedCompose)
	}{
		{"privileged yes", func(d *resolvedCompose) {
			service := d.Services["postgres"]
			service.Privileged = true
			d.Services["postgres"] = service
		}},
		{"host network quoted", func(d *resolvedCompose) {
			service := d.Services["network-probe"]
			service.NetworkMode = "host"
			d.Services["network-probe"] = service
		}},
		{"swapped locked image", func(d *resolvedCompose) {
			service := d.Services["postgres"]
			service.Image = "attacker.invalid/postgres@sha256:" + strings.Repeat("f", 64)
			d.Services["postgres"] = service
		}},
		{"published port", func(d *resolvedCompose) {
			service := d.Services["bifrost-1"]
			service.Ports = []json.RawMessage{json.RawMessage(`{"published":8080}`)}
			d.Services["bifrost-1"] = service
		}},
		{"external network", func(d *resolvedCompose) {
			network := d.Networks["client_net"]
			network.External = true
			d.Networks["client_net"] = network
		}},
		{"wrong bridge driver", func(d *resolvedCompose) {
			network := d.Networks["client_net"]
			network.Driver = "overlay"
			d.Networks["client_net"] = network
		}},
		{"swapped bridge identity", func(d *resolvedCompose) {
			client := d.Networks["client_net"]
			data := d.Networks["data_net"]
			client.DriverOpts["com.docker.network.bridge.name"], data.DriverOpts["com.docker.network.bridge.name"] = data.DriverOpts["com.docker.network.bridge.name"], client.DriverOpts["com.docker.network.bridge.name"]
			d.Networks["client_net"], d.Networks["data_net"] = client, data
		}},
		{"extra bridge option", func(d *resolvedCompose) {
			network := d.Networks["control_net"]
			network.DriverOpts["com.docker.network.bridge.enable_ip_masquerade"] = "true"
			d.Networks["control_net"] = network
		}},
		{"renamed logical network", func(d *resolvedCompose) {
			network := d.Networks["control_net"]
			delete(d.Networks, "control_net")
			d.Networks["evil_net"] = network
		}},
		{"wrong run identity", func(d *resolvedCompose) {
			service := d.Services["egress-sentinel"]
			service.Command = []string{"-run-id=other"}
			d.Services["egress-sentinel"] = service
		}},
		{"observer disabled", func(d *resolvedCompose) {
			service := d.Services["bifrost-2"]
			service.Environment["BIFROST_SEALED_LAB_INGRESS_OBSERVER"] = "0"
			d.Services["bifrost-2"] = service
		}},
		{"loopback-only Bifrost bind", func(d *resolvedCompose) {
			service := d.Services["bifrost-1"]
			service.Environment["BIFROST_HOST"] = "localhost"
			d.Services["bifrost-1"] = service
		}},
		{"observer wrong run identity", func(d *resolvedCompose) {
			service := d.Services["bifrost-3"]
			service.Environment["LAB_RUN_ID"] = "other"
			d.Services["bifrost-3"] = service
		}},
		{"route isolation removed", func(d *resolvedCompose) {
			service := d.Services["netns-codex"]
			service.Command = []string{"tail -f /dev/null"}
			d.Services["netns-codex"] = service
		}},
	}
	for _, mutation := range mutations {
		t.Run(mutation.name, func(t *testing.T) {
			candidate, _, _ := resolvedFixture()
			mutation.mutate(&candidate)
			data, _ := json.Marshal(candidate)
			if err := ValidateResolvedCompose(data, source, runtime); err == nil {
				t.Fatal("unsafe normalized Compose mutation was accepted")
			}
		})
	}
}

func resolvedFixture() (resolvedCompose, Lock, RuntimeLock) {
	digest := func(letter string) string { return "registry.invalid/image@sha256:" + strings.Repeat(letter, 64) }
	source := Lock{Images: []Image{
		{ID: "alpine-netns", Reference: digest("1")}, {ID: "coredns", Reference: digest("2")},
		{ID: "health-stub", Reference: digest("3")}, {ID: "postgres", Reference: digest("4")},
	}}
	runtime := RuntimeLock{RunID: "run-1", Images: []RuntimeImage{
		{ID: "bifrost", Reference: digest("a")}, {ID: "claude-runner", Reference: digest("b")},
		{ID: "codex-runner", Reference: digest("c")}, {ID: "egress-sentinel", Reference: digest("d")},
	}}
	base := func(image string) resolvedService {
		return resolvedService{Image: image, ReadOnly: true, CapDrop: []string{"ALL"}, SecurityOpt: []string{"no-new-privileges:true"}}
	}
	services := map[string]resolvedService{}
	for _, name := range []string{"netns-bifrost-1", "netns-bifrost-2", "netns-bifrost-3", "netns-claude", "netns-codex"} {
		service := base(digest("1"))
		service.CapAdd = []string{"NET_ADMIN"}
		service.Command = []string{"ip route del default; ip -6 route del default; test -z routes; ip route get dns"}
		services[name] = service
	}
	services["network-probe"] = base(digest("1"))
	services["network-probe"] = withMode(services["network-probe"], "service:netns-codex")
	services["controlled-dns"] = base(digest("2"))
	dns := services["controlled-dns"]
	dns.CapAdd = []string{"NET_BIND_SERVICE"}
	services["controlled-dns"] = dns
	services["health-stub"] = base(digest("3"))
	services["contract-stub"] = base(digest("3"))
	services["postgres"] = base(digest("4"))
	services["config-seed"] = base(digest("a"))
	services["mantle-contract-service"] = base(digest("a"))
	services["bifrost-1"] = withMode(base(digest("a")), "service:netns-bifrost-1")
	services["bifrost-2"] = withMode(base(digest("a")), "service:netns-bifrost-2")
	services["bifrost-3"] = withMode(base(digest("a")), "service:netns-bifrost-3")
	for _, name := range []string{"bifrost-1", "bifrost-2", "bifrost-3"} {
		service := services[name]
		service.Environment = map[string]any{
			"BIFROST_HOST":                        "0.0.0.0",
			"BIFROST_SEALED_LAB_INGRESS_OBSERVER": "1",
			"LAB_RUN_ID":                          runtime.RunID,
		}
		services[name] = service
	}
	services["claude-runner"] = withMode(base(digest("b")), "service:netns-claude")
	services["codex-runner"] = withMode(base(digest("c")), "service:netns-codex")
	sentinel := base(digest("d"))
	sentinel.Command = []string{"-run-id=run-1"}
	services["egress-sentinel"] = sentinel
	bridges, _ := BridgeNames("run-1")
	networks := map[string]resolvedNetwork{}
	for _, name := range []string{"client_net", "control_net", "data_net"} {
		networks[name] = resolvedNetwork{Internal: true, EnableIPv6: true, Driver: "bridge", DriverOpts: map[string]string{"com.docker.network.bridge.name": bridges[name]}}
	}
	return resolvedCompose{Services: services, Networks: networks}, source, runtime
}

func withMode(service resolvedService, mode string) resolvedService {
	service.NetworkMode = mode
	return service
}
