// Package tokenexchange implements the small, security-sensitive OAuth
// exchange surface needed for MCP/A2A downstream calls.
package tokenexchange

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

const (
	tokenExchangeGrantType = "urn:ietf:params:oauth:grant-type:token-exchange"
	jwtBearerGrantType     = "urn:ietf:params:oauth:grant-type:jwt-bearer"
	accessTokenType        = "urn:ietf:params:oauth:token-type:access_token"
	defaultCacheSkew       = 30 * time.Second
	defaultHTTPTimeout     = 15 * time.Second
	defaultMaxCacheEntries = 256
	defaultMaxTokenTTL     = 5 * time.Minute
	maxTokenResponseBytes  = 1 << 20
)

var (
	ErrDisabled          = errors.New("token exchange is disabled")
	ErrMissingSubject    = errors.New("token exchange subject token is missing")
	ErrInvalidConfig     = errors.New("invalid token exchange configuration")
	ErrInvalidTokenReply = errors.New("token endpoint returned no access token")
)

type cachedToken struct {
	value     string
	expiresAt time.Time
	lastUsed  time.Time
}

type inFlight struct {
	done  chan struct{}
	token string
	err   error
}

// Exchanger is safe for concurrent use. The cache stores only short-lived
// exchanged credentials in memory; it never persists the subject, actor, or
// client secret. Cache keys are one-way digests of request inputs.
type Exchanger struct {
	client *http.Client
	now    func() time.Time

	mu       sync.Mutex
	cache    map[string]cachedToken
	inFlight map[string]*inFlight
}

func New(client *http.Client) *Exchanger {
	if client == nil {
		client = http.DefaultClient
	}
	copy := *client
	// Token endpoints are never allowed to redirect. A redirect can turn a
	// trusted credential egress into an SSRF or credential disclosure path.
	copy.CheckRedirect = func(_ *http.Request, _ []*http.Request) error {
		return errors.New("token endpoint redirects are disabled")
	}
	if copy.Timeout == 0 {
		copy.Timeout = defaultHTTPTimeout
	}
	return &Exchanger{
		client:   &copy,
		now:      time.Now,
		cache:    make(map[string]cachedToken),
		inFlight: make(map[string]*inFlight),
	}
}

// ExchangeFromContext resolves the configured subject and actor headers from
// the request context and exchanges them. The request header map is populated
// by the HTTP transport after authentication. Values are never logged.
func (e *Exchanger) ExchangeFromContext(ctx context.Context, config *schemas.MCPTokenExchangeConfig) (string, error) {
	if config == nil || !config.Enabled {
		return "", ErrDisabled
	}
	headers, _ := ctx.Value(schemas.BifrostContextKeyRequestHeaders).(map[string]string)
	subjectHeader := strings.ToLower(strings.TrimSpace(config.SubjectTokenHeader))
	if subjectHeader == "" {
		subjectHeader = "authorization"
	}
	subjectToken := headerValue(headers, subjectHeader)
	if strings.EqualFold(subjectHeader, "authorization") {
		subjectToken = bearerValue(subjectToken)
	}
	actorToken := ""
	actorHeader := strings.ToLower(strings.TrimSpace(config.ActorTokenHeader))
	if actorHeader != "" {
		actorToken = headerValue(headers, actorHeader)
		if strings.EqualFold(actorHeader, "authorization") {
			actorToken = bearerValue(actorToken)
		}
	}
	return e.Exchange(ctx, config, subjectToken, actorToken)
}

func (e *Exchanger) Exchange(ctx context.Context, config *schemas.MCPTokenExchangeConfig, subjectToken, actorToken string) (string, error) {
	if config == nil || !config.Enabled {
		return "", ErrDisabled
	}
	subjectToken = strings.TrimSpace(subjectToken)
	if subjectToken == "" {
		return "", ErrMissingSubject
	}
	if err := validateConfig(config); err != nil {
		return "", err
	}
	grant := config.Grant
	if grant == "" {
		grant = schemas.MCPTokenExchangeGrantTokenExchange
	}
	if grant == schemas.MCPTokenExchangeGrantTokenExchange && config.ActorTokenHeader != "" && strings.TrimSpace(actorToken) == "" {
		return "", fmt.Errorf("%w: configured actor token was not supplied", ErrMissingSubject)
	}

	now := e.now()
	key := cacheKey(config, subjectToken, actorToken)
	if token, ok := e.cached(key, now); ok {
		return token, nil
	}
	flight, leader := e.begin(key)
	if !leader {
		select {
		case <-flight.done:
			return flight.token, flight.err
		case <-ctx.Done():
			return "", ctx.Err()
		}
	}

	token, err := e.exchange(ctx, config, subjectToken, actorToken, now, key)
	e.finish(key, flight, token, err)
	return token, err
}

// ValidateConfig validates an exchange profile without performing network I/O.
// Management APIs and config reconciliation use this before persisting a
// profile, while Exchange repeats validation at the request boundary.
func ValidateConfig(config *schemas.MCPTokenExchangeConfig) error {
	if config == nil || !config.Enabled {
		return nil
	}
	return validateConfig(config)
}

func (e *Exchanger) exchange(ctx context.Context, config *schemas.MCPTokenExchangeConfig, subjectToken, actorToken string, now time.Time, key string) (string, error) {
	form, err := buildForm(config, subjectToken, actorToken)
	if err != nil {
		return "", err
	}
	if config.ClientAuthMethod == schemas.MCPTokenExchangeClientAuthPost {
		form.Set("client_id", config.ClientID.GetValue())
		form.Set("client_secret", config.ClientSecret.GetValue())
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, config.TokenURL.GetValue(), strings.NewReader(form.Encode()))
	if err != nil {
		return "", fmt.Errorf("%w: token endpoint request could not be created", ErrInvalidConfig)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if config.ClientAuthMethod == "" || config.ClientAuthMethod == schemas.MCPTokenExchangeClientAuthBasic {
		req.SetBasicAuth(config.ClientID.GetValue(), config.ClientSecret.GetValue())
	}

	resp, err := e.client.Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		return "", errors.New("token endpoint request failed")
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxTokenResponseBytes+1))
	if err != nil {
		return "", errors.New("token endpoint response unreadable")
	}
	if len(body) > maxTokenResponseBytes {
		return "", errors.New("token endpoint response exceeded the safety limit")
	}
	var reply tokenReply
	if err := json.Unmarshal(body, &reply); err != nil {
		return "", fmt.Errorf("token exchange failed with HTTP %d", resp.StatusCode)
	}
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		if safe := safeOAuthError(reply.Error); safe != "" {
			return "", fmt.Errorf("token exchange rejected: %s", safe)
		}
		return "", fmt.Errorf("token exchange failed with HTTP %d", resp.StatusCode)
	}
	if strings.TrimSpace(reply.AccessToken) == "" {
		return "", ErrInvalidTokenReply
	}

	expiresIn := time.Duration(reply.ExpiresIn) * time.Second
	if expiresIn <= 0 {
		// RFC 8693 permits an omitted expires_in. Do not cache an unbounded token.
		expiresIn = 30 * time.Second
	}
	maxTTL := defaultMaxTokenTTL
	if config.MaxTokenTTLSeconds > 0 {
		maxTTL = time.Duration(config.MaxTokenTTLSeconds) * time.Second
	}
	if expiresIn > maxTTL {
		expiresIn = maxTTL
	}
	if subjectExpiry, ok := jwtExpiry(subjectToken); ok {
		if until := subjectExpiry.Sub(now); until < expiresIn {
			expiresIn = until
		}
	}
	skew := defaultCacheSkew
	if config.CacheSkewSeconds > 0 {
		skew = time.Duration(config.CacheSkewSeconds) * time.Second
	}
	cacheFor := expiresIn - skew
	if cacheFor > 0 {
		e.put(key, cachedToken{value: reply.AccessToken, expiresAt: now.Add(cacheFor), lastUsed: now}, config.MaxCacheEntries)
	}
	return reply.AccessToken, nil
}

type tokenReply struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int64  `json:"expires_in"`
	Error       string `json:"error"`
}

func buildForm(config *schemas.MCPTokenExchangeConfig, subjectToken, actorToken string) (url.Values, error) {
	form := url.Values{}
	grant := config.Grant
	if grant == "" {
		grant = schemas.MCPTokenExchangeGrantTokenExchange
	}
	switch grant {
	case schemas.MCPTokenExchangeGrantTokenExchange:
		form.Set("grant_type", tokenExchangeGrantType)
		form.Set("subject_token", subjectToken)
		subjectType := config.SubjectTokenType
		if subjectType == "" {
			subjectType = accessTokenType
		}
		form.Set("subject_token_type", subjectType)
		if config.RequestedTokenType != "" {
			form.Set("requested_token_type", config.RequestedTokenType)
		}
		if actorToken != "" {
			form.Set("actor_token", actorToken)
			actorType := config.ActorTokenType
			if actorType == "" {
				actorType = accessTokenType
			}
			form.Set("actor_token_type", actorType)
		}
	case schemas.MCPTokenExchangeGrantJWTBearer:
		form.Set("grant_type", jwtBearerGrantType)
		form.Set("assertion", subjectToken)
	default:
		return nil, fmt.Errorf("%w: unsupported grant %q", ErrInvalidConfig, grant)
	}
	addValues(form, "audience", config.Audience)
	addValues(form, "resource", config.Resource)
	addValues(form, "scope", config.Scope)
	if config.RequestedTokenUse != "" {
		form.Set("requested_token_use", config.RequestedTokenUse)
	}
	for key, value := range config.AdditionalParameters {
		key = strings.TrimSpace(key)
		if key == "" || form.Has(key) || key == "client_id" || key == "client_secret" {
			continue
		}
		form.Set(key, value)
	}
	return form, nil
}

func addValues(form url.Values, key string, values []string) {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			form.Add(key, value)
		}
	}
}

func validateConfig(config *schemas.MCPTokenExchangeConfig) error {
	if config.TokenURL == nil || strings.TrimSpace(config.TokenURL.GetValue()) == "" {
		return fmt.Errorf("%w: token_url is required", ErrInvalidConfig)
	}
	u, err := url.Parse(config.TokenURL.GetValue())
	if err != nil || u.Scheme == "" || u.Host == "" {
		return fmt.Errorf("%w: token_url must be an absolute URL", ErrInvalidConfig)
	}
	if u.User != nil || u.Fragment != "" {
		return fmt.Errorf("%w: token_url must not contain userinfo or a fragment", ErrInvalidConfig)
	}
	if u.Scheme != "https" && !(config.AllowInsecureHTTP && u.Scheme == "http") {
		return fmt.Errorf("%w: token_url must use https unless allow_insecure_http is enabled", ErrInvalidConfig)
	}
	if !hostAllowed(u, config.AllowedHosts) {
		return fmt.Errorf("%w: token endpoint host is not allowlisted", ErrInvalidConfig)
	}
	if config.ClientAuthMethod != "" && config.ClientAuthMethod != schemas.MCPTokenExchangeClientAuthBasic && config.ClientAuthMethod != schemas.MCPTokenExchangeClientAuthPost {
		return fmt.Errorf("%w: unsupported client authentication profile", ErrInvalidConfig)
	}
	if config.ClientID == nil || config.ClientSecret == nil || strings.TrimSpace(config.ClientID.GetValue()) == "" || strings.TrimSpace(config.ClientSecret.GetValue()) == "" {
		return fmt.Errorf("%w: client_id and client_secret are required", ErrInvalidConfig)
	}
	if config.MaxCacheEntries < 0 || config.MaxTokenTTLSeconds < 0 || config.TimeoutSeconds < 0 {
		return fmt.Errorf("%w: limits cannot be negative", ErrInvalidConfig)
	}
	return nil
}

func hostAllowed(endpoint *url.URL, allowed []string) bool {
	host := strings.ToLower(endpoint.Host)
	hostname := strings.ToLower(endpoint.Hostname())
	for _, candidate := range allowed {
		candidate = strings.ToLower(strings.TrimSpace(candidate))
		if candidate == "" {
			continue
		}
		if strings.HasPrefix(candidate, "*.") && strings.HasSuffix(hostname, candidate[1:]) {
			return true
		}
		if candidate == host || candidate == hostname {
			return true
		}
	}
	return false
}

func (e *Exchanger) cached(key string, now time.Time) (string, bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	entry, ok := e.cache[key]
	if !ok || !now.Before(entry.expiresAt) {
		if ok {
			delete(e.cache, key)
		}
		return "", false
	}
	entry.lastUsed = now
	e.cache[key] = entry
	return entry.value, true
}

func (e *Exchanger) begin(key string) (*inFlight, bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if existing, ok := e.inFlight[key]; ok {
		return existing, false
	}
	flight := &inFlight{done: make(chan struct{})}
	e.inFlight[key] = flight
	return flight, true
}

func (e *Exchanger) finish(key string, flight *inFlight, token string, err error) {
	e.mu.Lock()
	flight.token, flight.err = token, err
	delete(e.inFlight, key)
	close(flight.done)
	e.mu.Unlock()
}

func (e *Exchanger) put(key string, token cachedToken, maxEntries int) {
	e.mu.Lock()
	defer e.mu.Unlock()
	limit := defaultMaxCacheEntries
	if maxEntries > 0 {
		limit = maxEntries
	}
	e.cache[key] = token
	for len(e.cache) > limit {
		oldestKey := ""
		var oldest time.Time
		for candidate, entry := range e.cache {
			if candidate == key {
				continue
			}
			if oldestKey == "" || entry.lastUsed.Before(oldest) {
				oldestKey, oldest = candidate, entry.lastUsed
			}
		}
		if oldestKey == "" {
			break
		}
		delete(e.cache, oldestKey)
	}
}

func headerValue(headers map[string]string, name string) string {
	for key, value := range headers {
		if strings.EqualFold(key, name) {
			return value
		}
	}
	return ""
}

func bearerValue(value string) string {
	if len(value) >= 7 && strings.EqualFold(value[:7], "bearer ") {
		return strings.TrimSpace(value[7:])
	}
	return value
}

func cacheKey(config *schemas.MCPTokenExchangeConfig, subjectToken, actorToken string) string {
	h := sha256.New()
	write := func(value string) {
		h.Write([]byte(strconv.Itoa(len(value))))
		h.Write([]byte(":"))
		h.Write([]byte(value))
	}
	write(config.TokenURL.GetValue())
	write(string(config.Grant))
	write(strings.Join(config.Audience, "\x00"))
	write(strings.Join(config.Resource, "\x00"))
	write(strings.Join(config.Scope, "\x00"))
	if config.ClientID != nil {
		write(config.ClientID.GetValue())
	}
	for _, value := range []string{subjectToken, actorToken} {
		digest := sha256.Sum256([]byte(value))
		write(hex.EncodeToString(digest[:]))
	}
	return hex.EncodeToString(h.Sum(nil))
}

func jwtExpiry(token string) (time.Time, bool) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return time.Time{}, false
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return time.Time{}, false
	}
	var claims struct {
		Exp json.Number `json:"exp"`
	}
	if err := json.Unmarshal(payload, &claims); err != nil {
		return time.Time{}, false
	}
	seconds, err := claims.Exp.Int64()
	if err != nil || seconds <= 0 {
		return time.Time{}, false
	}
	return time.Unix(seconds, 0), true
}

func safeOAuthError(value string) string {
	value = strings.TrimSpace(value)
	if len(value) > 64 {
		return "oauth_error"
	}
	for _, r := range value {
		if (r < 'a' || r > 'z') && (r < 'A' || r > 'Z') && (r < '0' || r > '9') && r != '_' && r != '-' && r != '.' {
			return "oauth_error"
		}
	}
	return value
}

// ParseExpiresIn is kept small and exported for conformance tests and future
// adapters that receive expires_in as a JSON string.
func ParseExpiresIn(value string) (int64, error) {
	return strconv.ParseInt(strings.TrimSpace(value), 10, 64)
}
