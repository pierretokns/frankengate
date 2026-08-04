// Package registry contains bounded adapters for untrusted agent/MCP registry
// manifests. A parsed manifest is evidence for catalog review, never routing
// authorization or a credential source.
package registry

import (
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
)

const (
	MaxManifestBytes = 256 * 1024
	MaxEntries       = 256
)

type Manifest struct {
	SchemaVersion string  `json:"schema_version"`
	Repository    string  `json:"repository"`
	Revision      string  `json:"revision"`
	License       string  `json:"license"`
	Entries       []Entry `json:"entries"`
}

type Entry struct {
	ID          string     `json:"id"`
	Name        string     `json:"name"`
	Version     string     `json:"version"`
	Description string     `json:"description,omitempty"`
	Source      string     `json:"source"`
	Digest      string     `json:"digest"`
	Transport   *Transport `json:"transport,omitempty"`
	Publisher   string     `json:"publisher,omitempty"`
}

type Transport struct {
	Type    string            `json:"type"`
	URL     string            `json:"url"`
	Headers map[string]string `json:"headers,omitempty"`
}

func Parse(data []byte) (Manifest, error) {
	if len(data) == 0 || len(data) > MaxManifestBytes {
		return Manifest{}, fmt.Errorf("registry manifest exceeds %d bytes or is empty", MaxManifestBytes)
	}
	var manifest Manifest
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&manifest); err != nil {
		return Manifest{}, fmt.Errorf("decode registry manifest: %w", err)
	}
	if err := manifest.Validate(); err != nil {
		return Manifest{}, err
	}
	return manifest, nil
}

func (m Manifest) Validate() error {
	if strings.TrimSpace(m.SchemaVersion) == "" || strings.TrimSpace(m.Repository) == "" || strings.TrimSpace(m.Revision) == "" {
		return fmt.Errorf("schema_version, repository, and immutable revision are required")
	}
	if len(m.Entries) > MaxEntries {
		return fmt.Errorf("registry manifest contains more than %d entries", MaxEntries)
	}
	if m.License == "" {
		return fmt.Errorf("registry license is required")
	}
	for i, entry := range m.Entries {
		if entry.ID == "" || entry.Name == "" || entry.Version == "" || entry.Source == "" || entry.Digest == "" {
			return fmt.Errorf("entries[%d] requires id, name, version, source, and digest", i)
		}
		if !strings.HasPrefix(entry.Digest, "sha256:") || len(entry.Digest) != len("sha256:")+64 {
			return fmt.Errorf("entries[%d].digest must be a sha256 hex digest", i)
		}
		if entry.Transport != nil {
			if err := validateTransport(*entry.Transport); err != nil {
				return fmt.Errorf("entries[%d].transport: %w", i, err)
			}
		}
	}
	return nil
}

func validateTransport(transport Transport) error {
	if transport.Type == "" || transport.URL == "" {
		return fmt.Errorf("type and url are required")
	}
	parsed, err := url.Parse(transport.URL)
	if err != nil || parsed.User != nil || parsed.Host == "" {
		return fmt.Errorf("url must be an absolute URL without userinfo")
	}
	if parsed.Scheme != "https" && parsed.Scheme != "http" {
		return fmt.Errorf("url scheme %q is not supported", parsed.Scheme)
	}
	for key := range transport.Headers {
		if key == "Authorization" || strings.EqualFold(key, "Cookie") || strings.ContainsAny(key, "\r\n") {
			return fmt.Errorf("credential or unsafe header %q is not allowed", key)
		}
	}
	return nil
}
