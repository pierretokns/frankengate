package main

import (
	"archive/tar"
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/maximhq/bifrost/tests/conformance/lab/contract"
)

const (
	maxRecorderPolicyBytes  = 1 << 20
	maxRecorderArchiveBytes = 32 << 20
	maxRecorderBinaryBytes  = 16 << 20
	maxRecorderTarEntries   = 256
	recorderBinaryPath      = "network-recorder"
)

var canonicalContainerID = regexp.MustCompile(`^[0-9a-f]{64}$`)

type boundedWriter struct {
	buffer bytes.Buffer
	limit  int
}

func (writer *boundedWriter) Write(data []byte) (int, error) {
	if len(data) > writer.limit-writer.buffer.Len() {
		return 0, errors.New("recorder artifact archive exceeds bounded contract")
	}
	return writer.buffer.Write(data)
}

func verifyPinnedRecorderArtifacts(executor commandExecutor, environment []string, stderr io.Writer, dockerBinary, policyPath, nativePlatform string, lock contract.RuntimeLock) (returnErr error) {
	if policyPath == "" || !filepath.IsAbs(policyPath) {
		return errors.New("runtime-lock/v2 requires an absolute recorder policy path")
	}
	policy, err := readBoundedFile(policyPath, maxRecorderPolicyBytes)
	if err != nil {
		return fmt.Errorf("read recorder policy: %w", err)
	}
	recorder, ok := lock.NetworkRecorderImage()
	if !ok {
		return errors.New("runtime lock does not expose a validated recorder image")
	}
	containerName := "fg-recorder-extract-" + lock.RunID
	ownershipToken, err := recorderOwnershipToken()
	if err != nil {
		return fmt.Errorf("create recorder extraction ownership token: %w", err)
	}
	var created bytes.Buffer
	if err := executor.Run(environment, &created, stderr, dockerBinary, "create", "--name", containerName, "--label", "frankengate.sealed-lab.run="+lock.RunID, "--label", "frankengate.sealed-lab.extract="+ownershipToken, "--network", "none", "--read-only", recorder.Reference); err != nil {
		createErr := fmt.Errorf("create pinned recorder extraction container: %w", err)
		if cleanupErr := removeOwnedRecorderContainer(executor, environment, stderr, dockerBinary, containerName, lock.RunID, ownershipToken, recorder.Reference); cleanupErr != nil {
			return errors.Join(createErr, fmt.Errorf("resolve ambiguous recorder create: %w", cleanupErr))
		}
		return createErr
	}
	containerID := strings.TrimSpace(created.String())
	if !canonicalContainerID.MatchString(containerID) {
		identityErr := errors.New("Docker did not return a canonical recorder extraction container identity")
		if cleanupErr := removeOwnedRecorderContainer(executor, environment, stderr, dockerBinary, containerName, lock.RunID, ownershipToken, recorder.Reference); cleanupErr != nil {
			return errors.Join(identityErr, cleanupErr)
		}
		return identityErr
	}
	removed := false
	defer func() {
		if !removed {
			if err := executor.Run(environment, io.Discard, stderr, dockerBinary, "rm", "--force", containerID); err != nil {
				cleanupErr := fmt.Errorf("remove recorder extraction container: %w", err)
				if returnErr == nil {
					returnErr = cleanupErr
				} else {
					returnErr = errors.Join(returnErr, cleanupErr)
				}
			}
		}
	}()
	archive := &boundedWriter{limit: maxRecorderArchiveBytes}
	if err := executor.Run(environment, archive, stderr, dockerBinary, "cp", containerID+":/"+recorderBinaryPath, "-"); err != nil {
		return fmt.Errorf("copy pinned recorder executable: %w", err)
	}
	binary, err := extractRecorderBinary(archive.buffer.Bytes())
	if err != nil {
		return err
	}
	if err := lock.VerifyRecorderArtifacts(policy, nativePlatform, binary); err != nil {
		return fmt.Errorf("verify pinned recorder artifacts: %w", err)
	}
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, "rm", "--force", containerID); err != nil {
		return fmt.Errorf("remove recorder extraction container: %w", err)
	}
	removed = true
	return nil
}

func recorderOwnershipToken() (string, error) {
	value := make([]byte, 32)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

func removeOwnedRecorderContainer(executor commandExecutor, environment []string, stderr io.Writer, dockerBinary, containerName, runID, ownershipToken, imageReference string) error {
	var inspected bytes.Buffer
	format := `{{.Id}}{{"\t"}}{{index .Config.Labels "frankengate.sealed-lab.run"}}{{"\t"}}{{index .Config.Labels "frankengate.sealed-lab.extract"}}{{"\t"}}{{.Config.Image}}`
	if err := executor.Run(environment, &inspected, stderr, dockerBinary, "inspect", "--type", "container", "--format", format, containerName); err != nil {
		return fmt.Errorf("inspect recorder extraction ownership: %w", err)
	}
	fields := strings.Split(strings.TrimSpace(inspected.String()), "\t")
	if len(fields) != 4 || !canonicalContainerID.MatchString(fields[0]) || fields[1] != runID || fields[2] != ownershipToken || fields[3] != imageReference {
		return errors.New("recorder extraction name is not owned by this invocation")
	}
	if err := executor.Run(environment, io.Discard, stderr, dockerBinary, "rm", "--force", fields[0]); err != nil {
		return fmt.Errorf("remove owned recorder extraction container: %w", err)
	}
	return nil
}

func readBoundedFile(path string, limit int) ([]byte, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, int64(limit)+1))
	if err != nil {
		return nil, err
	}
	if len(data) == 0 || len(data) > limit {
		return nil, errors.New("artifact is empty or exceeds its bounded contract")
	}
	return data, nil
}

func extractRecorderBinary(archive []byte) ([]byte, error) {
	reader := tar.NewReader(bytes.NewReader(archive))
	var binary []byte
	for entries := 0; ; entries++ {
		if entries >= maxRecorderTarEntries {
			return nil, errors.New("recorder artifact archive contains too many entries")
		}
		header, err := reader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read recorder artifact archive: %w", err)
		}
		rawName := filepath.ToSlash(header.Name)
		name := strings.TrimPrefix(rawName, "./")
		if header.Typeflag == tar.TypeDir && strings.HasSuffix(name, "/") {
			name = strings.TrimSuffix(name, "/")
		}
		if strings.HasPrefix(rawName, "/") || name == "" || path.Clean(name) != name || strings.Contains(name, "\\") {
			return nil, fmt.Errorf("recorder artifact archive contains noncanonical path %q", rawName)
		}
		if name != recorderBinaryPath {
			if header.Typeflag == tar.TypeDir && header.Mode&0o7022 == 0 && header.Uid == 0 && header.Gid == 0 {
				continue
			}
			return nil, fmt.Errorf("recorder scratch image contains unexpected entry %q", name)
		}
		if binary != nil || !header.FileInfo().Mode().IsRegular() || header.Size <= 0 || header.Size > maxRecorderBinaryBytes || header.Mode&0o7777 != 0o555 || header.Uid != 0 || header.Gid != 0 {
			return nil, errors.New("recorder image contains an invalid or duplicate executable")
		}
		binary, err = io.ReadAll(io.LimitReader(reader, maxRecorderBinaryBytes+1))
		if err != nil || len(binary) == 0 || len(binary) > maxRecorderBinaryBytes || int64(len(binary)) != header.Size {
			return nil, errors.New("recorder executable size does not match artifact archive header")
		}
	}
	if binary == nil {
		return nil, errors.New("recorder artifact archive omits /network-recorder")
	}
	return binary, nil
}
