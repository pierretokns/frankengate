package mcp

import (
	"strings"
	"testing"
)

func TestBoundedMCPTraceValue(t *testing.T) {
	if got := boundedMCPTraceValue("  safe  "); got != "safe" {
		t.Fatalf("trimmed value = %q, want safe", got)
	}
	got := boundedMCPTraceValue(strings.Repeat("x", maxMCPTraceValueRunes+100))
	if n := len([]rune(got)); n > maxMCPTraceValueRunes+len([]rune("…[truncated]")) {
		t.Fatalf("bounded value has %d runes", n)
	}
	if !strings.HasSuffix(got, "…[truncated]") {
		t.Fatal("bounded value does not advertise truncation")
	}
}
