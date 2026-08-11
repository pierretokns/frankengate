package a2apush

import (
	"context"
	"errors"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

func TestValidateConfigRejectsUnsafeDestinationsAndInlineSecrets(t *testing.T) {
	base := Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}
	policy := Policy{
		AllowedHosts: []string{"notify.example.test"},
		Resolver: ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
			return []net.IPAddr{{IP: net.ParseIP("203.0.113.10")}}, nil
		}),
	}
	if err := ValidateConfig(context.Background(), base, policy); err != nil {
		t.Fatalf("valid config rejected: %v", err)
	}

	unsafe := base
	unsafe.URL = "http://notify.example.test/a2a"
	if err := ValidateConfig(context.Background(), unsafe, policy); err == nil {
		t.Fatal("expected non-HTTPS URL to be rejected")
	}

	unsafe = base
	unsafe.URL = "https://notify.example.test/a2a#fragment"
	if err := ValidateConfig(context.Background(), unsafe, policy); err == nil {
		t.Fatal("expected URL fragment to be rejected")
	}

	unsafe = base
	unsafe.URL = "https://notify.example.test/a2a"
	unsafe.AuthScheme = "bearer"
	unsafe.CredentialRef = "Bearer inline-token"
	if !errors.Is(ValidateConfig(context.Background(), unsafe, policy), ErrSecretRef) {
		t.Fatal("expected inline bearer secret to be rejected")
	}

	unsafe = base
	unsafe.AuthScheme = "hmac-sha256"
	if !errors.Is(ValidateConfig(context.Background(), unsafe, policy), ErrSecretRef) {
		t.Fatal("expected missing signing secret reference to be rejected")
	}
}

func TestValidateConfigBlocksPrivateDNSResolution(t *testing.T) {
	cfg := Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}
	policy := Policy{
		AllowedHosts: []string{"notify.example.test"},
		Resolver: ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
			return []net.IPAddr{{IP: net.ParseIP("10.0.0.4")}}, nil
		}),
	}
	if err := ValidateConfig(context.Background(), cfg, policy); err == nil || !strings.Contains(err.Error(), "private") {
		t.Fatalf("expected private DNS result to be blocked, got %v", err)
	}
}

func TestMemoryStoreIsTenantScopedAndSecretReferenceOnly(t *testing.T) {
	now := time.Date(2026, time.August, 11, 12, 0, 0, 0, time.UTC)
	store := NewMemoryStore(func() time.Time { return now })
	cfg := Config{
		ID: "push-1", TaskID: "task-1", TenantID: "tenant-1",
		URL: "https://notify.example.test/a2a", AuthScheme: "bearer", CredentialRef: "vault://tenant-1/a2a",
	}
	if err := store.Create(context.Background(), cfg); err != nil {
		t.Fatalf("create: %v", err)
	}
	if _, err := store.Get(context.Background(), "tenant-2", cfg.TaskID, cfg.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-tenant lookup returned %v", err)
	}
	got, err := store.Get(context.Background(), cfg.TenantID, cfg.TaskID, cfg.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.CredentialRef != cfg.CredentialRef || !got.CreatedAt.Equal(now) {
		t.Fatalf("stored config changed: %#v", got)
	}
}

func TestDurableStoreUsesHashedTenantTaskKeysAndPropagatesBackendFailure(t *testing.T) {
	backend := objectstore.NewInMemoryObjectStore()
	store := NewDurableStore(backend, "a2a/push", func() time.Time { return time.Unix(10, 0) })
	cfg := Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}
	if err := store.Create(context.Background(), cfg); err != nil {
		t.Fatalf("create: %v", err)
	}
	for _, key := range backend.Keys() {
		if strings.Contains(key, cfg.TenantID) || strings.Contains(key, cfg.TaskID) || strings.Contains(key, cfg.ID) {
			t.Fatalf("object key leaked tenant/task/config identity: %q", key)
		}
	}
	if err := store.Create(context.Background(), cfg); !errors.Is(err, ErrAlreadyExists) {
		t.Fatalf("duplicate create returned %v", err)
	}
	backend.GetErr = errors.New("objectstore: unavailable")
	if err := store.Create(context.Background(), Config{ID: "push-2", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}); err == nil || !strings.Contains(err.Error(), "check existing") {
		t.Fatalf("backend failure was not propagated: %v", err)
	}
}
