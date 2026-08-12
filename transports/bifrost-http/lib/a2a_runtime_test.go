package lib

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2abroker"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

type runtimeOAuthProvider struct{}

func (runtimeOAuthProvider) GetAccessToken(context.Context, string) (string, error) {
	return "runtime-oauth-token", nil
}
func (runtimeOAuthProvider) RefreshAccessToken(context.Context, string) error    { return nil }
func (runtimeOAuthProvider) ValidateToken(context.Context, string) (bool, error) { return true, nil }
func (runtimeOAuthProvider) RevokeToken(context.Context, string) error           { return nil }
func (runtimeOAuthProvider) GetUserAccessTokenByMode(context.Context, schemas.MCPAuthMode, string, string) (string, error) {
	return "runtime-user-token", nil
}
func (runtimeOAuthProvider) InitiateUserOAuthFlow(context.Context, string, string, string, schemas.MCPAuthMode) (*schemas.OAuth2FlowInitiation, string, error) {
	return nil, "", nil
}
func (runtimeOAuthProvider) CompleteUserOAuthFlow(context.Context, string, string) (string, error) {
	return "", nil
}
func (runtimeOAuthProvider) RefreshUserAccessToken(context.Context, string) error { return nil }

type runtimeSenderFunc func(context.Context, a2abroker.SendRequest) (a2abroker.Event, error)

func (f runtimeSenderFunc) Send(ctx context.Context, request a2abroker.SendRequest) (a2abroker.Event, error) {
	return f(ctx, request)
}

func TestConfigOutboundA2ARuntimeUsesConfiguredCredentialResolver(t *testing.T) {
	cfg := &Config{
		A2ABroker:             a2abroker.New(func() time.Time { return time.Unix(100, 0) }, func() string { return "task-runtime" }, a2abroker.RetryPolicy{}),
		A2ACredentialResolver: &a2abroker.RuntimeCredentialResolver{OAuthProvider: runtimeOAuthProvider{}},
	}
	task, err := cfg.SubmitOutboundA2A("https://agent.example/a2a", "card-digest", []byte(`{"message":"hello"}`), "trace-runtime")
	if err != nil {
		t.Fatal(err)
	}
	card := &a2adiscovery.AgentCard{SecuritySchemes: map[string]a2adiscovery.SecurityScheme{"oauth": {Type: "oauth2"}}}
	var got http.Header
	completed, err := cfg.DispatchOutboundA2A(context.Background(), task.ID, []byte(`{"message":"hello"}`), runtimeSenderFunc(func(_ context.Context, request a2abroker.SendRequest) (a2abroker.Event, error) {
		got = request.Headers
		return a2abroker.Event{State: a2abroker.StateCompleted}, nil
	}), card, a2abroker.CredentialRequest{TenantID: "tenant-runtime", OAuthConfigID: "oauth-prod"}, a2abroker.CredentialPolicy{AllowedHosts: []string{"agent.example"}, AllowedKinds: []a2abroker.CredentialKind{a2abroker.CredentialOAuth2}})
	if err != nil {
		t.Fatal(err)
	}
	if completed.State != a2abroker.StateCompleted || got.Get("Authorization") != "Bearer runtime-oauth-token" {
		t.Fatalf("completed=%#v headers=%#v", completed, got)
	}
	if completed.Error != "" || completed.TraceID != "trace-runtime" {
		t.Fatalf("credential or trace leaked into task error/state: %#v", completed)
	}
}

func TestConfigOutboundA2ARuntimeRequiresExplicitConfiguredSender(t *testing.T) {
	cfg := &Config{
		A2ABroker:             a2abroker.New(time.Now, func() string { return "task-runtime-configured" }, a2abroker.RetryPolicy{}),
		A2ACredentialResolver: &a2abroker.RuntimeCredentialResolver{OAuthProvider: runtimeOAuthProvider{}},
	}
	task, err := cfg.SubmitOutboundA2A("https://agent.example/a2a", "card-digest", []byte(`{"message":"hello"}`), "trace-runtime")
	if err != nil {
		t.Fatal(err)
	}
	card := &a2adiscovery.AgentCard{SecuritySchemes: map[string]a2adiscovery.SecurityScheme{"oauth": {Type: "oauth2"}}}
	policy := a2abroker.CredentialPolicy{AllowedHosts: []string{"agent.example"}, AllowedKinds: []a2abroker.CredentialKind{a2abroker.CredentialOAuth2}}
	if _, err := cfg.DispatchConfiguredOutboundA2A(context.Background(), task.ID, []byte(`{"message":"hello"}`), card, a2abroker.CredentialRequest{TenantID: "tenant-runtime", OAuthConfigID: "oauth-prod"}, policy); err == nil {
		t.Fatal("expected configured outbound dispatch to fail closed without an installed sender")
	}
	cfg.SetA2AOutboundSender(runtimeSenderFunc(func(_ context.Context, request a2abroker.SendRequest) (a2abroker.Event, error) {
		if request.Headers.Get("Authorization") != "Bearer runtime-oauth-token" {
			t.Fatalf("credential resolver was not used: %#v", request.Headers)
		}
		return a2abroker.Event{State: a2abroker.StateCompleted}, nil
	}))
	completed, err := cfg.DispatchConfiguredOutboundA2A(context.Background(), task.ID, []byte(`{"message":"hello"}`), card, a2abroker.CredentialRequest{TenantID: "tenant-runtime", OAuthConfigID: "oauth-prod"}, policy)
	if err != nil || completed.State != a2abroker.StateCompleted {
		t.Fatalf("configured dispatch failed: task=%#v err=%v", completed, err)
	}
}
