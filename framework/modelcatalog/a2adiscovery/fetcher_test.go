package a2adiscovery

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"slices"
	"strings"
	"testing"
	"time"
)

func TestProtocolVersionCompatibilityWindow(t *testing.T) {
	if SupportedProtocolVersion != "1.0.0" {
		t.Fatalf("canonical A2A protocol version = %q", SupportedProtocolVersion)
	}
	if !IsSupportedProtocolVersion("1.0.0") || !IsSupportedProtocolVersion("1.0.1") {
		t.Fatal("released and immediately prior A2A versions must be accepted")
	}
	if IsSupportedProtocolVersion("0.3") {
		t.Fatal("unsupported A2A protocol version was accepted")
	}
}

func TestValidateReleasedAgentCardUsesSupportedInterfaces(t *testing.T) {
	source, err := url.Parse("https://agent.example/.well-known/agent-card.json")
	if err != nil {
		t.Fatal(err)
	}
	card := &AgentCard{
		Name:    "Modern Agent",
		Version: "1.0.0",
		SupportedInterfaces: []AgentInterface{{
			URL:             "https://agent.example/a2a",
			ProtocolBinding: TransportJSONRPC,
			ProtocolVersion: "1.0.0",
		}},
		Skills: []AgentSkill{{ID: "chat", Name: "Chat"}},
	}
	if err := ValidateAgentCard(card, source, HTTPSOnly); err != nil {
		t.Fatalf("modern A2A card should validate: %v", err)
	}
}

func TestSecuritySchemeAcceptsReleasedWrapperShape(t *testing.T) {
	source, err := url.Parse("https://agent.example/.well-known/agent-card.json")
	if err != nil {
		t.Fatal(err)
	}
	var card AgentCard
	if err := json.Unmarshal([]byte(`{"name":"agent","version":"1","supportedInterfaces":[{"url":"https://agent.example/a2a","protocolBinding":"JSONRPC","protocolVersion":"1.0"}],"securitySchemes":{"oidc":{"openIdConnectSecurityScheme":{"openIdConnectUrl":"https://issuer.example/.well-known/openid-configuration"}}},"securityRequirements":[{"oidc":[]}],"skills":[{"id":"chat","name":"Chat"}]}`), &card); err != nil {
		t.Fatal(err)
	}
	if err := ValidateAgentCard(&card, source, HTTPSOnly); err != nil {
		t.Fatalf("released security wrapper should validate: %v", err)
	}
	if card.SecuritySchemes["oidc"].Type != "openIdConnect" {
		t.Fatalf("security scheme type = %#v", card.SecuritySchemes["oidc"])
	}
}

func TestSecurityRequirementsAcceptReleasedWrapperShape(t *testing.T) {
	var card AgentCard
	err := json.Unmarshal([]byte(`{
		"name":"agent",
		"version":"1",
		"supportedInterfaces":[{"url":"https://agent.example/a2a","protocolBinding":"JSONRPC","protocolVersion":"1.0"}],
		"securitySchemes":{"oidc":{"openIdConnectSecurityScheme":{"openIdConnectUrl":"https://issuer.example/.well-known/openid-configuration"}}},
		"securityRequirements":[{"schemes":{"oidc":{"list":["openid","profile"]}}}],
		"skills":[{"id":"chat","name":"Chat"}]
	}`), &card)
	if err != nil {
		t.Fatal(err)
	}
	source, err := url.Parse("https://agent.example/.well-known/agent-card.json")
	if err != nil {
		t.Fatal(err)
	}
	if err := ValidateAgentCard(&card, source, HTTPSOnly); err != nil {
		t.Fatalf("released security requirements should validate: %v", err)
	}
	if got := card.SecurityRequirements[0]["oidc"]; !slices.Equal(got, []string{"openid", "profile"}) {
		t.Fatalf("security requirement scopes = %#v", got)
	}
}

func TestFetchWellKnownHTTPSAgentCard(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != WellKnownAgentCardPath {
			t.Fatalf("expected primary well-known path, got %s", r.URL.Path)
		}
		writeCard(t, w, validCard("https://agent.example"+serverPortPath(t, r)))
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	result, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err != nil {
		t.Fatalf("fetch: %v", err)
	}
	if result.Card.Name != "Example Agent" {
		t.Fatalf("unexpected card: %+v", result.Card)
	}
}

func TestFetchFallsBackToLegacyWellKnownAgentCard(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case WellKnownAgentCardPath:
			http.NotFound(w, r)
		case LegacyAgentCardPath:
			writeCard(t, w, validCard("https://agent.example"+serverPortPath(t, r)))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	result, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err != nil {
		t.Fatalf("fetch: %v", err)
	}
	if result.Card.ProtocolVersion != SupportedProtocolVersion {
		t.Fatalf("unexpected card: %+v", result.Card)
	}
}

func TestFetchDirectCardURL(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/cards/agent.json" {
			t.Fatalf("expected direct path, got %s", r.URL.Path)
		}
		writeCard(t, w, validCard("https://agent.example"+serverPortPath(t, r)))
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL)+"/cards/agent.json")
	if err != nil {
		t.Fatalf("fetch: %v", err)
	}
}

func TestHTTPSPolicyRejectsHTTPByDefaultAndAllowsWhenConfigured(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeCard(t, w, validCard("http://agent.example"+serverPortPath(t, r)))
	}))
	defer server.Close()

	httpsOnly := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	_, err := httpsOnly.Fetch(context.Background(), "http://agent.example:"+portOf(t, server.URL))
	if err == nil || !strings.Contains(err.Error(), "http a2a discovery URLs are disabled") {
		t.Fatalf("expected http policy error, got %v", err)
	}

	httpAllowed := testFetcher(t, server, "agent.example", HTTPSOrHTTP, nil)
	_, err = httpAllowed.Fetch(context.Background(), "http://agent.example:"+portOf(t, server.URL))
	if err != nil {
		t.Fatalf("expected http policy override to fetch: %v", err)
	}
}

func TestRedirectLimit(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case WellKnownAgentCardPath:
			http.Redirect(w, r, "/first", http.StatusFound)
		case "/first":
			http.Redirect(w, r, "/second", http.StatusFound)
		case "/second":
			writeCard(t, w, validCard("https://agent.example"+serverPortPath(t, r)))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, func(opts *Options) {
		opts.MaxRedirects = 1
	})
	_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err == nil || !strings.Contains(err.Error(), "redirect limit 1 exceeded") {
		t.Fatalf("expected redirect limit error, got %v", err)
	}
}

func TestOversizeBodyRejected(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(strings.Repeat("x", 32)))
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, func(opts *Options) {
		opts.MaxResponseBytes = 8
	})
	_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err == nil || !strings.Contains(err.Error(), "exceeds 8 bytes") {
		t.Fatalf("expected oversize error, got %v", err)
	}
}

func TestMalformedJSONRejected(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"protocolVersion":`))
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err == nil || !strings.Contains(err.Error(), "decode a2a agent card") {
		t.Fatalf("expected malformed json error, got %v", err)
	}
}

func TestDeniedIPRanges(t *testing.T) {
	t.Run("direct loopback url", func(t *testing.T) {
		fetcher, err := NewFetcher(Options{AllowedHosts: []string{"127.0.0.1"}, HTTPSPolicy: HTTPSOrHTTP})
		if err != nil {
			t.Fatalf("new fetcher: %v", err)
		}
		_, err = fetcher.Fetch(context.Background(), "http://127.0.0.1/.well-known/agent-card.json")
		if err == nil || !strings.Contains(err.Error(), "loopback") {
			t.Fatalf("expected loopback denial, got %v", err)
		}
	})

	t.Run("resolved private ip", func(t *testing.T) {
		server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			writeCard(t, w, validCard("https://agent.example"+serverPortPath(t, r)))
		}))
		defer server.Close()
		fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, func(opts *Options) {
			opts.Resolver = staticResolver("10.0.0.7")
		})
		_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
		if err == nil || !strings.Contains(err.Error(), "private") {
			t.Fatalf("expected private ip denial, got %v", err)
		}
	})
}

func TestContentTypeRejected(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		_, _ = w.Write([]byte(`{}`))
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err == nil || !strings.Contains(err.Error(), "unsupported a2a agent card content-type") {
		t.Fatalf("expected content type error, got %v", err)
	}
}

func TestHostAllowlistRejected(t *testing.T) {
	fetcher, err := NewFetcher(Options{
		AllowedHosts: []string{"allowed.example"},
		HTTPSPolicy:  HTTPSOnly,
		Resolver:     staticResolver("93.184.216.34"),
	})
	if err != nil {
		t.Fatalf("new fetcher: %v", err)
	}
	_, err = fetcher.Fetch(context.Background(), "https://blocked.example/.well-known/agent-card.json")
	if err == nil || !strings.Contains(err.Error(), "allowlist") {
		t.Fatalf("expected allowlist error, got %v", err)
	}
}

func TestEndpointOriginMismatchRejected(t *testing.T) {
	server := newCardTLSServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeCard(t, w, validCard("https://other.example"+serverPortPath(t, r)))
	}))
	defer server.Close()

	fetcher := testFetcher(t, server, "agent.example", HTTPSOnly, nil)
	_, err := fetcher.Fetch(context.Background(), "https://agent.example:"+portOf(t, server.URL))
	if err == nil || !strings.Contains(err.Error(), "must match fetched card origin") {
		t.Fatalf("expected origin mismatch error, got %v", err)
	}
}

func TestValidateAgentCardRejectsInvalidFields(t *testing.T) {
	source, err := url.Parse("https://agent.example:443/.well-known/agent-card.json")
	if err != nil {
		t.Fatalf("parse source: %v", err)
	}
	card := validCard("https://agent.example")
	card.ProtocolVersion = "0.9"
	card.PreferredTransport = TransportBinding("FTP")
	card.DefaultInputModes = []string{"bad/*"}
	card.SecuritySchemes = map[string]SecurityScheme{
		"api": {Type: "apiKey", Name: "x-api-key", In: "body"},
	}
	card.Security = []map[string][]string{{"missing": nil}}
	card.Skills = []AgentSkill{{
		ID:         "",
		Name:       "",
		InputModes: []string{"text/plain"},
		Extensions: map[string]json.RawMessage{
			"broken": json.RawMessage(`{`),
		},
	}}
	err = ValidateAgentCard(&card, source, HTTPSOnly)
	if err == nil {
		t.Fatalf("expected validation errors")
	}
	message := err.Error()
	for _, fragment := range []string{"protocolVersion", "preferredTransport", "defaultInputModes", "security", "skills[0].id", "valid JSON"} {
		if !strings.Contains(message, fragment) {
			t.Fatalf("expected error to contain %q, got %q", fragment, message)
		}
	}
}

func newCardTLSServer(t *testing.T, handler http.Handler) *httptest.Server {
	t.Helper()
	server := httptest.NewTLSServer(handler)
	return server
}

func testFetcher(t *testing.T, server *httptest.Server, host string, policy HTTPSPolicy, mutate func(*Options)) *Fetcher {
	t.Helper()
	opts := Options{
		AllowedHosts:     []string{host + ":" + portOf(t, server.URL)},
		HTTPSPolicy:      policy,
		Resolver:         staticResolver("93.184.216.34"),
		DialContext:      dialToServer(t, server),
		TLSClientConfig:  &tls.Config{InsecureSkipVerify: true},
		Timeout:          2 * time.Second,
		MaxResponseBytes: DefaultMaxResponseBytes,
	}
	if mutate != nil {
		mutate(&opts)
	}
	fetcher, err := NewFetcher(opts)
	if err != nil {
		t.Fatalf("new fetcher: %v", err)
	}
	return fetcher
}

func staticResolver(ip string) ResolverFunc {
	return func(ctx context.Context, host string) ([]net.IPAddr, error) {
		return []net.IPAddr{{IP: net.ParseIP(ip)}}, nil
	}
}

func dialToServer(t *testing.T, server *httptest.Server) DialContextFunc {
	t.Helper()
	dialer := &net.Dialer{Timeout: 2 * time.Second}
	return func(ctx context.Context, network, address string) (net.Conn, error) {
		_, requestedPort, err := net.SplitHostPort(address)
		if err != nil {
			return nil, err
		}
		if requestedPort != portOf(t, server.URL) {
			return nil, fmt.Errorf("unexpected dial address %s", address)
		}
		return dialer.DialContext(ctx, network, server.Listener.Addr().String())
	}
}

func validCard(endpoint string) AgentCard {
	return AgentCard{
		SchemaVersion:      SupportedSchemaVersion,
		ProtocolVersion:    SupportedProtocolVersion,
		Name:               "Example Agent",
		Description:        "A bounded test agent card.",
		URL:                endpoint,
		PreferredTransport: TransportJSONRPC,
		Provider:           &AgentProvider{Organization: "Example"},
		Version:            "2026-08-04",
		Capabilities:       AgentCapabilities{Streaming: true},
		SecuritySchemes: map[string]SecurityScheme{
			"api_key": {Type: "apiKey", Name: "x-api-key", In: "header"},
		},
		Security:           []map[string][]string{{"api_key": nil}},
		DefaultInputModes:  []string{"text", "application/json"},
		DefaultOutputModes: []string{"text"},
		Skills: []AgentSkill{{
			ID:          "search",
			Name:        "Search",
			Description: "Searches a bounded corpus.",
			Tags:        []string{"search"},
			InputModes:  []string{"text"},
			OutputModes: []string{"text"},
			Extensions: map[string]json.RawMessage{
				"com.example.skill": json.RawMessage(`{"tier":"test"}`),
			},
		}},
		Extensions: map[string]json.RawMessage{
			"com.example.card": json.RawMessage(`{"admission":"test"}`),
		},
	}
}

func writeCard(t *testing.T, w http.ResponseWriter, card AgentCard) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	if err := json.NewEncoder(w).Encode(card); err != nil {
		t.Fatalf("encode card: %v", err)
	}
}

func portOf(t *testing.T, rawURL string) string {
	t.Helper()
	parsed, err := url.Parse(rawURL)
	if err != nil {
		t.Fatalf("parse server url: %v", err)
	}
	return parsed.Port()
}

func serverPortPath(t *testing.T, r *http.Request) string {
	t.Helper()
	port := r.Host
	if strings.Contains(port, ":") {
		_, splitPort, err := net.SplitHostPort(r.Host)
		if err == nil {
			port = ":" + splitPort
		}
	}
	if !strings.HasPrefix(port, ":") {
		port = ":" + port
	}
	return port + "/rpc"
}
