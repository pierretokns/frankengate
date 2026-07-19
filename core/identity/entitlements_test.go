package identity

import (
	"errors"
	"testing"
)

func TestEvaluateMergesGroupsDeterministically(t *testing.T) {
	p := Policy{RequireMatch: true, Rules: []GroupRule{
		{Group: "finance", Models: []string{"claude", "gpt"}, Providers: []string{"bedrock"}, ToolGroups: []string{"sql"}},
		{Group: "research", Models: []string{"gpt", "nova"}, Providers: []string{"bedrock"}, ToolGroups: []string{"web"}},
	}}
	e, err := p.Evaluate([]string{"unknown", "research", "finance", "finance"})
	if err != nil {
		t.Fatal(err)
	}
	if got, want := e.MatchedGroups, []string{"finance", "research"}; !equal(got, want) {
		t.Fatalf("groups=%v want %v", got, want)
	}
	if got, want := e.Models, []string{"claude", "gpt", "nova"}; !equal(got, want) {
		t.Fatalf("models=%v want %v", got, want)
	}
}

func TestEvaluateMissingGroupsFailsClosed(t *testing.T) {
	p := Policy{RequireMatch: true, Rules: []GroupRule{{Group: "finance", Models: []string{"gpt"}}}}
	_, err := p.Evaluate(nil)
	if !errors.Is(err, ErrNoEntitlement) {
		t.Fatalf("err=%v", err)
	}
}

func TestPolicyRejectsDuplicateAndEmptyRules(t *testing.T) {
	for _, p := range []Policy{
		{Rules: []GroupRule{{Group: "finance"}, {Group: "finance"}}},
		{Rules: []GroupRule{{Group: " "}}},
		{Rules: []GroupRule{{Group: "finance", Models: []string{""}}}},
	} {
		if err := p.Validate(); !errors.Is(err, ErrInvalidPolicy) {
			t.Fatalf("err=%v", err)
		}
	}
}

func TestEntitlementsAuthorizeFailsClosedAndSupportsScopedGrants(t *testing.T) {
	e := Entitlements{Models: []string{"claude-*"}, Providers: []string{"bedrock"}, ToolGroups: []string{"sql-*"}}
	if err := e.Authorize("bedrock", "claude-sonnet", []string{"sql-query"}); err != nil {
		t.Fatal(err)
	}
	for _, denied := range []struct{ provider, model, tool string }{
		{"openai", "claude-sonnet", "sql-query"},
		{"bedrock", "gpt-4", "sql-query"},
		{"bedrock", "claude-sonnet", "web-fetch"},
	} {
		if err := e.Authorize(denied.provider, denied.model, []string{denied.tool}); err == nil {
			t.Fatalf("expected entitlement denial for %+v", denied)
		}
	}
}

func equal(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
