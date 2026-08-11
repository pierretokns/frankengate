package a2apush

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestHTTPDeliverySendsBearerAndIdempotencyMetadata(t *testing.T) {
	var got http.Header
	var body string
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Clone()
		bytes, _ := io.ReadAll(r.Body)
		body = string(bytes)
		w.WriteHeader(http.StatusAccepted)
	}))
	defer server.Close()

	delivery := HTTPDelivery{
		Client:  server.Client(),
		Secrets: SecretResolverFunc(func(_ context.Context, ref string) (string, error) { return "bearer-secret-1", nil }),
		Policy:  localHTTPDeliveryPolicy(server),
	}
	request := DeliveryRequest{
		Config:  Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: server.URL, AuthScheme: "bearer", CredentialRef: "vault://tenant-1/push"},
		Payload: []byte(`{"task":"task-1"}`), DeliveryID: "delivery-1", Attempt: 2,
	}
	request.PayloadHash = PayloadDigest(request.Payload)
	if err := delivery.Deliver(context.Background(), request); err != nil {
		t.Fatalf("deliver: %v", err)
	}
	if got.Get("Authorization") != "Bearer bearer-secret-1" || got.Get("Idempotency-Key") != "delivery-1" || got.Get("X-A2A-Attempt") != "2" {
		t.Fatalf("delivery headers = %#v", got)
	}
	if got.Get("X-A2A-Payload-SHA256") != request.PayloadHash || body != string(request.Payload) {
		t.Fatalf("delivery body/metadata hash mismatch: body=%q headers=%#v", body, got)
	}
}

func TestHTTPDeliverySignsHMACAndNotificationToken(t *testing.T) {
	var got http.Header
	var body []byte
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Clone()
		body, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	now := time.Unix(1_735_000_000, 0).UTC()
	delivery := HTTPDelivery{
		Client: server.Client(), Secrets: SecretResolverFunc(func(_ context.Context, ref string) (string, error) {
			switch ref {
			case "vault://sign":
				return "signing-secret-1", nil
			case "vault://notify":
				return "notification-token-1", nil
			default:
				return "", context.Canceled
			}
		}), Policy: localHTTPDeliveryPolicy(server), Now: func() time.Time { return now },
	}
	request := DeliveryRequest{
		Config:  Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: server.URL, AuthScheme: "hmac-sha256", SigningSecretRef: "vault://sign", NotificationTokenRef: "vault://notify"},
		Payload: []byte(`{"state":"completed"}`), DeliveryID: "delivery-2", Attempt: 1,
	}
	request.PayloadHash = PayloadDigest(request.Payload)
	if err := delivery.Deliver(context.Background(), request); err != nil {
		t.Fatalf("deliver: %v", err)
	}
	if got.Get("X-A2A-Notification-Token") != "notification-token-1" {
		t.Fatalf("notification token header = %q", got.Get("X-A2A-Notification-Token"))
	}
	timestamp := got.Get("X-A2A-Timestamp")
	want := hmacDigest("signing-secret-1", timestamp, request.DeliveryID, request.PayloadHash, body)
	if got.Get("X-A2A-Signature") != "sha256="+want {
		t.Fatalf("signature = %q want sha256=%s", got.Get("X-A2A-Signature"), want)
	}
	if timestamp != "1735000000" {
		t.Fatalf("timestamp = %q", timestamp)
	}
}

func TestHTTPDeliveryRejectsRedirectAndPrivateDNSRebinding(t *testing.T) {
	redirected := false
	target := httptest.NewTLSServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { redirected = true }))
	defer target.Close()
	redirect := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target.URL, http.StatusTemporaryRedirect)
	}))
	defer redirect.Close()

	request := DeliveryRequest{Config: Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: redirect.URL}, Payload: []byte("payload"), DeliveryID: "delivery-1"}
	delivery := HTTPDelivery{Client: redirect.Client(), Policy: localHTTPDeliveryPolicy(redirect)}
	if err := delivery.Deliver(context.Background(), request); err == nil || redirected {
		t.Fatalf("redirect was followed or accepted: err=%v redirected=%v", err, redirected)
	}

	private := request
	private.Config.URL = "https://notify.example.test/a2a"
	delivery = HTTPDelivery{Policy: Policy{AllowedHosts: []string{"notify.example.test"}, RequireDNSResolution: true, Resolver: ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
		return []net.IPAddr{{IP: net.ParseIP("10.0.0.8")}}, nil
	})}}
	if err := delivery.Deliver(context.Background(), private); err == nil || !strings.Contains(err.Error(), "private") {
		t.Fatalf("private rebinding was accepted: %v", err)
	}
}

func localHTTPDeliveryPolicy(server *httptest.Server) Policy {
	return Policy{AllowedHosts: []string{"127.0.0.1"}, AllowLoopback: true, RequireDNSResolution: true}
}

func TestHMACDigestUsesSHA256(t *testing.T) {
	payload := []byte("payload")
	got := hmacDigest("secret", "1", "delivery", PayloadDigest(payload), payload)
	mac := hmac.New(sha256.New, []byte("secret"))
	_, _ = mac.Write([]byte("1.delivery." + PayloadDigest(payload) + ".payload"))
	want := hex.EncodeToString(mac.Sum(nil))
	if got != want {
		t.Fatalf("digest=%s want=%s", got, want)
	}
}
