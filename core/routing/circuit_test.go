package routing

import (
	"testing"
	"time"
)

func TestProviderCircuitOpensAndAllowsSingleProbe(t *testing.T) {
	now := time.Unix(100, 0)
	c := NewProviderCircuit(ProviderCircuitConfig{MaxProviders: 2, FailureThreshold: 2, Cooldown: time.Second})
	c.now = func() time.Time { return now }
	if !c.Allow("bedrock").Allowed {
		t.Fatal("healthy provider was rejected")
	}
	c.RecordFailure("bedrock")
	c.RecordFailure("bedrock")
	if d := c.Allow("bedrock"); d.Allowed || d.Reason != "cooldown" {
		t.Fatalf("open decision = %#v", d)
	}
	now = now.Add(2 * time.Second)
	if d := c.Allow("bedrock"); !d.Allowed || d.Reason != "probe" {
		t.Fatalf("probe decision = %#v", d)
	}
	if d := c.Allow("bedrock"); d.Allowed || d.Reason != "probe_in_flight" {
		t.Fatalf("concurrent probe decision = %#v", d)
	}
	c.RecordSuccess("bedrock")
	if d := c.Allow("bedrock"); !d.Allowed || d.State != circuitClosed {
		t.Fatalf("recovered decision = %#v", d)
	}
}

func TestProviderCircuitBoundsProviderCardinality(t *testing.T) {
	c := NewProviderCircuit(ProviderCircuitConfig{MaxProviders: 1})
	if !c.Allow("one").Allowed {
		t.Fatal("first provider rejected")
	}
	if d := c.Allow("two"); d.Allowed || d.Reason != "provider_limit" {
		t.Fatalf("bounded decision = %#v", d)
	}
	if d := c.Allow(""); d.Allowed || d.Reason != "empty_provider" {
		t.Fatalf("empty decision = %#v", d)
	}
}
