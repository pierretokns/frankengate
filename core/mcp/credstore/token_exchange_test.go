package credstore

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/stretchr/testify/require"
)

func TestTokenExchangeResolverNeverForwardsSubjectToken(t *testing.T) {
	var gotSubject string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = r.ParseForm()
		gotSubject = r.Form.Get("subject_token")
		_, _ = w.Write([]byte(`{"access_token":"downstream","expires_in":60}`))
	}))
	defer server.Close()

	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{
		Tenant: "acme", Issuer: "https://okta.example", Subject: "user-1",
	})
	ctx.SetValue(schemas.BifrostContextKeyRequestHeaders, map[string]string{
		"authorization": "Bearer inbound-user-token",
	})
	config := &schemas.MCPClientConfig{
		Name:     "okta-tools",
		AuthType: schemas.MCPAuthTypeTokenExchange,
		TokenExchange: &schemas.MCPTokenExchangeConfig{
			Enabled:           true,
			TokenURL:          schemas.NewSecretVar(server.URL),
			AllowedHosts:      []string{"127.0.0.1"},
			AllowInsecureHTTP: true,
			ClientID:          schemas.NewSecretVar("client"),
			ClientSecret:      schemas.NewSecretVar("secret"),
		},
	}

	store := NewCredStore(nil, nil, nil)
	headers, err := store.ConnectionHeaders(ctx, config)
	require.NoError(t, err)
	require.Equal(t, "Bearer downstream", headers.Get("Authorization"))
	require.NotEqual(t, "Bearer inbound-user-token", headers.Get("Authorization"))
	require.Equal(t, "inbound-user-token", gotSubject)
}

func TestTokenExchangeResolverRequiresPerCallConnection(t *testing.T) {
	store := NewCredStore(nil, nil, nil)
	require.True(t, store.RequiresPerCallConnection(&schemas.MCPClientConfig{AuthType: schemas.MCPAuthTypeTokenExchange}))
}
