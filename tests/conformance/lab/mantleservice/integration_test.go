package mantleservice_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/tests/conformance/lab/mantleservice"
)

func TestIntegrationHandlerPreservesAuthorityPathAndSecretFreeTranscript(t *testing.T) {
	var transcript bytes.Buffer
	handler, err := mantleservice.NewIntegrationHandler(&transcript)
	if err != nil {
		t.Fatal(err)
	}
	body := `{"model":"openai.gpt-5.5","input":"sealed-c9-gpt55 SEALED_CODEX_RUN_ID:test-1","stream":true}`
	request := httptest.NewRequest(http.MethodPost, "https://"+mantleservice.IntegrationHost+"/openai/v1/responses", strings.NewReader(body))
	request.Host = mantleservice.IntegrationHost
	request.Header.Set("Authorization", "Bearer synthetic-mantle-contract")
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "response.completed") {
		t.Fatalf("response=%d %s", response.Code, response.Body.String())
	}
	var record mantleservice.TranscriptRecord
	if err := json.NewDecoder(&transcript).Decode(&record); err != nil {
		t.Fatal(err)
	}
	if record.Schema != mantleservice.TranscriptSchema || record.RunID != "test-1" || record.Sequence != 1 || record.Host != mantleservice.IntegrationHost || record.Path != "/openai/v1/responses" || record.Model != "openai.gpt-5.5" || !record.Stream || record.Status != http.StatusOK || len(record.BodySHA256) != 64 || record.Authorization != "synthetic-bearer" {
		t.Fatalf("transcript=%#v", record)
	}
	if strings.Contains(transcript.String(), "synthetic-mantle-contract") || strings.Contains(transcript.String(), "sealed-c9-gpt55") {
		t.Fatalf("transcript leaked credential or body: %s", transcript.String())
	}
}

func TestIntegrationHandlerRejectsAuthoritySubstitutionWithoutTranscriptCredit(t *testing.T) {
	var transcript bytes.Buffer
	handler, err := mantleservice.NewIntegrationHandler(&transcript)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodPost, "https://mantle.invalid/openai/v1/responses", strings.NewReader(`{"model":"openai.gpt-5.5","input":"x"}`))
	request.Host = "mantle.invalid"
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusNotFound || transcript.Len() != 0 {
		t.Fatalf("wrong authority earned transcript credit: status=%d transcript=%q", response.Code, transcript.String())
	}
}
