package a2abroker

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
)

const defaultHTTPJSONSenderMaxResponseBytes = 64 << 10

// HTTPJSONSender is the guarded default transport for outbound A2A
// message/send calls. It accepts either the HTTP+JSON task envelope or the
// JSON-RPC result envelope and projects only bounded lifecycle state into the
// broker. Response bodies and remote error details are never copied into task
// history.
//
// The caller must provide an explicit host allowlist. A custom Resolver is
// required for DNS names so the selected address is checked before dialing;
// this prevents a DNS rebinding from bypassing the endpoint policy.
type HTTPJSONSender struct {
	Client           *http.Client
	AllowedHosts     []string
	AllowLoopback    bool
	Resolver         IPResolver
	MaxResponseBytes int
}

type IPResolver interface {
	LookupIPAddr(context.Context, string) ([]net.IPAddr, error)
}

type IPResolverFunc func(context.Context, string) ([]net.IPAddr, error)

func (f IPResolverFunc) LookupIPAddr(ctx context.Context, host string) ([]net.IPAddr, error) {
	return f(ctx, host)
}

func (s HTTPJSONSender) Send(ctx context.Context, request SendRequest) (Event, error) {
	if err := s.validateEndpoint(request.Endpoint); err != nil {
		return Event{}, err
	}
	if request.TaskID == "" {
		return Event{}, errors.New("A2A task ID is required")
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, request.Endpoint, bytes.NewReader(request.Payload))
	if err != nil {
		return Event{}, errors.New("create outbound A2A request")
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json, application/a2a+json")
	req.Header.Set("X-A2A-Task-ID", request.TaskID)
	if request.CardDigest != "" {
		req.Header.Set("X-A2A-Card-Digest", request.CardDigest)
	}
	for key, values := range request.Headers {
		canonical := http.CanonicalHeaderKey(key)
		if forbiddenOutboundHeader(canonical) {
			return Event{}, fmt.Errorf("outbound A2A credential contains forbidden header %q", canonical)
		}
		for _, value := range values {
			req.Header.Add(canonical, value)
		}
	}
	// Preserve the gateway's distributed trace when the caller supplied one.
	// This is intentionally done after credential headers are copied so the
	// credential resolver cannot override propagation metadata.
	otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))

	client, closeIdle, err := s.client()
	if err != nil {
		return Event{}, err
	}
	defer closeIdle()
	response, err := client.Do(req)
	if err != nil {
		return Event{}, errors.New("deliver outbound A2A request")
	}
	defer response.Body.Close()
	body, err := readBounded(response.Body, s.maxResponseBytes())
	if err != nil {
		return Event{}, err
	}
	if response.StatusCode == http.StatusUnauthorized || response.StatusCode == http.StatusForbidden {
		return Event{State: StateAuthRequired, Message: "remote A2A authentication required", At: time.Now().UTC()}, nil
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return Event{State: StateRejected, Error: "remote A2A endpoint rejected the request", At: time.Now().UTC()}, nil
	}
	return parseHTTPJSONEvent(body), nil
}

func (s HTTPJSONSender) validateEndpoint(endpoint string) error {
	u, err := url.Parse(endpoint)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" || u.User != nil {
		return errors.New("outbound A2A endpoint must be an HTTPS URL without userinfo")
	}
	if len(s.AllowedHosts) == 0 {
		return errors.New("outbound A2A endpoint is not allowlisted")
	}
	host := strings.ToLower(u.Hostname())
	for _, allowed := range s.AllowedHosts {
		if strings.EqualFold(strings.TrimSpace(allowed), host) {
			return nil
		}
	}
	return errors.New("outbound A2A endpoint host is not allowlisted")
}

func (s HTTPJSONSender) client() (*http.Client, func(), error) {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	if s.Client != nil && s.Client.Transport != nil {
		base, ok := s.Client.Transport.(*http.Transport)
		if !ok {
			return nil, func() {}, errors.New("outbound A2A HTTP client must use an HTTP transport")
		}
		transport = base.Clone()
	}
	transport.Proxy = nil
	transport.DialContext = s.dialContext()
	client := &http.Client{Transport: transport}
	if s.Client != nil {
		client.Timeout = s.Client.Timeout
	}
	if client.Timeout <= 0 {
		client.Timeout = 15 * time.Second
	}
	client.CheckRedirect = func(_ *http.Request, _ []*http.Request) error {
		return errors.New("outbound A2A redirects are disabled")
	}
	return client, transport.CloseIdleConnections, nil
}

func (s HTTPJSONSender) dialContext() func(context.Context, string, string) (net.Conn, error) {
	dialer := &net.Dialer{}
	return func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil {
			host = address
		}
		if ip := net.ParseIP(host); ip != nil {
			if err := validateOutboundIP(ip, s.AllowLoopback); err != nil {
				return nil, err
			}
			return dialer.DialContext(ctx, network, net.JoinHostPort(host, port))
		}
		if s.Resolver == nil {
			return nil, errors.New("outbound A2A DNS resolution policy is not configured")
		}
		addresses, err := s.Resolver.LookupIPAddr(ctx, host)
		if err != nil || len(addresses) == 0 {
			return nil, errors.New("outbound A2A DNS resolution failed")
		}
		var lastErr error
		for _, candidate := range addresses {
			if err := validateOutboundIP(candidate.IP, s.AllowLoopback); err != nil {
				lastErr = err
				continue
			}
			conn, dialErr := dialer.DialContext(ctx, network, net.JoinHostPort(candidate.IP.String(), port))
			if dialErr == nil {
				return conn, nil
			}
			lastErr = dialErr
		}
		if lastErr != nil {
			return nil, lastErr
		}
		return nil, errors.New("outbound A2A endpoint has no usable address")
	}
}

func validateOutboundIP(ip net.IP, allowLoopback bool) error {
	if ip == nil {
		return errors.New("outbound A2A endpoint resolved to an empty address")
	}
	if ip.IsLoopback() && allowLoopback {
		return nil
	}
	if ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsUnspecified() || ip.IsLoopback() {
		return errors.New("outbound A2A endpoint resolved to a private address")
	}
	return nil
}

func forbiddenOutboundHeader(header string) bool {
	lower := strings.ToLower(header)
	return lower == "host" || lower == "content-length" || lower == "cookie" || strings.HasPrefix(lower, "x-forwarded-")
}

func readBounded(reader io.Reader, max int) ([]byte, error) {
	if max <= 0 {
		max = defaultHTTPJSONSenderMaxResponseBytes
	}
	body, err := io.ReadAll(io.LimitReader(reader, int64(max)+1))
	if err != nil {
		return nil, errors.New("read outbound A2A response")
	}
	if len(body) > max {
		return nil, fmt.Errorf("outbound A2A response exceeds %d bytes", max)
	}
	return body, nil
}

func (s HTTPJSONSender) maxResponseBytes() int {
	if s.MaxResponseBytes > 0 {
		return s.MaxResponseBytes
	}
	return defaultHTTPJSONSenderMaxResponseBytes
}

func parseHTTPJSONEvent(body []byte) Event {
	now := time.Now().UTC()
	if len(strings.TrimSpace(string(body))) == 0 {
		return Event{State: StateWorking, Retryable: true, At: now}
	}
	var envelope struct {
		Result json.RawMessage `json:"result"`
		Error  json.RawMessage `json:"error"`
		Status struct {
			State string `json:"state"`
		} `json:"status"`
	}
	if json.Unmarshal(body, &envelope) != nil {
		return Event{State: StateWorking, Retryable: true, Error: "remote A2A response was not valid JSON", At: now}
	}
	if len(envelope.Error) > 0 && string(envelope.Error) != "null" {
		return Event{State: StateRejected, Error: "remote A2A JSON-RPC error", At: now}
	}
	status := envelope.Status.State
	if len(envelope.Result) > 0 && string(envelope.Result) != "null" {
		var result struct {
			Status struct {
				State string `json:"state"`
			} `json:"status"`
		}
		if json.Unmarshal(envelope.Result, &result) == nil && result.Status.State != "" {
			status = result.Status.State
		}
	}
	switch strings.ToUpper(strings.TrimSpace(status)) {
	case "TASK_STATE_WORKING", "WORKING":
		return Event{State: StateWorking, At: now}
	case "TASK_STATE_INPUT_REQUIRED", "INPUT_REQUIRED":
		return Event{State: StateInputRequired, Message: "remote A2A input is required", At: now}
	case "TASK_STATE_AUTH_REQUIRED", "AUTH_REQUIRED":
		return Event{State: StateAuthRequired, Message: "remote A2A authentication is required", At: now}
	case "TASK_STATE_FAILED", "FAILED":
		return Event{State: StateFailed, Error: "remote A2A task failed", At: now}
	case "TASK_STATE_CANCELED", "CANCELED", "CANCELLED":
		return Event{State: StateCanceled, Error: "remote A2A task was canceled", At: now}
	case "TASK_STATE_REJECTED", "REJECTED":
		return Event{State: StateRejected, Error: "remote A2A task was rejected", At: now}
	default:
		return Event{State: StateCompleted, Message: "remote A2A task completed", At: now}
	}
}

var _ Sender = HTTPJSONSender{}
