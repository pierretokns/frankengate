package server

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCloudflareEmailSenderSendsAuthenticatedJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.Header.Get("Authorization") != "Bearer token" {
			t.Fatalf("unexpected request: method=%s authorization=%q", r.Method, r.Header.Get("Authorization"))
		}
		body, err := io.ReadAll(r.Body)
		if err != nil || !strings.Contains(string(body), `"from":"alerts@example.com"`) || !strings.Contains(string(body), `"to":["ops@example.com"]`) {
			t.Fatalf("unexpected JSON body: %s (err=%v)", body, err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	sender := cloudflareEmailSender{client: server.Client(), endpoint: server.URL, token: "token"}
	if err := sender.Send(context.Background(), "alerts@example.com", []string{"ops@example.com"}, "subject", "body"); err != nil {
		t.Fatalf("send failed: %v", err)
	}
}

func TestCloudflareEmailSenderFailsOnProviderError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()
	sender := cloudflareEmailSender{client: server.Client(), endpoint: server.URL, token: "token"}
	if err := sender.Send(context.Background(), "a@example.com", []string{"b@example.com"}, "subject", "body"); err == nil {
		t.Fatal("expected provider error")
	}
}
