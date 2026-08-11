package a2abroker

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

// CredentialKind describes the mechanism used for one downstream A2A call.
// The broker treats all values as opaque credentials and never records their
// material in Task, Event, or error strings.
type CredentialKind string

const (
	CredentialNone          CredentialKind = "none"
	CredentialPassThrough   CredentialKind = "pass_through"
	CredentialAPIKey        CredentialKind = "api_key"
	CredentialBearer        CredentialKind = "bearer"
	CredentialOAuth2        CredentialKind = "oauth2"
	CredentialOIDC          CredentialKind = "oidc"
	CredentialMTLS          CredentialKind = "mtls"
	CredentialTokenExchange CredentialKind = "token_exchange"
)

// ErrCredentialRequired is returned by a resolver when the caller must
// complete an interactive or delegated authorization step before dispatch.
// Callers should map this to an A2A auth-required task, not expose the error
// detail to the remote agent.
var ErrCredentialRequired = errors.New("credential input required")

type CredentialRequest struct {
	TenantID     string
	TaskID       string
	Endpoint     string
	CardDigest   string
	SchemeID     string
	Scheme       a2adiscovery.SecurityScheme
	Scopes       []string
	SubjectToken string
	ActorToken   string
	// OAuthConfigID selects a server-level OAuth credential when AuthMode is
	// MCPAuthModeNone. Per-identity lookups require AuthMode, Identity, and
	// MCPClientID together; the adapter never silently falls back between them.
	OAuthConfigID string
	AuthMode      schemas.MCPAuthMode
	Identity      string
	MCPClientID   string
	// TokenExchange opts into an injected RFC 8693/7523 exchange source. The
	// source is called only when this profile is explicitly present and enabled.
	TokenExchange *schemas.MCPTokenExchangeConfig
	// AllowSubjectPassThrough is an explicit caller decision for a bearer
	// scheme. It prevents a resolver from treating any supplied subject token
	// as a downstream credential by accident.
	AllowSubjectPassThrough bool
}

type Credential struct {
	Kind      CredentialKind
	Headers   http.Header
	ExpiresAt int64
}

type CredentialResolver interface {
	Resolve(context.Context, CredentialRequest) (Credential, error)
}

type CredentialResolverFunc func(context.Context, CredentialRequest) (Credential, error)

func (f CredentialResolverFunc) Resolve(ctx context.Context, request CredentialRequest) (Credential, error) {
	return f(ctx, request)
}

// CredentialPolicy is the operator-controlled boundary around remote agent
// credentials. An empty AllowedHosts list is intentionally not an allow-all:
// callers must explicitly opt into a host, which keeps card discovery and
// outbound credential use fail-closed.
type CredentialPolicy struct {
	AllowedHosts     []string
	AllowedKinds     []CredentialKind
	AllowPassThrough bool
}

func (p CredentialPolicy) validateEndpoint(endpoint string) error {
	u, err := url.Parse(endpoint)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" || u.User != nil {
		return fmt.Errorf("A2A credential endpoint must be an HTTPS URL without userinfo")
	}
	if len(p.AllowedHosts) == 0 {
		return fmt.Errorf("A2A credential endpoint is not allowlisted")
	}
	host := strings.ToLower(u.Hostname())
	for _, allowed := range p.AllowedHosts {
		if strings.EqualFold(strings.TrimSpace(allowed), host) {
			return nil
		}
	}
	return fmt.Errorf("A2A credential endpoint host is not allowlisted")
}

func (p CredentialPolicy) allows(kind CredentialKind) bool {
	if kind == CredentialPassThrough && !p.AllowPassThrough {
		return false
	}
	if len(p.AllowedKinds) == 0 {
		return true
	}
	for _, allowed := range p.AllowedKinds {
		if allowed == kind {
			return true
		}
	}
	return false
}

// SelectSecurityScheme deterministically chooses a declared scheme. An
// explicit scheme ID is required when the card offers multiple alternatives;
// this prevents a caller from silently changing the trust or delegation mode
// by reordering a card's map keys.
func SelectSecurityScheme(card *a2adiscovery.AgentCard, schemeID string) (string, a2adiscovery.SecurityScheme, error) {
	if card == nil {
		return "", a2adiscovery.SecurityScheme{}, fmt.Errorf("agent card is required")
	}
	if len(card.SecuritySchemes) == 0 {
		return "", a2adiscovery.SecurityScheme{}, fmt.Errorf("agent card declares no credential scheme")
	}
	if schemeID != "" {
		scheme, ok := card.SecuritySchemes[schemeID]
		if !ok {
			return "", a2adiscovery.SecurityScheme{}, fmt.Errorf("credential scheme is not declared")
		}
		return schemeID, scheme, nil
	}
	requirements := card.Security
	if len(requirements) == 0 {
		requirements = card.SecurityRequirements
	}
	for _, requirement := range requirements {
		ids := make([]string, 0, len(requirement))
		for id := range requirement {
			ids = append(ids, id)
		}
		sort.Strings(ids)
		for _, id := range ids {
			if scheme, ok := card.SecuritySchemes[id]; ok {
				return id, scheme, nil
			}
		}
	}
	if len(card.SecuritySchemes) == 1 {
		for id, scheme := range card.SecuritySchemes {
			return id, scheme, nil
		}
	}
	return "", a2adiscovery.SecurityScheme{}, fmt.Errorf("credential scheme selection is ambiguous")
}

func kindForScheme(scheme a2adiscovery.SecurityScheme) (CredentialKind, error) {
	switch strings.ToLower(strings.TrimSpace(scheme.Type)) {
	case "apikey":
		return CredentialAPIKey, nil
	case "http":
		switch strings.ToLower(strings.TrimSpace(scheme.Scheme)) {
		case "bearer":
			return CredentialBearer, nil
		default:
			return CredentialBearer, nil
		}
	case "oauth2":
		return CredentialOAuth2, nil
	case "openidconnect":
		return CredentialOIDC, nil
	case "mutualtls", "mtls":
		return CredentialMTLS, nil
	default:
		return "", fmt.Errorf("unsupported A2A credential scheme")
	}
}

func requiredScopes(card *a2adiscovery.AgentCard, schemeID string) []string {
	requirements := card.Security
	if len(requirements) == 0 {
		requirements = card.SecurityRequirements
	}
	for _, requirement := range requirements {
		if scopes, ok := requirement[schemeID]; ok {
			return append([]string(nil), scopes...)
		}
	}
	return nil
}

func compatibleCredentialKind(declared, resolved CredentialKind) bool {
	if resolved == CredentialPassThrough || resolved == CredentialTokenExchange {
		return declared == CredentialBearer || declared == CredentialOAuth2 || declared == CredentialOIDC
	}
	return declared == resolved
}

func (c Credential) validated(scheme a2adiscovery.SecurityScheme, policy CredentialPolicy) (Credential, error) {
	kind := c.Kind
	if kind == "" {
		var err error
		kind, err = kindForScheme(scheme)
		if err != nil {
			return Credential{}, err
		}
	}
	declaredKind, err := kindForScheme(scheme)
	if err != nil || !compatibleCredentialKind(declaredKind, kind) {
		return Credential{}, fmt.Errorf("credential kind does not match the declared scheme")
	}
	if !policy.allows(kind) {
		return Credential{}, fmt.Errorf("A2A credential kind is not allowed")
	}
	result := Credential{Kind: kind, ExpiresAt: c.ExpiresAt, Headers: c.Headers.Clone()}
	for key, values := range result.Headers {
		canonical := http.CanonicalHeaderKey(key)
		if canonical == "Host" || canonical == "Content-Length" || strings.HasPrefix(strings.ToLower(canonical), "x-forwarded-") || strings.EqualFold(canonical, "Cookie") {
			return Credential{}, fmt.Errorf("credential contains a forbidden downstream header")
		}
		result.Headers[canonical] = append([]string(nil), values...)
		if key != canonical {
			delete(result.Headers, key)
		}
	}
	switch kind {
	case CredentialBearer, CredentialOAuth2, CredentialOIDC, CredentialPassThrough, CredentialTokenExchange:
		if len(result.Headers) != 1 || len(result.Headers.Values("Authorization")) != 1 {
			return Credential{}, fmt.Errorf("bearer credentials must contain one Authorization header")
		}
	case CredentialAPIKey:
		if !strings.EqualFold(scheme.In, "header") || strings.TrimSpace(scheme.Name) == "" || len(result.Headers) != 1 || len(result.Headers.Values(scheme.Name)) != 1 {
			return Credential{}, fmt.Errorf("API-key credentials must contain the declared header")
		}
	case CredentialMTLS:
		if len(result.Headers) != 0 {
			return Credential{}, fmt.Errorf("mTLS credentials cannot be represented as HTTP headers")
		}
	}
	return result, nil
}

// ResolveCredential validates the card declaration, endpoint policy, and the
// resolver result before any downstream sender sees credentials.
func ResolveCredential(ctx context.Context, request CredentialRequest, card *a2adiscovery.AgentCard, policy CredentialPolicy, resolver CredentialResolver) (Credential, error) {
	if resolver == nil {
		return Credential{}, fmt.Errorf("credential resolver is required")
	}
	if strings.TrimSpace(request.TenantID) == "" || strings.TrimSpace(request.TaskID) == "" || strings.TrimSpace(request.CardDigest) == "" {
		return Credential{}, fmt.Errorf("tenant, task, and card digest are required for credential resolution")
	}
	if err := policy.validateEndpoint(request.Endpoint); err != nil {
		return Credential{}, err
	}
	id, scheme, err := SelectSecurityScheme(card, request.SchemeID)
	if err != nil {
		return Credential{}, err
	}
	request.SchemeID, request.Scheme = id, scheme
	declaredScopes := requiredScopes(card, id)
	if len(request.Scopes) == 0 {
		request.Scopes = declaredScopes
	}
	for _, required := range declaredScopes {
		found := false
		for _, requested := range request.Scopes {
			if requested == required {
				found = true
				break
			}
		}
		if !found {
			return Credential{}, fmt.Errorf("requested credential scopes do not satisfy the declared requirement")
		}
	}
	credential, err := resolver.Resolve(ctx, request)
	if err != nil {
		if errors.Is(err, ErrCredentialRequired) {
			return Credential{}, ErrCredentialRequired
		}
		return Credential{}, fmt.Errorf("resolve A2A credential: %w", err)
	}
	return credential.validated(scheme, policy)
}

// DispatchWithCredentials resolves a credential after task admission and
// before transport dispatch. Interactive authorization becomes a durable task
// state rather than an opaque transport error.
func (b *Broker) DispatchWithCredentials(ctx context.Context, taskID string, payload []byte, sender Sender, card *a2adiscovery.AgentCard, request CredentialRequest, policy CredentialPolicy, resolver CredentialResolver) (Task, error) {
	task, ok := b.Get(taskID)
	if !ok {
		return Task{}, fmt.Errorf("task %q not found", taskID)
	}
	if request.TaskID == "" {
		request.TaskID = task.ID
	}
	if request.Endpoint == "" {
		request.Endpoint = task.Endpoint
	}
	if request.CardDigest == "" {
		request.CardDigest = task.CardDigest
	}
	credential, err := ResolveCredential(ctx, request, card, policy, resolver)
	if err != nil {
		if errors.Is(err, ErrCredentialRequired) {
			return b.Apply(taskID, Event{State: StateAuthRequired, Error: "authentication required", At: b.now()})
		}
		return Task{}, err
	}
	return b.dispatch(ctx, taskID, payload, sender, credential.Headers)
}
