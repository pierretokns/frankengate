package contract

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHostedWorkflowPreservesSealedLabInputs(t *testing.T) {
	root := filepath.Join("..", "..", "..", "..")
	read := func(path string) string {
		data, err := os.ReadFile(filepath.Join(root, path))
		if err != nil {
			t.Fatal(err)
		}
		return string(data)
	}
	workflow := read(".github/workflows/sealed-mantle-lab.yml")
	script := read(".github/scripts/run-sealed-mantle-lab.sh")
	for _, required := range []string{"pull_request:", "workflow_dispatch:", "run: bash .github/scripts/run-sealed-mantle-lab.sh", "driver-opts: network=host", "if: always()", "actions/upload-artifact@"} {
		if !strings.Contains(workflow, required) {
			t.Fatalf("hosted workflow misses %q", required)
		}
	}
	if strings.Contains(workflow, "paths:") || strings.Contains(workflow, "paths-ignore:") {
		t.Fatal("hosted workflow must not filter gateway-affecting PR paths")
	}
	for _, required := range []string{
		"registry:2@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373",
		"git -C \"$root\" archive HEAD", "--file \"$build/source/tests/conformance/lab/Dockerfile.gateway\"", "\"$build/source\"",
		"test -f \"$build/source/tests/conformance/lab/cmd/config-seed/main.go\"",
		"artifact_status", "rejected-oversize", "size > 4194304", "total > 8388608", "runtime-lock.json", "lifecycle.json",
		`docker buildx build --network=none --platform "linux/$arch" --file "$lab/Dockerfile.runner" --push --tag "$tag" "$context"`,
		`docker buildx build --network=none --platform "linux/$arch" --file "$lab/Dockerfile.sentinel" --push --tag "$registry/sentinel:$run_id-$arch" "$build/sentinel-$arch"`,
	} {
		if !strings.Contains(script, required) {
			t.Fatalf("hosted runner misses %q", required)
		}
	}
	if strings.Count(script, "docker buildx build --network=none") != 2 {
		t.Fatal("offline second-stage build count drifted")
	}
	for _, forbidden := range []string{"truncate -s", "registry:2\n", `docker buildx build --platform linux/amd64,linux/arm64 --file "$lab/Dockerfile.gateway"`} {
		if strings.Contains(script, forbidden) {
			t.Fatalf("hosted runner retains unsafe pattern %q", forbidden)
		}
	}
	ignore := read("tests/conformance/lab/Dockerfile.gateway.dockerignore")
	if strings.Contains(ignore, "tests") || !strings.Contains(ignore, ".git") {
		t.Fatal("gateway-specific build context excludes required lab source")
	}
	if _, err := os.Stat(filepath.Join(root, "tests/conformance/lab/Dockerfile.gateway")); err != nil {
		t.Fatal("gateway-specific ignore is not colocated with its Dockerfile")
	}
}
