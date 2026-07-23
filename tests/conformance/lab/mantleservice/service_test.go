package mantleservice_test

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/tests/conformance/lab/mantleservice"
)

func newServer(t *testing.T) *httptest.Server {
	t.Helper()
	service, err := mantleservice.New()
	if err != nil {
		t.Fatalf("new service: %v", err)
	}
	server := httptest.NewServer(service)
	t.Cleanup(server.Close)
	return server
}

func request(t *testing.T, server *httptest.Server, method, path, body string) *http.Response {
	t.Helper()
	req, err := http.NewRequest(method, server.URL+path, strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Authorization", "Bearer synthetic-mantle-contract")
	req.Header.Set("Content-Type", "application/json")
	response, err := server.Client().Do(req)
	if err != nil {
		t.Fatalf("request %s: %v", path, err)
	}
	return response
}

func errorCode(t *testing.T, response *http.Response) string {
	t.Helper()
	defer response.Body.Close()
	var envelope struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if err := json.NewDecoder(response.Body).Decode(&envelope); err != nil {
		t.Fatalf("decode error: %v", err)
	}
	return envelope.Error.Code
}

func TestPublicBoundaryUsesExactAuthorityScopedRoutes(t *testing.T) {
	server := newServer(t)
	tests := []struct {
		name, model, path string
		status            int
	}{
		{"gpt 5.4 exceptional", "openai.gpt-5.4", "/openai/v1/responses", http.StatusOK},
		{"gpt 5.5 exceptional", "openai.gpt-5.5", "/openai/v1/responses", http.StatusOK},
		{"gpt 5.6 route observation", "openai.gpt-5.6-sol", "/openai/v1/responses", http.StatusUnauthorized},
		{"gpt 5.6 luna route observation", "openai.gpt-5.6-luna", "/openai/v1/responses", http.StatusUnauthorized},
		{"gpt 5.6 terra route observation", "openai.gpt-5.6-terra", "/openai/v1/responses", http.StatusUnauthorized},
		{"gpt oss generic", "openai.gpt-oss-120b", "/v1/responses", http.StatusOK},
		{"gpt oss 20b generic", "openai.gpt-oss-20b", "/v1/responses", http.StatusOK},
		{"gpt 5.5 forbidden generic", "openai.gpt-5.5", "/v1/responses", http.StatusNotFound},
		{"gpt oss forbidden exceptional", "openai.gpt-oss-120b", "/openai/v1/responses", http.StatusNotFound},
		{"unknown resembles family", "openai.gpt-5.50", "/openai/v1/responses", http.StatusNotFound},
		{"client provider prefix rejected", "bedrock_mantle/openai.gpt-5.5", "/openai/v1/responses", http.StatusNotFound},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			response := request(t, server, http.MethodPost, test.path, `{"model":"`+test.model+`","input":"hello"}`)
			defer response.Body.Close()
			if response.StatusCode != test.status {
				body, _ := io.ReadAll(response.Body)
				t.Fatalf("status=%d want=%d body=%s", response.StatusCode, test.status, body)
			}
		})
	}
}

func TestModelsAreDeterministicWithinDeclaredCoverage(t *testing.T) {
	server := newServer(t)
	response := request(t, server, http.MethodGet, "/v1/models", "")
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("status=%d", response.StatusCode)
	}
	var result struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		t.Fatal(err)
	}
	got := make([]string, 0, len(result.Data))
	for _, model := range result.Data {
		got = append(got, model.ID)
	}
	want := []string{"openai.gpt-5.4", "openai.gpt-5.5", "openai.gpt-5.6-luna", "openai.gpt-5.6-sol", "openai.gpt-5.6-terra", "openai.gpt-oss-120b", "openai.gpt-oss-20b"}
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("models=%v want=%v", got, want)
	}
}

func TestObservedGPT56RowsCanOnlyReplayLockedAccessDenied(t *testing.T) {
	server := newServer(t)
	for _, model := range []string{"openai.gpt-5.6-luna", "openai.gpt-5.6-sol", "openai.gpt-5.6-terra"} {
		for _, stream := range []string{"false", "true"} {
			response := request(t, server, http.MethodPost, "/openai/v1/responses", `{"model":"`+model+`","input":"hello","stream":`+stream+`}`)
			if response.StatusCode != http.StatusUnauthorized || errorCode(t, response) != "access_denied" {
				t.Fatalf("%s stream=%s exceeded observation authority", model, stream)
			}
		}
	}
}

func TestResponsesUnaryIsByteDeterministicAndHeaderAgnostic(t *testing.T) {
	server := newServer(t)
	body := `{"model":"openai.gpt-5.5","input":[{"role":"user","content":"hello"}]}`
	first := request(t, server, http.MethodPost, "/openai/v1/responses", body)
	firstBytes, _ := io.ReadAll(first.Body)
	first.Body.Close()
	req, _ := http.NewRequest(http.MethodPost, server.URL+"/openai/v1/responses", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer synthetic-mantle-contract")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-openai-internal-codex-responses-lite", "true")
	second, err := server.Client().Do(req)
	if err != nil {
		t.Fatal(err)
	}
	secondBytes, _ := io.ReadAll(second.Body)
	second.Body.Close()
	if first.StatusCode != http.StatusOK || second.StatusCode != http.StatusOK || !bytes.Equal(firstBytes, secondBytes) {
		t.Fatalf("Responses output depends on failed remapping header:\n%s\n%s", firstBytes, secondBytes)
	}
}

func TestPublicResponsesMatchReviewedGoldenBytes(t *testing.T) {
	server := newServer(t)
	for _, test := range []struct{ name, body, golden string }{
		{"unary", `{"model":"openai.gpt-5.5","input":"golden"}`, "response.golden.json"},
		{"stream", `{"model":"openai.gpt-5.5","input":"golden","stream":true}`, "responses-stream.golden.sse"},
		{"chat", `{"model":"openai.gpt-oss-120b","messages":[{"role":"user","content":"golden"}]}`, "chat.golden.json"},
	} {
		t.Run(test.name, func(t *testing.T) {
			path := "/openai/v1/responses"
			if test.name == "chat" {
				path = "/v1/chat/completions"
			}
			response := request(t, server, http.MethodPost, path, test.body)
			defer response.Body.Close()
			got, err := io.ReadAll(response.Body)
			if err != nil {
				t.Fatal(err)
			}
			want, err := os.ReadFile(filepath.Join("testdata", test.golden))
			if err != nil {
				t.Fatal(err)
			}
			if test.name == "stream" {
				want = append(want, '\n')
			}
			if !bytes.Equal(got, want) {
				t.Fatalf("response drifted from reviewed golden\ngot: %s\nwant: %s", got, want)
			}
		})
	}
}

func TestResponsesSSEHasOneOrderedTerminal(t *testing.T) {
	server := newServer(t)
	response := request(t, server, http.MethodPost, "/openai/v1/responses", `{"model":"openai.gpt-5.5","input":"hello","stream":true}`)
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK || response.Header.Get("Content-Type") != "text/event-stream" {
		t.Fatalf("status/type=%d/%q", response.StatusCode, response.Header.Get("Content-Type"))
	}
	scanner := bufio.NewScanner(response.Body)
	var types []string
	var sequences []int
	for scanner.Scan() {
		if !strings.HasPrefix(scanner.Text(), "data: ") {
			continue
		}
		var event struct {
			Type     string `json:"type"`
			Sequence int    `json:"sequence_number"`
		}
		if err := json.Unmarshal([]byte(strings.TrimPrefix(scanner.Text(), "data: ")), &event); err != nil {
			t.Fatal(err)
		}
		types = append(types, event.Type)
		sequences = append(sequences, event.Sequence)
	}
	if err := scanner.Err(); err != nil {
		t.Fatal(err)
	}
	wantTypes := "response.created,response.output_item.added,response.content_part.added,response.output_text.delta,response.output_text.done,response.content_part.done,response.output_item.done,response.completed"
	if strings.Join(types, ",") != wantTypes || len(sequences) != 8 {
		t.Fatalf("events=%v sequences=%v", types, sequences)
	}
	for index, sequence := range sequences {
		if sequence != index {
			t.Fatalf("sequence[%d]=%d", index, sequence)
		}
	}
}

func TestChatOnlyOnExplicitlySupportedRow(t *testing.T) {
	server := newServer(t)
	unsupported := request(t, server, http.MethodPost, "/openai/v1/chat/completions", `{"model":"openai.gpt-5.5","messages":[{"role":"user","content":"hello"}]}`)
	if unsupported.StatusCode != http.StatusBadRequest || errorCode(t, unsupported) != "unsupported_operation" {
		t.Fatal("GPT-5.5 chat did not fail closed")
	}
	supported := request(t, server, http.MethodPost, "/v1/chat/completions", `{"model":"openai.gpt-oss-120b","messages":[{"role":"user","content":"hello"}]}`)
	defer supported.Body.Close()
	if supported.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(supported.Body)
		t.Fatalf("GPT OSS chat status=%d body=%s", supported.StatusCode, body)
	}
	streaming := request(t, server, http.MethodPost, "/v1/chat/completions", `{"model":"openai.gpt-oss-20b","messages":[{"role":"user","content":"hello"}],"stream":true}`)
	if streaming.StatusCode != http.StatusBadRequest || errorCode(t, streaming) != "streaming_not_covered" {
		t.Fatal("explicit Chat streaming exclusion was not enforced")
	}
}

func TestMalformedTargetsAuthAndMediaTypeFailClosed(t *testing.T) {
	server := newServer(t)
	for _, path := range []string{"/openai/openai/v1/responses", "/openai//v1/responses", "/openai/v1/responses?model=openai.gpt-5.5"} {
		response := request(t, server, http.MethodPost, path, `{"model":"openai.gpt-5.5","input":"hello"}`)
		if response.StatusCode != http.StatusNotFound {
			response.Body.Close()
			t.Fatalf("path %q status=%d", path, response.StatusCode)
		}
		response.Body.Close()
	}
	req, _ := http.NewRequest(http.MethodPost, server.URL+"/openai/v1/responses", strings.NewReader(`{"model":"openai.gpt-5.5","input":"hello"}`))
	req.Header.Set("Content-Type", "application/json")
	response, err := server.Client().Do(req)
	if err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusUnauthorized || errorCode(t, response) != "invalid_auth" {
		t.Fatal("missing auth did not fail closed")
	}
	for _, authorization := range []string{"Bearer synthetic-", "Bearer synthetic-mantle-contract extra", "Bearer synthetic-other", "Bearer real-credential"} {
		req, _ := http.NewRequest(http.MethodPost, server.URL+"/openai/v1/responses", strings.NewReader(`{"model":"openai.gpt-5.5","input":"hello"}`))
		req.Header.Set("Authorization", authorization)
		req.Header.Set("Content-Type", "application/json")
		response, err := server.Client().Do(req)
		if err != nil {
			t.Fatal(err)
		}
		if response.StatusCode != http.StatusUnauthorized || errorCode(t, response) != "invalid_auth" {
			t.Fatalf("authorization %q did not fail closed", authorization)
		}
	}
	duplicate, _ := http.NewRequest(http.MethodPost, server.URL+"/openai/v1/responses", strings.NewReader(`{"model":"openai.gpt-5.5","input":"hello"}`))
	duplicate.Header.Add("Authorization", "Bearer synthetic-mantle-contract")
	duplicate.Header.Add("Authorization", "Bearer synthetic-mantle-contract")
	duplicate.Header.Set("Content-Type", "application/json")
	response, err = server.Client().Do(duplicate)
	if err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusUnauthorized || errorCode(t, response) != "invalid_auth" {
		t.Fatal("duplicate Authorization values accepted")
	}
	for name, body := range map[string]string{
		"duplicate model":  `{"model":"openai.gpt-5.5","model":"openai.gpt-5.4","input":"hello"}`,
		"unknown field":    `{"model":"openai.gpt-5.5","input":"hello","temperature":1}`,
		"null input":       `{"model":"openai.gpt-5.5","input":null}`,
		"nested duplicate": `{"model":"openai.gpt-5.5","input":{"x":1,"x":2}}`,
	} {
		t.Run(name, func(t *testing.T) {
			response := request(t, server, http.MethodPost, "/openai/v1/responses", body)
			if response.StatusCode != http.StatusBadRequest || errorCode(t, response) != "invalid_request" {
				t.Fatalf("malformed body accepted")
			}
		})
	}
}

func TestCoverageManifestCarriesRequiredProvenanceAndCapabilities(t *testing.T) {
	service, err := mantleservice.New()
	if err != nil {
		t.Fatal(err)
	}
	coverage := service.Coverage()
	if coverage.Schema != "bedrock-mantle-openai-service-coverage/v1" || len(coverage.SourceLockSHA256) != 64 || len(coverage.Sources) != 5 || len(coverage.ModelRoutes) != 2 || len(coverage.Omissions) != 3 || len(coverage.Discrepancies) != 1 || len(coverage.Rows) != 7 {
		t.Fatalf("coverage=%#v", coverage)
	}
	omissions := map[string]bool{}
	for _, omission := range coverage.Omissions {
		omissions[omission.ID] = omission.Subject != "" && omission.Reason != ""
	}
	for _, required := range []string{"anthropic-separate-surface", "chat-streaming-excluded", "gemma-4-missing-authority"} {
		if !omissions[required] {
			t.Fatalf("missing machine-readable omission %q", required)
		}
	}
	for _, discrepancy := range coverage.Discrepancies {
		if discrepancy.ID == "" || discrepancy.Status == "" || discrepancy.Resolution == "" || len(discrepancy.SourceIDs) < 2 {
			t.Fatalf("incomplete discrepancy=%#v", discrepancy)
		}
	}
	for _, route := range coverage.ModelRoutes {
		if route.Method != http.MethodGet || route.Path == "" || route.Auth == "" || route.ContentType != "application/json" || route.EventGrammar != "openai-model-list-json" || route.SourceID == "" {
			t.Fatalf("incomplete Models route=%#v", route)
		}
	}
	for _, row := range coverage.Rows {
		if row.ModelID == "" || row.Revision == "" || row.Method != http.MethodPost || row.Path == "" || row.Auth == "" || row.ContentType != "application/json" || row.SourceID == "" || row.Authority == "" {
			t.Fatalf("incomplete row=%#v", row)
		}
		if (row.ModelID == "openai.gpt-5.4" || row.ModelID == "openai.gpt-5.5") && (row.Path != "/openai/v1/responses" || row.Chat) {
			t.Fatalf("frontier route drift=%#v", row)
		}
		if strings.HasPrefix(row.ModelID, "openai.gpt-5.6-") && (row.Authority != "aws-observed-sample" || row.Responses || row.ResponsesEventGrammar != "" || row.ExpectedStatus != http.StatusUnauthorized || row.ExpectedErrorCode != "access_denied") {
			t.Fatalf("GPT-5.6 observation authority escalated into success=%#v", row)
		}
		if row.Chat != (row.ChatPath != "") {
			t.Fatalf("inferred rather than explicit Chat route=%#v", row)
		}
		if row.ChatStreaming {
			t.Fatalf("Chat streaming unexpectedly claimed=%#v", row)
		}
	}
}

func TestCoverageIsCryptographicallyBoundToCanonicalSourceLock(t *testing.T) {
	service, err := mantleservice.New()
	if err != nil {
		t.Fatal(err)
	}
	coverage := service.Coverage()
	data, err := os.ReadFile(filepath.Join("..", "..", "bedrock", "sources", "source-lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(data)
	if got := fmt.Sprintf("%x", digest); got != coverage.SourceLockSHA256 {
		t.Fatalf("source lock digest=%s coverage=%s", got, coverage.SourceLockSHA256)
	}
	var lock struct {
		Sources []struct {
			ID             string `json:"id"`
			AuthorityClass string `json:"authority_class"`
			ArtifactDigest string `json:"artifact_digest"`
		} `json:"sources"`
	}
	if err := json.Unmarshal(data, &lock); err != nil {
		t.Fatal(err)
	}
	locked := map[string]struct{ authority, digest string }{}
	for _, source := range lock.Sources {
		locked[source.ID] = struct{ authority, digest string }{source.AuthorityClass, source.ArtifactDigest}
	}
	for _, source := range coverage.Sources {
		if locked[source.ID].digest != source.ArtifactDigest || locked[source.ID].authority != source.AuthorityClass {
			t.Fatalf("coverage source %q does not match locked authority/digest", source.ID)
		}
	}
	observation, err := os.ReadFile(filepath.Join("..", "..", "bedrock", "observations", "mantle-frontier-access-denied.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	observationDigest := sha256.Sum256(observation)
	wantObservation := locked["mantle-frontier-observation-2026-07-21"].digest
	if got := "sha256:" + fmt.Sprintf("%x", observationDigest); got != wantObservation {
		t.Fatalf("observation digest=%s lock=%s", got, wantObservation)
	}
}
