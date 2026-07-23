package main

import (
	"archive/tar"
	"bytes"
	"os"
	"os/exec"
	"strings"
	"testing"
)

// TestDockerRecorderCopyContract characterizes the real Docker copy archive
// used by recorder verification. CI opts in explicitly so ordinary unit tests
// remain hermetic on hosts without a Docker daemon.
func TestDockerRecorderCopyContract(t *testing.T) {
	if os.Getenv("FRANKENGATE_DOCKER_ARTIFACT_TEST") != "1" {
		t.Skip("real Docker artifact characterization is an explicit CI gate")
	}
	binary := []byte("synthetic network recorder")
	var rootfs bytes.Buffer
	writer := tar.NewWriter(&rootfs)
	if err := writer.WriteHeader(&tar.Header{Name: recorderBinaryPath, Mode: 0o555, Size: int64(len(binary)), Typeflag: tar.TypeReg}); err != nil {
		t.Fatal(err)
	}
	if _, err := writer.Write(binary); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}

	importCommand := exec.Command("docker", "import", "--change", `CMD ["/network-recorder"]`, "-")
	importCommand.Stdin = bytes.NewReader(rootfs.Bytes())
	imageOutput, err := importCommand.CombinedOutput()
	if err != nil {
		t.Fatalf("docker import scratch recorder fixture: %v: %s", err, imageOutput)
	}
	imageID := strings.TrimSpace(string(imageOutput))
	if !strings.HasPrefix(imageID, "sha256:") {
		t.Fatalf("docker import returned noncanonical image identity %q", imageID)
	}
	t.Cleanup(func() {
		if output, err := exec.Command("docker", "image", "rm", "--force", imageID).CombinedOutput(); err != nil {
			t.Errorf("remove Docker characterization image: %v: %s", err, output)
		}
	})

	createOutput, err := exec.Command("docker", "create", "--network", "none", "--read-only", imageID).CombinedOutput()
	if err != nil {
		t.Fatalf("docker create scratch recorder fixture: %v: %s", err, createOutput)
	}
	containerID := strings.TrimSpace(string(createOutput))
	if !canonicalContainerID.MatchString(containerID) {
		t.Fatalf("docker create returned noncanonical container identity %q", containerID)
	}
	t.Cleanup(func() {
		if output, err := exec.Command("docker", "rm", "--force", containerID).CombinedOutput(); err != nil {
			t.Errorf("remove Docker characterization container: %v: %s", err, output)
		}
	})

	archive, err := exec.Command("docker", "cp", containerID+":/"+recorderBinaryPath, "-").Output()
	if err != nil {
		t.Fatal(err)
	}
	extracted, err := extractRecorderBinary(archive)
	if err != nil {
		t.Fatalf("real Docker recorder copy violates extraction contract: %v", err)
	}
	if !bytes.Equal(extracted, binary) {
		t.Fatalf("real Docker recorder copy changed recorder bytes")
	}
}
