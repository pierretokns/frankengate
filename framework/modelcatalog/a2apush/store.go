// Package a2apush contains the durable, secret-reference-only state model for
// A2A push notifications. It deliberately has no network sender: delivery is
// an operator-approved egress seam implemented by the transport layer.
package a2apush

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

var (
	ErrNotFound      = errors.New("A2A push configuration not found")
	ErrAlreadyExists = errors.New("A2A push configuration already exists")
	ErrDisabled      = errors.New("A2A push notifications are disabled")
	ErrSecretRef     = errors.New("A2A push credentials must be references, not inline secrets")
)

// Config contains no bearer tokens, signing keys, cookies, or arbitrary
// headers. CredentialRef and SigningSecretRef are opaque references resolved
// only by an approved delivery implementation at send time.
type Config struct {
	ID                   string    `json:"id"`
	TaskID               string    `json:"taskId"`
	TenantID             string    `json:"tenantId"`
	URL                  string    `json:"url"`
	AuthScheme           string    `json:"authScheme,omitempty"`
	CredentialRef        string    `json:"credentialRef,omitempty"`
	SigningSecretRef     string    `json:"signingSecretRef,omitempty"`
	NotificationTokenRef string    `json:"notificationTokenRef,omitempty"`
	CreatedAt            time.Time `json:"createdAt"`
	UpdatedAt            time.Time `json:"updatedAt"`
}

type Policy struct {
	AllowedHosts         []string
	Resolver             Resolver
	AllowLoopback        bool
	RequireDNSResolution bool
}

type Resolver interface {
	LookupIPAddr(context.Context, string) ([]net.IPAddr, error)
}

type ResolverFunc func(context.Context, string) ([]net.IPAddr, error)

func (f ResolverFunc) LookupIPAddr(ctx context.Context, host string) ([]net.IPAddr, error) {
	return f(ctx, host)
}

type Store interface {
	Create(context.Context, Config) error
	Get(context.Context, string, string, string) (Config, error)
	List(context.Context, string, string) ([]Config, error)
	Delete(context.Context, string, string, string) error
}

func ValidateConfig(ctx context.Context, cfg Config, policy Policy) error {
	if strings.TrimSpace(cfg.ID) == "" || len(cfg.ID) > 128 || strings.TrimSpace(cfg.TaskID) == "" || strings.TrimSpace(cfg.TenantID) == "" {
		return errors.New("A2A push configuration identity is required")
	}
	if strings.TrimSpace(cfg.URL) == "" {
		return errors.New("A2A push URL is required")
	}
	u, err := url.Parse(cfg.URL)
	if err != nil || u.User != nil || u.Fragment != "" || u.Hostname() == "" || u.Scheme != "https" {
		return errors.New("A2A push URL must be an HTTPS URL without userinfo or fragments")
	}
	if !hostAllowed(u.Hostname(), policy.AllowedHosts) {
		return errors.New("A2A push URL host is not allowlisted")
	}
	if ip := net.ParseIP(u.Hostname()); ip != nil {
		if err := validateIP(ip, policy.AllowLoopback); err != nil {
			return err
		}
	} else if policy.RequireDNSResolution && policy.Resolver == nil {
		return errors.New("A2A push URL DNS resolution policy is not configured")
	} else if policy.Resolver != nil {
		ips, err := policy.Resolver.LookupIPAddr(ctx, u.Hostname())
		if err != nil || len(ips) == 0 {
			return errors.New("A2A push URL DNS resolution failed")
		}
		for _, ip := range ips {
			if err := validateIP(ip.IP, policy.AllowLoopback); err != nil {
				return err
			}
		}
	}
	if cfg.AuthScheme != "" && cfg.AuthScheme != "bearer" && cfg.AuthScheme != "hmac-sha256" {
		return errors.New("unsupported A2A push authentication scheme")
	}
	if cfg.AuthScheme == "bearer" && strings.TrimSpace(cfg.CredentialRef) == "" || cfg.AuthScheme == "hmac-sha256" && strings.TrimSpace(cfg.SigningSecretRef) == "" {
		return ErrSecretRef
	}
	if looksLikeSecret(cfg.CredentialRef) || looksLikeSecret(cfg.SigningSecretRef) || looksLikeSecret(cfg.NotificationTokenRef) {
		return ErrSecretRef
	}
	return nil
}

type MemoryStore struct {
	mu    sync.RWMutex
	now   func() time.Time
	items map[string]Config
}

func NewMemoryStore(now func() time.Time) *MemoryStore {
	if now == nil {
		now = time.Now
	}
	return &MemoryStore{now: now, items: make(map[string]Config)}
}

func (s *MemoryStore) Create(ctx context.Context, cfg Config) error {
	if err := ValidateConfig(ctx, cfg, Policy{AllowedHosts: []string{"*"}, AllowLoopback: true}); err != nil {
		return err
	}
	key := itemKey(cfg.TenantID, cfg.TaskID, cfg.ID)
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.items[key]; exists {
		return ErrAlreadyExists
	}
	if cfg.CreatedAt.IsZero() {
		cfg.CreatedAt = s.now().UTC()
	}
	if cfg.UpdatedAt.IsZero() {
		cfg.UpdatedAt = cfg.CreatedAt
	}
	s.items[key] = cfg
	return nil
}

func (s *MemoryStore) Get(_ context.Context, tenant, task, id string) (Config, error) {
	s.mu.RLock()
	cfg, ok := s.items[itemKey(tenant, task, id)]
	s.mu.RUnlock()
	if !ok {
		return Config{}, ErrNotFound
	}
	return cfg, nil
}

func (s *MemoryStore) List(_ context.Context, tenant, task string) ([]Config, error) {
	s.mu.RLock()
	result := make([]Config, 0)
	for _, cfg := range s.items {
		if cfg.TenantID == tenant && cfg.TaskID == task {
			result = append(result, cfg)
		}
	}
	s.mu.RUnlock()
	sort.SliceStable(result, func(i, j int) bool { return result[i].CreatedAt.Before(result[j].CreatedAt) })
	return result, nil
}

func (s *MemoryStore) Delete(_ context.Context, tenant, task, id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := itemKey(tenant, task, id)
	if _, ok := s.items[key]; !ok {
		return ErrNotFound
	}
	delete(s.items, key)
	return nil
}

type DurableStore struct {
	store      objectstore.ObjectStore
	prefix     string
	now        func() time.Time
	IsNotFound func(error) bool
}

func NewDurableStore(store objectstore.ObjectStore, prefix string, now func() time.Time) *DurableStore {
	if now == nil {
		now = time.Now
	}
	return &DurableStore{store: store, prefix: strings.TrimSuffix(prefix, "/") + "/", now: now, IsNotFound: defaultIsNotFound}
}

func (s *DurableStore) Create(ctx context.Context, cfg Config) error {
	if s == nil || s.store == nil {
		return ErrDisabled
	}
	if err := ValidateConfig(ctx, cfg, Policy{AllowedHosts: []string{"*"}, AllowLoopback: true}); err != nil {
		return err
	}
	key := s.key(cfg.TenantID, cfg.TaskID, cfg.ID)
	if _, err := s.store.Get(ctx, key); err == nil {
		return ErrAlreadyExists
	} else if !s.isNotFound(err) {
		return fmt.Errorf("check existing A2A push configuration: %w", err)
	}
	if cfg.CreatedAt.IsZero() {
		cfg.CreatedAt = s.now().UTC()
	}
	if cfg.UpdatedAt.IsZero() {
		cfg.UpdatedAt = cfg.CreatedAt
	}
	body, err := json.Marshal(cfg)
	if err != nil {
		return err
	}
	return s.store.Put(ctx, key, body, map[string]string{"kind": "a2a_push_config", "tenant": hashPart(cfg.TenantID), "task": hashPart(cfg.TaskID)})
}

func (s *DurableStore) Get(ctx context.Context, tenant, task, id string) (Config, error) {
	if s == nil || s.store == nil {
		return Config{}, ErrDisabled
	}
	body, err := s.store.Get(ctx, s.key(tenant, task, id))
	if err != nil {
		return Config{}, ErrNotFound
	}
	var cfg Config
	if err := json.Unmarshal(body, &cfg); err != nil {
		return Config{}, fmt.Errorf("decode A2A push configuration: %w", err)
	}
	return cfg, nil
}

func (s *DurableStore) List(ctx context.Context, tenant, task string) ([]Config, error) {
	if s == nil || s.store == nil {
		return nil, ErrDisabled
	}
	items, err := s.store.ListByPrefix(ctx, s.prefix+hashPart(tenant)+"/"+hashPart(task)+"/")
	if err != nil {
		return nil, err
	}
	result := make([]Config, 0, len(items))
	for _, item := range items {
		body, getErr := s.store.Get(ctx, item.Key)
		if getErr != nil {
			return nil, getErr
		}
		var cfg Config
		if err := json.Unmarshal(body, &cfg); err != nil {
			return nil, fmt.Errorf("decode A2A push configuration: %w", err)
		}
		result = append(result, cfg)
	}
	sort.SliceStable(result, func(i, j int) bool { return result[i].CreatedAt.Before(result[j].CreatedAt) })
	return result, nil
}

func (s *DurableStore) Delete(ctx context.Context, tenant, task, id string) error {
	if s == nil || s.store == nil {
		return ErrDisabled
	}
	key := s.key(tenant, task, id)
	if _, err := s.store.Get(ctx, key); err != nil {
		if s.isNotFound(err) {
			return ErrNotFound
		}
		return fmt.Errorf("check A2A push configuration: %w", err)
	}
	return s.store.Delete(ctx, key)
}

// DeliveryRequest is the only transport-facing contract. A concrete sender
// must be injected by an operator-approved egress implementation; the state
// package itself cannot transmit task payloads.
type DeliveryRequest struct {
	Config  Config
	Payload []byte
}

type Delivery interface {
	Deliver(context.Context, DeliveryRequest) error
}

type DeadLetter struct {
	ID          string    `json:"id"`
	TenantID    string    `json:"tenantId"`
	TaskID      string    `json:"taskId"`
	ConfigID    string    `json:"configId"`
	URL         string    `json:"url"`
	PayloadHash string    `json:"payloadHash"`
	Attempts    int       `json:"attempts"`
	Error       string    `json:"error"`
	CreatedAt   time.Time `json:"createdAt"`
}

type DeadLetterStore interface {
	Put(context.Context, DeadLetter) error
}

func itemKey(tenant, task, id string) string {
	return tenant + "\x00" + task + "\x00" + id
}

func hashPart(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func (s *DurableStore) key(tenant, task, id string) string {
	return s.prefix + hashPart(tenant) + "/" + hashPart(task) + "/" + hashPart(id) + ".json"
}

func (s *DurableStore) isNotFound(err error) bool {
	if s != nil && s.IsNotFound != nil {
		return s.IsNotFound(err)
	}
	return defaultIsNotFound(err)
}

func defaultIsNotFound(err error) bool {
	if err == nil {
		return false
	}
	message := strings.ToLower(err.Error())
	return strings.Contains(message, "not found") || strings.Contains(message, "no such key") || strings.Contains(message, "nosuchkey")
}

func hostAllowed(host string, allowlist []string) bool {
	for _, allowed := range allowlist {
		allowed = strings.ToLower(strings.TrimSpace(allowed))
		if allowed == "*" || allowed == strings.ToLower(host) {
			return true
		}
	}
	return false
}

func validateIP(ip net.IP, allowLoopback bool) error {
	if ip == nil {
		return errors.New("A2A push URL resolved to an invalid IP")
	}
	if allowLoopback && ip.IsLoopback() {
		return nil
	}
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsUnspecified() {
		return errors.New("A2A push URL resolved to a private or local IP")
	}
	return nil
}

func looksLikeSecret(value string) bool {
	value = strings.TrimSpace(value)
	return strings.HasPrefix(value, "Bearer ") || strings.HasPrefix(value, "eyJ") || len(value) > 256
}
