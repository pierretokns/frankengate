// Command pricingsync fetches a public model-pricing document and publishes a
// validated, timestamped, last-known-good copy for FrankenGate's site.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const defaultURL = "https://getbifrost.ai/datasheet"

type artifact struct {
	Brand       string          `json:"brand"`
	Source      string          `json:"source"`
	RetrievedAt string          `json:"retrieved_at"`
	Models      json.RawMessage `json:"models"`
}

func fetch(ctx context.Context, client *http.Client, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("upstream returned %s", resp.Status)
	}
	b, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if err != nil {
		return nil, err
	}
	if len(bytes.TrimSpace(b)) == 0 {
		return nil, errors.New("upstream returned an empty document")
	}
	return b, nil
}

// validate accepts both the common map-of-models format and an object with a
// models field. Every model entry must be an object; malformed data is never
// allowed to replace the last-known-good cache.
func validate(raw []byte) (json.RawMessage, error) {
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	obj, ok := value.(map[string]any)
	if !ok || len(obj) == 0 {
		return nil, errors.New("pricing document must be a non-empty JSON object")
	}
	models := value
	if m, exists := obj["models"]; exists {
		if _, ok := m.(map[string]any); !ok {
			return nil, errors.New("models must be an object")
		}
		models = m
	}
	entries, ok := models.(map[string]any)
	if !ok || len(entries) == 0 {
		return nil, errors.New("pricing document contains no model entries")
	}
	for name, entry := range entries {
		if strings.TrimSpace(name) == "" {
			return nil, errors.New("pricing document contains an empty model name")
		}
		if _, ok := entry.(map[string]any); !ok {
			return nil, fmt.Errorf("model %q is not an object", name)
		}
	}
	// Canonicalize whitespace and map ordering through a second marshal.
	b, err := json.Marshal(value)
	return b, err
}

func atomicWrite(name string, data []byte) error {
	if err := os.MkdirAll(filepath.Dir(name), 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(name), ".pricing-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err = tmp.Chmod(0o644); err == nil {
		_, err = tmp.Write(data)
	}
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	return os.Rename(tmpName, name)
}

func publish(dir, source string, raw []byte, now time.Time) error {
	stamp := now.UTC().Format("20060102T150405Z")
	archive := filepath.Join(dir, "archive", "pricing-"+stamp+".json")
	if err := atomicWrite(archive, raw); err != nil {
		return err
	}
	a := artifact{Brand: "FrankenGate", Source: source, RetrievedAt: now.UTC().Format(time.RFC3339), Models: raw}
	wrapped, err := json.MarshalIndent(a, "", "  ")
	if err != nil {
		return err
	}
	wrapped = append(wrapped, '\n')
	if err := atomicWrite(filepath.Join(dir, "latest.json"), wrapped); err != nil {
		return err
	}
	return atomicWrite(filepath.Join(dir, "latest-upstream.json"), append(raw, '\n'))
}

func main() {
	url := flag.String("url", defaultURL, "public pricing URL")
	out := flag.String("out", "pricing-cache", "cache output directory")
	timeout := flag.Duration("timeout", 30*time.Second, "HTTP timeout")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()
	raw, err := fetch(ctx, &http.Client{Timeout: *timeout}, *url)
	if err != nil {
		fmt.Fprintln(os.Stderr, "pricing sync failed (cache preserved):", err)
		os.Exit(1)
	}
	raw, err = validate(raw)
	if err != nil {
		fmt.Fprintln(os.Stderr, "pricing sync rejected (cache preserved):", err)
		os.Exit(1)
	}
	if err = publish(*out, *url, raw, time.Now()); err != nil {
		fmt.Fprintln(os.Stderr, "pricing publish failed:", err)
		os.Exit(1)
	}
	f, _ := os.ReadDir(filepath.Join(*out, "archive"))
	sort.Slice(f, func(i, j int) bool { return f[i].Name() < f[j].Name() })
	fmt.Printf("published %s (%d archived snapshots)\n", filepath.Join(*out, "latest.json"), len(f))
}
