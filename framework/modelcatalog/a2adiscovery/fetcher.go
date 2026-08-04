package a2adiscovery

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type HTTPSPolicy int

const (
	HTTPSOnly HTTPSPolicy = iota
	HTTPSOrHTTP
)

type Resolver interface {
	LookupIPAddr(ctx context.Context, host string) ([]net.IPAddr, error)
}

type ResolverFunc func(ctx context.Context, host string) ([]net.IPAddr, error)

func (f ResolverFunc) LookupIPAddr(ctx context.Context, host string) ([]net.IPAddr, error) {
	return f(ctx, host)
}

type DialContextFunc func(ctx context.Context, network, address string) (net.Conn, error)

type Options struct {
	MaxResponseBytes  int64
	Timeout           time.Duration
	HTTPSPolicy       HTTPSPolicy
	MaxRedirects      int
	AllowedHosts      []string
	AllowedDomains    []string
	AllowedMediaTypes []string
	Resolver          Resolver
	DialContext       DialContextFunc
	TLSClientConfig   *tls.Config
}

type Fetcher struct {
	maxResponseBytes  int64
	timeout           time.Duration
	httpsPolicy       HTTPSPolicy
	maxRedirects      int
	allowedHosts      map[string]struct{}
	allowedDomains    []string
	allowedMediaTypes map[string]struct{}
	resolver          Resolver
	dialContext       DialContextFunc
	client            *http.Client
}

type StatusError struct {
	URL        string
	StatusCode int
}

func (e *StatusError) Error() string {
	return fmt.Sprintf("a2a card fetch %s returned status %d", e.URL, e.StatusCode)
}

func NewFetcher(opts Options) (*Fetcher, error) {
	maxResponseBytes := opts.MaxResponseBytes
	if maxResponseBytes <= 0 {
		maxResponseBytes = DefaultMaxResponseBytes
	}
	timeout := opts.Timeout
	if timeout <= 0 {
		timeout = time.Duration(DefaultTimeoutMillis) * time.Millisecond
	}
	maxRedirects := opts.MaxRedirects
	if maxRedirects < 0 {
		return nil, errors.New("max redirects must be non-negative")
	}
	if maxRedirects == 0 {
		maxRedirects = DefaultMaxRedirects
	}
	allowedHosts := normalizeAllowedHosts(opts.AllowedHosts)
	allowedDomains := normalizeAllowedDomains(opts.AllowedDomains)
	if len(allowedHosts) == 0 && len(allowedDomains) == 0 {
		return nil, errors.New("at least one allowed host or domain is required")
	}
	mediaTypes := normalizeMediaTypes(opts.AllowedMediaTypes)
	if len(mediaTypes) == 0 {
		mediaTypes = normalizeMediaTypes([]string{"application/json", "application/a2a+json", "application/agent-card+json"})
	}
	resolver := opts.Resolver
	if resolver == nil {
		resolver = net.DefaultResolver
	}
	dialContext := opts.DialContext
	if dialContext == nil {
		netDialer := &net.Dialer{Timeout: timeout}
		dialContext = netDialer.DialContext
	}

	f := &Fetcher{
		maxResponseBytes:  maxResponseBytes,
		timeout:           timeout,
		httpsPolicy:       opts.HTTPSPolicy,
		maxRedirects:      maxRedirects,
		allowedHosts:      allowedHosts,
		allowedDomains:    allowedDomains,
		allowedMediaTypes: mediaTypes,
		resolver:          resolver,
		dialContext:       dialContext,
	}

	tlsConfig := opts.TLSClientConfig
	if tlsConfig != nil {
		tlsConfig = tlsConfig.Clone()
	}
	transport := &http.Transport{
		Proxy:                 nil,
		DialContext:           f.safeDialContext,
		TLSClientConfig:       tlsConfig,
		DisableCompression:    true,
		ResponseHeaderTimeout: timeout,
	}
	f.client = &http.Client{
		Timeout:   timeout,
		Transport: transport,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) > f.maxRedirects {
				return fmt.Errorf("redirect limit %d exceeded", f.maxRedirects)
			}
			return f.validateURLPolicy(req.URL)
		},
	}
	return f, nil
}

func (f *Fetcher) Fetch(ctx context.Context, rawURL string) (*FetchResult, error) {
	target, err := parseFetchURL(rawURL)
	if err != nil {
		return nil, err
	}
	candidates := discoveryCandidates(target)
	var lastNotFound *StatusError
	for _, candidate := range candidates {
		result, err := f.fetchURL(ctx, candidate)
		if err == nil {
			return result, nil
		}
		var statusErr *StatusError
		if errors.As(err, &statusErr) && statusErr.StatusCode == http.StatusNotFound && len(candidates) > 1 {
			lastNotFound = statusErr
			continue
		}
		return nil, err
	}
	if lastNotFound != nil {
		return nil, lastNotFound
	}
	return nil, errors.New("no a2a card discovery candidates")
}

func (f *Fetcher) fetchURL(ctx context.Context, target *url.URL) (*FetchResult, error) {
	if err := f.validateURLPolicy(target); err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target.String(), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json, application/a2a+json, application/agent-card+json")
	req.Header.Set("Accept-Encoding", "identity")
	req.Header.Set("User-Agent", "bifrost-a2a-discovery/1")

	resp, err := f.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, &StatusError{URL: resp.Request.URL.String(), StatusCode: resp.StatusCode}
	}
	if err := f.validateContentType(resp.Header.Get("Content-Type")); err != nil {
		return nil, err
	}

	body, err := readBounded(resp.Body, f.maxResponseBytes)
	if err != nil {
		return nil, err
	}
	var card AgentCard
	if err := json.Unmarshal(body, &card); err != nil {
		return nil, fmt.Errorf("decode a2a agent card: %w", err)
	}
	if err := ValidateAgentCard(&card, resp.Request.URL, f.httpsPolicy); err != nil {
		return nil, err
	}
	return &FetchResult{URL: resp.Request.URL.String(), Card: &card}, nil
}

func parseFetchURL(rawURL string) (*url.URL, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return nil, err
	}
	if parsed.Scheme == "" || parsed.Host == "" {
		return nil, errors.New("a2a discovery URL must be absolute")
	}
	if parsed.User != nil {
		return nil, errors.New("a2a discovery URL must not contain userinfo")
	}
	if parsed.Fragment != "" {
		return nil, errors.New("a2a discovery URL must not contain a fragment")
	}
	return parsed, nil
}

func discoveryCandidates(target *url.URL) []*url.URL {
	if (target.Path == "" || target.Path == "/") && target.RawQuery == "" {
		primary := *target
		primary.Path = WellKnownAgentCardPath
		primary.RawPath = ""
		primary.ForceQuery = false
		legacy := *target
		legacy.Path = LegacyAgentCardPath
		legacy.RawPath = ""
		legacy.ForceQuery = false
		return []*url.URL{&primary, &legacy}
	}
	direct := *target
	return []*url.URL{&direct}
}

func (f *Fetcher) validateURLPolicy(target *url.URL) error {
	if target == nil {
		return errors.New("url is required")
	}
	switch target.Scheme {
	case "https":
	case "http":
		if f.httpsPolicy != HTTPSOrHTTP {
			return errors.New("http a2a discovery URLs are disabled by policy")
		}
	default:
		return fmt.Errorf("unsupported a2a discovery URL scheme %q", target.Scheme)
	}
	host := target.Hostname()
	if host == "" {
		return errors.New("a2a discovery URL host is required")
	}
	if isLocalhostName(host) {
		return fmt.Errorf("host %q is denied", host)
	}
	if !f.hostAllowed(host, target.Port()) {
		return fmt.Errorf("host %q is not in the a2a discovery allowlist", host)
	}
	if ip := net.ParseIP(host); ip != nil {
		if err := validatePublicIP(ip); err != nil {
			return err
		}
	}
	return nil
}

func (f *Fetcher) safeDialContext(ctx context.Context, network, address string) (net.Conn, error) {
	host, port, err := net.SplitHostPort(address)
	if err != nil {
		return nil, err
	}
	if port == "" {
		return nil, errors.New("dial address port is required")
	}
	if err := f.validateURLHostForDial(host, port); err != nil {
		return nil, err
	}
	ips, err := f.resolveAndValidate(ctx, host)
	if err != nil {
		return nil, err
	}
	var lastErr error
	for _, ip := range ips {
		conn, err := f.dialContext(ctx, network, net.JoinHostPort(ip.String(), port))
		if err == nil {
			return conn, nil
		}
		lastErr = err
	}
	if lastErr != nil {
		return nil, lastErr
	}
	return nil, fmt.Errorf("host %q resolved to no dialable addresses", host)
}

func (f *Fetcher) validateURLHostForDial(host, port string) error {
	if host == "" {
		return errors.New("dial host is required")
	}
	if isLocalhostName(host) {
		return fmt.Errorf("host %q is denied", host)
	}
	if !f.hostAllowed(host, port) {
		return fmt.Errorf("host %q is not in the a2a discovery allowlist", host)
	}
	return nil
}

func (f *Fetcher) resolveAndValidate(ctx context.Context, host string) ([]net.IP, error) {
	if ip := net.ParseIP(host); ip != nil {
		if err := validatePublicIP(ip); err != nil {
			return nil, err
		}
		return []net.IP{ip}, nil
	}
	addrs, err := f.resolver.LookupIPAddr(ctx, strings.TrimSuffix(host, "."))
	if err != nil {
		return nil, err
	}
	if len(addrs) == 0 {
		return nil, fmt.Errorf("host %q resolved to no addresses", host)
	}
	ips := make([]net.IP, 0, len(addrs))
	for _, addr := range addrs {
		if addr.IP == nil {
			continue
		}
		if err := validatePublicIP(addr.IP); err != nil {
			return nil, fmt.Errorf("host %q resolved to denied address %s: %w", host, addr.IP.String(), err)
		}
		ips = append(ips, addr.IP)
	}
	if len(ips) == 0 {
		return nil, fmt.Errorf("host %q resolved to no usable addresses", host)
	}
	return ips, nil
}

func validatePublicIP(ip net.IP) error {
	if ip == nil {
		return errors.New("ip address is required")
	}
	parsed := ip
	if v4 := ip.To4(); v4 != nil {
		parsed = v4
	}
	if parsed.IsUnspecified() {
		return fmt.Errorf("ip %s is unspecified", ip.String())
	}
	if parsed.IsLoopback() {
		return fmt.Errorf("ip %s is loopback", ip.String())
	}
	if parsed.IsPrivate() {
		return fmt.Errorf("ip %s is private", ip.String())
	}
	if parsed.IsLinkLocalUnicast() || parsed.IsLinkLocalMulticast() {
		return fmt.Errorf("ip %s is link-local", ip.String())
	}
	if parsed.IsMulticast() {
		return fmt.Errorf("ip %s is multicast", ip.String())
	}
	return nil
}

func (f *Fetcher) validateContentType(value string) error {
	if value == "" {
		return errors.New("a2a agent card response is missing content-type")
	}
	mediaType, _, err := mime.ParseMediaType(value)
	if err != nil {
		return fmt.Errorf("invalid a2a agent card content-type: %w", err)
	}
	mediaType = strings.ToLower(mediaType)
	if _, ok := f.allowedMediaTypes[mediaType]; !ok {
		return fmt.Errorf("unsupported a2a agent card content-type %q", mediaType)
	}
	return nil
}

func readBounded(reader io.Reader, maxBytes int64) ([]byte, error) {
	limited := io.LimitReader(reader, maxBytes+1)
	body, err := io.ReadAll(limited)
	if err != nil {
		return nil, err
	}
	if int64(len(body)) > maxBytes {
		return nil, fmt.Errorf("a2a agent card response exceeds %d bytes", maxBytes)
	}
	return body, nil
}

func (f *Fetcher) hostAllowed(host, port string) bool {
	host = normalizeHost(host)
	if host == "" {
		return false
	}
	if port != "" {
		if _, ok := f.allowedHosts[net.JoinHostPort(host, port)]; ok {
			return true
		}
	}
	if _, ok := f.allowedHosts[host]; ok {
		return true
	}
	for _, domain := range f.allowedDomains {
		if host == domain || strings.HasSuffix(host, "."+domain) {
			return true
		}
	}
	return false
}

func normalizeAllowedHosts(values []string) map[string]struct{} {
	out := make(map[string]struct{}, len(values))
	for _, value := range values {
		value = strings.TrimSpace(strings.ToLower(value))
		if value == "" {
			continue
		}
		if strings.Contains(value, ":") {
			if host, port, err := net.SplitHostPort(value); err == nil {
				out[net.JoinHostPort(normalizeHost(host), port)] = struct{}{}
				continue
			}
		}
		out[normalizeHost(value)] = struct{}{}
	}
	return out
}

func normalizeAllowedDomains(values []string) []string {
	out := make([]string, 0, len(values))
	seen := make(map[string]struct{}, len(values))
	for _, value := range values {
		value = normalizeHost(strings.TrimPrefix(strings.TrimSpace(value), "."))
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		out = append(out, value)
	}
	return out
}

func normalizeMediaTypes(values []string) map[string]struct{} {
	out := make(map[string]struct{}, len(values))
	for _, value := range values {
		value = strings.TrimSpace(strings.ToLower(value))
		if value == "" {
			continue
		}
		out[value] = struct{}{}
	}
	return out
}

func normalizeHost(host string) string {
	host = strings.TrimSpace(strings.ToLower(host))
	host = strings.TrimSuffix(host, ".")
	if strings.HasPrefix(host, "[") && strings.HasSuffix(host, "]") {
		host = strings.TrimPrefix(strings.TrimSuffix(host, "]"), "[")
	}
	return host
}

func isLocalhostName(host string) bool {
	host = normalizeHost(host)
	return host == "localhost" || strings.HasSuffix(host, ".localhost")
}

func sameOrigin(a, b *url.URL) bool {
	if a == nil || b == nil {
		return false
	}
	return strings.EqualFold(a.Scheme, b.Scheme) &&
		strings.EqualFold(normalizeHost(a.Hostname()), normalizeHost(b.Hostname())) &&
		effectivePort(a) == effectivePort(b)
}

func effectivePort(u *url.URL) string {
	if port := u.Port(); port != "" {
		return port
	}
	switch u.Scheme {
	case "https":
		return "443"
	case "http":
		return "80"
	default:
		return ""
	}
}
