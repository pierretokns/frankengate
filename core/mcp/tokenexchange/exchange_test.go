package tokenexchange

import (
	"context"
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/stretchr/testify/require"
)

func testConfig(endpoint string) *schemas.MCPTokenExchangeConfig {
	return &schemas.MCPTokenExchangeConfig{
		Enabled:           true,
		TokenURL:          schemas.NewSecretVar(endpoint),
		AllowedHosts:      []string{"127.0.0.1"},
		AllowInsecureHTTP: true,
		ClientID:          schemas.NewSecretVar("client"),
		ClientSecret:      schemas.NewSecretVar("secret"),
		Audience:          []string{"api://downstream"},
		Scope:             []string{"read"},
		CacheSkewSeconds:  1,
	}
}

func TestExchangeSubjectActorAndCache(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		require.NoError(t, r.ParseForm())
		require.Equal(t, tokenExchangeGrantType, r.Form.Get("grant_type"))
		require.Equal(t, "subject", r.Form.Get("subject_token"))
		require.Equal(t, "actor", r.Form.Get("actor_token"))
		require.Equal(t, "api://downstream", r.Form.Get("audience"))
		require.Equal(t, "read", r.Form.Get("scope"))
		user, password, ok := r.BasicAuth()
		require.True(t, ok)
		require.Equal(t, "client", user)
		require.Equal(t, "secret", password)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"access_token":"downstream","expires_in":120}`))
	}))
	defer server.Close()
	config := testConfig(server.URL)
	config.ActorTokenHeader = "x-actor"
	exchanger := New(nil)

	got, err := exchanger.Exchange(context.Background(), config, "subject", "actor")
	require.NoError(t, err)
	require.Equal(t, "downstream", got)
	got, err = exchanger.Exchange(context.Background(), config, "subject", "actor")
	require.NoError(t, err)
	require.Equal(t, "downstream", got)
	require.Equal(t, int32(1), calls.Load())
}

func TestExchangeFromContextOnlyReadsConfiguredHeaders(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.NoError(t, r.ParseForm())
		require.Equal(t, "from-header", r.Form.Get("subject_token"))
		_, _ = w.Write([]byte(`{"access_token":"ok","expires_in":60}`))
	}))
	defer server.Close()
	config := testConfig(server.URL)
	config.SubjectTokenHeader = "x-subject"
	ctx := context.WithValue(context.Background(), schemas.BifrostContextKeyRequestHeaders, map[string]string{
		"Authorization": "Bearer wrong-header",
		"X-Subject":     "from-header",
	})
	got, err := New(nil).ExchangeFromContext(ctx, config)
	require.NoError(t, err)
	require.Equal(t, "ok", got)
}

func TestExchangeRejectsUnallowlistedEndpointAndRedirect(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "https://example.invalid/token", http.StatusFound)
	}))
	defer server.Close()
	config := testConfig(server.URL)
	config.AllowedHosts = []string{"not-this-host"}
	_, err := New(nil).Exchange(context.Background(), config, "subject", "")
	require.ErrorIs(t, err, ErrInvalidConfig)

	config.AllowedHosts = []string{"127.0.0.1"}
	_, err = New(nil).Exchange(context.Background(), config, "different-subject", "")
	require.Error(t, err)
	require.Equal(t, "token endpoint request failed", err.Error())
}

func TestExchangeIsSingleFlightAndCacheIsBounded(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		time.Sleep(20 * time.Millisecond)
		_, _ = w.Write([]byte(`{"access_token":"one","expires_in":120}`))
	}))
	defer server.Close()
	config := testConfig(server.URL)
	config.MaxCacheEntries = 1
	exchanger := New(nil)

	var wg sync.WaitGroup
	for range 8 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			got, err := exchanger.Exchange(context.Background(), config, "same", "")
			require.NoError(t, err)
			require.Equal(t, "one", got)
		}()
	}
	wg.Wait()
	require.Equal(t, int32(1), calls.Load())
	require.Len(t, exchanger.cache, 1)
}

func TestExchangeCapsCacheToSubjectExpiry(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		_, _ = w.Write([]byte(`{"access_token":"short","expires_in":300}`))
	}))
	defer server.Close()
	now := time.Unix(2_000_000_000, 0)
	exchanger := New(nil)
	exchanger.now = func() time.Time { return now }
	config := testConfig(server.URL)
	config.CacheSkewSeconds = 1
	subject := jwtWithExpiry(now.Add(10 * time.Second))
	_, err := exchanger.Exchange(context.Background(), config, subject, "")
	require.NoError(t, err)
	require.Len(t, exchanger.cache, 1)
	entry := exchanger.cache[cacheKey(config, subject, "")]
	require.WithinDuration(t, now.Add(9*time.Second), entry.expiresAt, time.Second)
	_ = calls
}

func TestExchangeRedactsEndpointDetailsAndSecrets(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"error":"invalid_grant","error_description":"subject-secret"}`))
	}))
	defer server.Close()
	_, err := New(nil).Exchange(context.Background(), testConfig(server.URL), "subject-secret", "")
	require.Error(t, err)
	require.NotContains(t, err.Error(), "subject-secret")
	require.Contains(t, err.Error(), "invalid_grant")
}

func TestJWTBearerGrant(t *testing.T) {
	var got url.Values
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.NoError(t, r.ParseForm())
		got = r.Form
		_, _ = w.Write([]byte(`{"access_token":"jwt-exchanged","expires_in":60}`))
	}))
	defer server.Close()
	config := testConfig(server.URL)
	config.Grant = schemas.MCPTokenExchangeGrantJWTBearer
	config.AllowedHosts = []string{"127.0.0.1"}
	_, err := New(nil).Exchange(context.Background(), config, "assertion", "")
	require.NoError(t, err)
	require.Equal(t, jwtBearerGrantType, got.Get("grant_type"))
	require.Equal(t, "assertion", got.Get("assertion"))
	require.Empty(t, got.Get("subject_token"))
}

func TestIDJAGExchangeRedeemsAtResourceAuthorizationServer(t *testing.T) {
	var firstCalls, secondCalls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.NoError(t, r.ParseForm())
		user, password, ok := r.BasicAuth()
		require.True(t, ok)
		switch r.URL.Path {
		case "/idp":
			firstCalls.Add(1)
			require.Equal(t, "client", user)
			require.Equal(t, "secret", password)
			require.Equal(t, tokenExchangeGrantType, r.Form.Get("grant_type"))
			require.Equal(t, "subject", r.Form.Get("subject_token"))
			require.Equal(t, idJAGTokenType, r.Form.Get("requested_token_type"))
			require.Equal(t, "https://resource-as.example/", r.Form.Get("audience"))
			_, _ = w.Write([]byte(`{"access_token":"id-jag","issued_token_type":"urn:ietf:params:oauth:token-type:id-jag","token_type":"N_A","expires_in":60}`))
		case "/resource":
			secondCalls.Add(1)
			require.Equal(t, "resource-client", user)
			require.Equal(t, "resource-secret", password)
			require.Equal(t, jwtBearerGrantType, r.Form.Get("grant_type"))
			require.Equal(t, "id-jag", r.Form.Get("assertion"))
			require.Empty(t, r.Form.Get("subject_token"))
			_, _ = w.Write([]byte(`{"access_token":"mcp-bearer","token_type":"Bearer","expires_in":120}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	config := testConfig(server.URL + "/idp")
	config.Mode = schemas.MCPTokenExchangeModeIDJAG
	config.Audience = []string{"https://resource-as.example/"}
	config.ResourceTokenURL = schemas.NewSecretVar(server.URL + "/resource")
	config.ResourceAllowedHosts = []string{"127.0.0.1"}
	config.ResourceClientID = schemas.NewSecretVar("resource-client")
	config.ResourceClientSecret = schemas.NewSecretVar("resource-secret")

	exchanger := New(nil)
	got, err := exchanger.Exchange(context.Background(), config, "subject", "")
	require.NoError(t, err)
	require.Equal(t, "mcp-bearer", got)
	require.Equal(t, int32(1), firstCalls.Load())
	require.Equal(t, int32(1), secondCalls.Load())

	got, err = exchanger.Exchange(context.Background(), config, "subject", "")
	require.NoError(t, err)
	require.Equal(t, "mcp-bearer", got)
	require.Equal(t, int32(1), firstCalls.Load())
	require.Equal(t, int32(1), secondCalls.Load())
}

func TestIDJAGExchangeRejectsNonIDJAGIntermediate(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"access_token":"wrong","token_type":"Bearer","expires_in":60}`))
	}))
	defer server.Close()
	config := testConfig(server.URL)
	config.Mode = schemas.MCPTokenExchangeModeIDJAG
	config.Audience = []string{"https://resource-as.example/"}
	config.ResourceTokenURL = schemas.NewSecretVar(server.URL)
	config.ResourceAllowedHosts = []string{"127.0.0.1"}
	config.ResourceClientID = schemas.NewSecretVar("resource-client")
	config.ResourceClientSecret = schemas.NewSecretVar("resource-secret")

	_, err := New(nil).Exchange(context.Background(), config, "subject", "")
	require.ErrorIs(t, err, ErrInvalidTokenReply)
}

func TestIDJAGConfigRequiresResourceLegAndSingleAudience(t *testing.T) {
	config := testConfig("https://sts.example.com/token")
	config.AllowedHosts = []string{"sts.example.com"}
	config.Mode = schemas.MCPTokenExchangeModeIDJAG
	config.Audience = []string{"one", "two"}
	require.Error(t, ValidateConfig(config))

	config.Audience = []string{"https://resource-as.example/"}
	require.Error(t, ValidateConfig(config))
}

func TestParseExpiresIn(t *testing.T) {
	got, err := ParseExpiresIn(" 42 ")
	require.NoError(t, err)
	require.Equal(t, int64(42), got)
	_, err = ParseExpiresIn("not-a-duration")
	require.Error(t, err)
}

func jwtWithExpiry(exp time.Time) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"none","typ":"JWT"}`))
	payload := base64.RawURLEncoding.EncodeToString([]byte(`{"exp":2000000010}`))
	return strings.Join([]string{header, payload, "signature"}, ".")
}
