package mcp

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/mcpownership"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestMCPOwnershipConfigurationRequiresFenceIdentity(t *testing.T) {
	m := NewMCPManager(context.Background(), schemas.MCPConfig{}, nil, nil, nil)
	if err := m.SetMCPOwnership(mcpownership.NewRegistry(), "", time.Second); err == nil {
		t.Fatal("expected empty owner pod to be rejected")
	}
	if err := m.SetMCPOwnership(mcpownership.NewRegistry(), "pod-a", 0); err == nil {
		t.Fatal("expected non-positive lease to be rejected")
	}
	if err := m.SetMCPOwnership(mcpownership.NewRegistry(), "pod-a", time.Second); err != nil {
		t.Fatalf("configure ownership: %v", err)
	}
	if m.ownerPod != "pod-a" || m.ownershipTTL != time.Second {
		t.Fatalf("ownership config = pod=%q ttl=%s", m.ownerPod, m.ownershipTTL)
	}
}

func TestMCPOwnershipKeyUsesTrustedPrincipalAndRequestID(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "acme", Issuer: "okta", Subject: "u-7"})
	ctx.SetValue(schemas.BifrostContextKeyRequestID, "req-9")
	name := "search"
	req := &schemas.BifrostMCPRequest{ChatAssistantMessageToolCall: &schemas.ChatAssistantMessageToolCall{Function: schemas.ChatAssistantMessageToolCallFunction{Name: &name}}}
	state := &schemas.MCPClientState{ExecutionConfig: &schemas.MCPClientConfig{ID: "client-1", Name: "docs"}}
	key, op := mcpOwnershipKey(ctx, state, req)
	if key != (mcpownership.ConnectionKey{ClientID: "client-1", Principal: "acme:okta:u-7", SessionKey: "req-9"}) {
		t.Fatalf("key = %+v", key)
	}
	if op != "req-9:search" {
		t.Fatalf("operation = %q", op)
	}
}

func TestMCPOwnershipStaleFenceFailsClosedAtRegistryBoundary(t *testing.T) {
	reg := mcpownership.NewRegistry()
	now := time.Unix(1, 0)
	key := mcpownership.ConnectionKey{ClientID: "client", Principal: "acme:u", SessionKey: "session"}
	a, err := reg.Claim(now, key, "pod-a", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := reg.Claim(now.Add(2*time.Second), key, "pod-b", time.Second); err != nil {
		t.Fatal(err)
	}
	if _, err := reg.StartCall(now.Add(2*time.Second), key, "pod-a", a.Fence, "op"); !errors.Is(err, mcpownership.ErrStaleFence) {
		t.Fatalf("stale start = %v, want ErrStaleFence", err)
	}
}
