package a2abroker

import (
	"context"
	"errors"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

type fakeOAuthProvider struct {
	serverToken string
	userToken   string
	mode        schemas.MCPAuthMode
	identity    string
	client      string
}

func (f *fakeOAuthProvider) GetAccessToken(context.Context, string) (string, error) {
	return f.serverToken, nil
}
func (f *fakeOAuthProvider) RefreshAccessToken(context.Context, string) error    { return nil }
func (f *fakeOAuthProvider) ValidateToken(context.Context, string) (bool, error) { return true, nil }
func (f *fakeOAuthProvider) RevokeToken(context.Context, string) error           { return nil }
func (f *fakeOAuthProvider) GetUserAccessTokenByMode(_ context.Context, mode schemas.MCPAuthMode, identity, client string) (string, error) {
	f.mode, f.identity, f.client = mode, identity, client
	return f.userToken, nil
}
func (f *fakeOAuthProvider) InitiateUserOAuthFlow(context.Context, string, string, string, schemas.MCPAuthMode) (*schemas.OAuth2FlowInitiation, string, error) {
	return nil, "", nil
}
func (f *fakeOAuthProvider) CompleteUserOAuthFlow(context.Context, string, string) (string, error) {
	return "", nil
}
func (f *fakeOAuthProvider) RefreshUserAccessToken(context.Context, string) error { return nil }

type fakeExchanger struct {
	gotSubject string
	gotActor   string
	result     string
}

func (f *fakeExchanger) Exchange(_ context.Context, _ *schemas.MCPTokenExchangeConfig, subject, actor string) (string, error) {
	f.gotSubject, f.gotActor = subject, actor
	return f.result, nil
}

func TestRuntimeCredentialResolverUsesExactUserBinding(t *testing.T) {
	oauth := &fakeOAuthProvider{userToken: "user-token"}
	resolver := RuntimeCredentialResolver{OAuthProvider: oauth}
	credential, err := resolver.Resolve(context.Background(), CredentialRequest{
		Scheme:      a2adiscovery.SecurityScheme{Type: "oauth2"},
		AuthMode:    schemas.MCPAuthModeVK,
		Identity:    "vk-row-7",
		MCPClientID: "client-1",
	})
	if err != nil {
		t.Fatalf("resolve: %v", err)
	}
	if credential.Kind != CredentialOAuth2 || credential.Headers.Get("Authorization") != "Bearer user-token" {
		t.Fatalf("unexpected credential: %#v", credential)
	}
	if oauth.mode != schemas.MCPAuthModeVK || oauth.identity != "vk-row-7" || oauth.client != "client-1" {
		t.Fatalf("wrong user binding: mode=%q identity=%q client=%q", oauth.mode, oauth.identity, oauth.client)
	}
}

func TestRuntimeCredentialResolverUsesExplicitServerOAuthAndNoFallback(t *testing.T) {
	resolver := RuntimeCredentialResolver{OAuthProvider: &fakeOAuthProvider{serverToken: "server-token"}}
	credential, err := resolver.Resolve(context.Background(), CredentialRequest{
		Scheme:        a2adiscovery.SecurityScheme{Type: "openidConnect"},
		OAuthConfigID: "oauth-prod",
	})
	if err != nil || credential.Headers.Get("Authorization") != "Bearer server-token" {
		t.Fatalf("server OAuth resolution failed: credential=%#v err=%v", credential, err)
	}

	_, err = resolver.Resolve(context.Background(), CredentialRequest{
		Scheme:   a2adiscovery.SecurityScheme{Type: "oauth2"},
		AuthMode: schemas.MCPAuthModeUser,
		Identity: "user-1",
	})
	if !errors.Is(err, ErrCredentialRequired) {
		t.Fatalf("expected missing client binding to require auth, got %v", err)
	}
}

func TestRuntimeCredentialResolverRequiresExplicitPassThroughAndSupportsExchange(t *testing.T) {
	resolver := RuntimeCredentialResolver{}
	_, err := resolver.Resolve(context.Background(), CredentialRequest{
		Scheme:       a2adiscovery.SecurityScheme{Type: "http", Scheme: "bearer"},
		SubjectToken: "incoming-token",
	})
	if !errors.Is(err, ErrCredentialRequired) {
		t.Fatalf("unexpected implicit pass-through result: %v", err)
	}

	credential, err := resolver.Resolve(context.Background(), CredentialRequest{
		Scheme:                  a2adiscovery.SecurityScheme{Type: "http", Scheme: "bearer"},
		SubjectToken:            "incoming-token",
		AllowSubjectPassThrough: true,
	})
	if err != nil || credential.Kind != CredentialPassThrough || credential.Headers.Get("Authorization") != "Bearer incoming-token" {
		t.Fatalf("pass-through resolution failed: credential=%#v err=%v", credential, err)
	}

	exchanger := &fakeExchanger{result: "exchanged-token"}
	resolver = RuntimeCredentialResolver{Exchanger: exchanger}
	credential, err = resolver.Resolve(context.Background(), CredentialRequest{
		Scheme:        a2adiscovery.SecurityScheme{Type: "oauth2"},
		SubjectToken:  "subject-token",
		ActorToken:    "actor-token",
		TokenExchange: &schemas.MCPTokenExchangeConfig{Enabled: true},
	})
	if err != nil || credential.Kind != CredentialTokenExchange || credential.Headers.Get("Authorization") != "Bearer exchanged-token" {
		t.Fatalf("exchange resolution failed: credential=%#v err=%v", credential, err)
	}
	if exchanger.gotSubject != "subject-token" || exchanger.gotActor != "actor-token" {
		t.Fatalf("exchange received wrong tokens: subject=%q actor=%q", exchanger.gotSubject, exchanger.gotActor)
	}
}
