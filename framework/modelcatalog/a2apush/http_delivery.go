package a2apush

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"
)

const (
	defaultHTTPDeliveryTimeout = 15 * time.Second
	defaultMaxResponseBytes    = 64 << 10
)

// SecretResolver resolves an opaque reference at send time. Implementations
// must not persist or log the returned value.
type SecretResolver interface {
	Resolve(context.Context, string) (string, error)
}

type SecretResolverFunc func(context.Context, string) (string, error)

func (f SecretResolverFunc) Resolve(ctx context.Context, ref string) (string, error) {
	if f == nil {
		return "", errors.New("A2A push secret resolver is not configured")
	}
	return f(ctx, ref)
}

// HTTPDelivery is a guarded HTTPS POST sender for A2A push notifications.
// It resolves secret references only at delivery time, disables redirects,
// rechecks DNS/IP policy at connection time, and bounds request/response size.
type HTTPDelivery struct {
	Client           *http.Client
	Secrets          SecretResolver
	Policy           Policy
	Now              func() time.Time
	MaxPayloadBytes  int
	MaxResponseBytes int
}

func (d HTTPDelivery) Deliver(ctx context.Context, request DeliveryRequest) error {
	if strings.TrimSpace(request.DeliveryID) == "" {
		return errors.New("A2A push delivery ID is required")
	}
	maxPayload := d.maxPayloadBytes()
	if len(request.Payload) > maxPayload {
		return fmt.Errorf("A2A push payload exceeds %d bytes", maxPayload)
	}
	if request.PayloadHash != "" && request.PayloadHash != PayloadDigest(request.Payload) {
		return errors.New("A2A push payload digest mismatch")
	}
	if err := ValidateConfig(ctx, request.Config, d.Policy); err != nil {
		return fmt.Errorf("validate A2A push destination: %w", err)
	}

	payload := append([]byte(nil), request.Payload...)
	payloadHash := request.PayloadHash
	if payloadHash == "" {
		payloadHash = PayloadDigest(payload)
	}
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, request.Config.URL, bytes.NewReader(payload))
	if err != nil {
		return errors.New("create A2A push request")
	}
	httpRequest.Header.Set("Content-Type", "application/a2a+json")
	httpRequest.Header.Set("Accept", "application/a2a+json")
	httpRequest.Header.Set("X-A2A-Delivery-ID", request.DeliveryID)
	httpRequest.Header.Set("Idempotency-Key", request.DeliveryID)
	httpRequest.Header.Set("X-A2A-Payload-SHA256", payloadHash)
	httpRequest.Header.Set("X-A2A-Attempt", strconv.Itoa(request.Attempt))

	if request.Config.AuthScheme == "bearer" {
		secret, resolveErr := d.resolveSecret(ctx, request.Config.CredentialRef)
		if resolveErr != nil {
			return fmt.Errorf("resolve A2A push bearer credential: %w", resolveErr)
		}
		httpRequest.Header.Set("Authorization", "Bearer "+secret)
	}
	if request.Config.AuthScheme == "hmac-sha256" {
		secret, resolveErr := d.resolveSecret(ctx, request.Config.SigningSecretRef)
		if resolveErr != nil {
			return fmt.Errorf("resolve A2A push signing secret: %w", resolveErr)
		}
		now := time.Now().UTC()
		if d.Now != nil {
			now = d.Now().UTC()
		}
		timestamp := strconv.FormatInt(now.Unix(), 10)
		httpRequest.Header.Set("X-A2A-Timestamp", timestamp)
		httpRequest.Header.Set("X-A2A-Signature", "sha256="+hmacDigest(secret, timestamp, request.DeliveryID, payloadHash, payload))
	}
	if request.Config.NotificationTokenRef != "" {
		token, resolveErr := d.resolveSecret(ctx, request.Config.NotificationTokenRef)
		if resolveErr != nil {
			return fmt.Errorf("resolve A2A push notification token: %w", resolveErr)
		}
		httpRequest.Header.Set("X-A2A-Notification-Token", token)
	}

	client, closeIdle, err := d.client()
	if err != nil {
		return err
	}
	defer closeIdle()
	response, err := client.Do(httpRequest)
	if err != nil {
		return errors.New("deliver A2A push notification")
	}
	defer response.Body.Close()
	maxResponse := d.maxResponseBytes()
	read, readErr := io.Copy(io.Discard, io.LimitReader(response.Body, int64(maxResponse)+1))
	if readErr != nil {
		return errors.New("read A2A push response")
	}
	if read > int64(maxResponse) {
		return fmt.Errorf("A2A push response exceeds %d bytes", maxResponse)
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("A2A push destination returned HTTP status %d", response.StatusCode)
	}
	return nil
}

func (d HTTPDelivery) resolveSecret(ctx context.Context, ref string) (string, error) {
	if d.Secrets == nil {
		return "", errors.New("A2A push secret resolver is not configured")
	}
	secret, err := d.Secrets.Resolve(ctx, ref)
	if err != nil {
		return "", err
	}
	if strings.TrimSpace(secret) == "" {
		return "", errors.New("A2A push secret is empty")
	}
	return secret, nil
}

func (d HTTPDelivery) maxPayloadBytes() int {
	if d.MaxPayloadBytes > 0 {
		return d.MaxPayloadBytes
	}
	return defaultMaxPayloadBytes
}

func (d HTTPDelivery) maxResponseBytes() int {
	if d.MaxResponseBytes > 0 {
		return d.MaxResponseBytes
	}
	return defaultMaxResponseBytes
}

func (d HTTPDelivery) client() (*http.Client, func(), error) {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	if d.Client != nil && d.Client.Transport != nil {
		base, ok := d.Client.Transport.(*http.Transport)
		if !ok {
			return nil, func() {}, errors.New("A2A push HTTP client must use an HTTP transport")
		}
		transport = base.Clone()
	}
	transport.Proxy = nil
	transport.DialContext = d.dialContext()
	client := &http.Client{Transport: transport}
	if d.Client != nil {
		client.Timeout = d.Client.Timeout
	}
	if client.Timeout <= 0 {
		client.Timeout = defaultHTTPDeliveryTimeout
	}
	client.CheckRedirect = func(_ *http.Request, _ []*http.Request) error {
		return errors.New("A2A push redirects are disabled")
	}
	return client, transport.CloseIdleConnections, nil
}

func (d HTTPDelivery) dialContext() func(context.Context, string, string) (net.Conn, error) {
	dialer := &net.Dialer{}
	return func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil {
			host = address
		}
		if ip := net.ParseIP(host); ip != nil {
			if validateErr := validateIP(ip, d.Policy.AllowLoopback); validateErr != nil {
				return nil, validateErr
			}
			return dialer.DialContext(ctx, network, net.JoinHostPort(host, port))
		}
		if d.Policy.Resolver == nil {
			return nil, errors.New("A2A push URL DNS resolution policy is not configured")
		}
		addresses, err := d.Policy.Resolver.LookupIPAddr(ctx, host)
		if err != nil || len(addresses) == 0 {
			return nil, errors.New("A2A push URL DNS resolution failed")
		}
		var lastErr error
		for _, address := range addresses {
			if validateErr := validateIP(address.IP, d.Policy.AllowLoopback); validateErr != nil {
				lastErr = validateErr
				continue
			}
			conn, dialErr := dialer.DialContext(ctx, network, net.JoinHostPort(address.IP.String(), port))
			if dialErr == nil {
				return conn, nil
			}
			lastErr = dialErr
		}
		if lastErr != nil {
			return nil, lastErr
		}
		return nil, errors.New("A2A push URL has no usable address")
	}
}

// hmacDigest signs a stable request tuple. The delivery ID and payload hash
// bind retries and idempotency metadata to the body, while the timestamp gives
// receivers a replay window they can enforce.
func hmacDigest(secret, timestamp, deliveryID, payloadHash string, payload []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = io.WriteString(mac, timestamp)
	_, _ = io.WriteString(mac, ".")
	_, _ = io.WriteString(mac, deliveryID)
	_, _ = io.WriteString(mac, ".")
	_, _ = io.WriteString(mac, payloadHash)
	_, _ = io.WriteString(mac, ".")
	_, _ = mac.Write(payload)
	return hex.EncodeToString(mac.Sum(nil))
}
