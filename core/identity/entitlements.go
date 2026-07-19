// Package identity contains provider-neutral identity decisions.  The Okta
// adapter should only authenticate and normalize claims; authorization is
// deliberately deterministic and lives here so every IdP follows the same
// fail-closed rules.
package identity

import (
	"errors"
	"fmt"
	"sort"
	"strings"
)

var (
	ErrNoEntitlement     = errors.New("identity: no matching entitlement")
	ErrInvalidPolicy     = errors.New("identity: invalid entitlement policy")
	ErrModelDenied       = errors.New("identity: model is not entitled")
	ErrProviderDenied    = errors.New("identity: provider is not entitled")
	ErrToolDenied        = errors.New("identity: tool is not entitled")
	ErrMarketplaceDenied = errors.New("identity: marketplace capability is not entitled")
)

// MarketplaceAction identifies the separately governed lifecycle stages for
// skills/tools published through the enterprise marketplace. Discovery is
// intentionally distinct from installation and invocation: seeing metadata
// never grants the ability to install or execute it.
type MarketplaceAction string

const (
	MarketplaceDiscover MarketplaceAction = "discover"
	MarketplaceInstall  MarketplaceAction = "install"
	MarketplaceInvoke   MarketplaceAction = "invoke"
)

// GroupRule maps one IdP group to the effective model/provider/tool grants.
// Empty grant lists mean no access (never unrestricted access).
type GroupRule struct {
	Group               string
	Models              []string
	Providers           []string
	ToolGroups          []string
	MarketplaceDiscover []string
	MarketplaceInstall  []string
	MarketplaceInvoke   []string
}

// Entitlements is the normalized, immutable decision returned to governance.
// Groups and grants are sorted and deduplicated for stable cache keys and
// audit records.  Matched is intentionally retained to make no-match states
// observable without treating an empty grant as unrestricted.
type Entitlements struct {
	MatchedGroups       []string
	Models              []string
	Providers           []string
	ToolGroups          []string
	MarketplaceDiscover []string
	MarketplaceInstall  []string
	MarketplaceInvoke   []string
}

// Decision is the sanitized authorization outcome emitted to audit/telemetry.
// It intentionally contains only stable categories; never put IdP groups or
// raw claims in this value.
type Decision struct {
	Allowed    bool
	Capability string
	Reason     string
}

// AllowsModel, AllowsProvider, and AllowsTool are deliberately fail-closed:
// an entitlement snapshot is authoritative only when it explicitly grants the
// requested capability. A missing/empty grant never means unrestricted access.
func (e Entitlements) AllowsModel(model string) bool { return matchesGrant(e.Models, model) }
func (e Entitlements) AllowsProvider(provider string) bool {
	return matchesGrant(e.Providers, provider)
}
func (e Entitlements) AllowsTool(tool string) bool { return matchesGrant(e.ToolGroups, tool) }

// AllowsMarketplace is fail-closed for both unknown actions and missing
// grants. Callers must check the requested lifecycle action explicitly; an
// install grant does not imply invoke (or even discover) access.
func (e Entitlements) AllowsMarketplace(action MarketplaceAction, resource string) bool {
	var grants []string
	switch action {
	case MarketplaceDiscover:
		grants = e.MarketplaceDiscover
	case MarketplaceInstall:
		grants = e.MarketplaceInstall
	case MarketplaceInvoke:
		grants = e.MarketplaceInvoke
	default:
		return false
	}
	return matchesGrant(grants, resource)
}

func (e Entitlements) AuthorizeMarketplace(action MarketplaceAction, resource string) error {
	if !e.AllowsMarketplace(action, resource) {
		return ErrMarketplaceDenied
	}
	return nil
}

// Authorize checks the provider/model and every tool in one immutable snapshot.
// The returned errors are stable categories suitable for transport responses.
func (e Entitlements) Authorize(provider, model string, tools []string) error {
	if !e.AllowsProvider(provider) {
		return ErrProviderDenied
	}
	if !e.AllowsModel(model) {
		return ErrModelDenied
	}
	for _, tool := range tools {
		if !e.AllowsTool(tool) {
			return ErrToolDenied
		}
	}
	return nil
}

func matchesGrant(grants []string, value string) bool {
	value = strings.TrimSpace(value)
	if value == "" {
		return false
	}
	for _, raw := range grants {
		grant := strings.TrimSpace(raw)
		if grant == "*" || strings.EqualFold(grant, value) {
			return true
		}
		if strings.HasSuffix(grant, "*") && strings.HasPrefix(strings.ToLower(value), strings.ToLower(strings.TrimSuffix(grant, "*"))) {
			return true
		}
	}
	return false
}

// Policy evaluates IdP groups. If RequireMatch is true, a token with no
// recognized group is rejected. This should be enabled for enterprise Okta
// deployments so a missing/omitted groups claim cannot broaden access.
type Policy struct {
	Rules        []GroupRule
	RequireMatch bool
}

func (p Policy) Validate() error {
	seen := make(map[string]struct{}, len(p.Rules))
	for _, r := range p.Rules {
		g := strings.TrimSpace(r.Group)
		if g == "" {
			return fmt.Errorf("%w: group is required", ErrInvalidPolicy)
		}
		if _, ok := seen[g]; ok {
			return fmt.Errorf("%w: duplicate group %q", ErrInvalidPolicy, g)
		}
		seen[g] = struct{}{}
		grants := append(append(append(append(append(append([]string{}, r.Models...), r.Providers...), r.ToolGroups...), r.MarketplaceDiscover...), r.MarketplaceInstall...), r.MarketplaceInvoke...)
		for _, grant := range grants {
			if strings.TrimSpace(grant) == "" {
				return fmt.Errorf("%w: empty grant for group %q", ErrInvalidPolicy, g)
			}
		}
	}
	return nil
}

// Evaluate returns the intersection of configured policy and token groups.
// It never interprets an absent group as wildcard access and does not trust
// display names or claims other than the normalized group values supplied by
// the verified JWT/SCIM adapter.
func (p Policy) Evaluate(groups []string) (Entitlements, error) {
	if err := p.Validate(); err != nil {
		return Entitlements{}, err
	}
	rules := make(map[string]GroupRule, len(p.Rules))
	for _, rule := range p.Rules {
		rules[strings.TrimSpace(rule.Group)] = rule
	}
	matched := make(map[string]struct{})
	out := Entitlements{}
	for _, raw := range groups {
		group := strings.TrimSpace(raw)
		if group == "" {
			continue
		}
		rule, ok := rules[group]
		if !ok {
			continue
		}
		if _, ok := matched[group]; ok {
			continue
		}
		matched[group] = struct{}{}
		out.MatchedGroups = append(out.MatchedGroups, group)
		out.Models = append(out.Models, rule.Models...)
		out.Providers = append(out.Providers, rule.Providers...)
		out.ToolGroups = append(out.ToolGroups, rule.ToolGroups...)
		out.MarketplaceDiscover = append(out.MarketplaceDiscover, rule.MarketplaceDiscover...)
		out.MarketplaceInstall = append(out.MarketplaceInstall, rule.MarketplaceInstall...)
		out.MarketplaceInvoke = append(out.MarketplaceInvoke, rule.MarketplaceInvoke...)
	}
	if p.RequireMatch && len(out.MatchedGroups) == 0 {
		return Entitlements{}, ErrNoEntitlement
	}
	canonicalize(&out)
	return out, nil
}

func canonicalize(e *Entitlements) {
	e.MatchedGroups = uniqueSorted(e.MatchedGroups)
	e.Models = uniqueSorted(e.Models)
	e.Providers = uniqueSorted(e.Providers)
	e.ToolGroups = uniqueSorted(e.ToolGroups)
	e.MarketplaceDiscover = uniqueSorted(e.MarketplaceDiscover)
	e.MarketplaceInstall = uniqueSorted(e.MarketplaceInstall)
	e.MarketplaceInvoke = uniqueSorted(e.MarketplaceInvoke)
}

func uniqueSorted(values []string) []string {
	seen := make(map[string]struct{}, len(values))
	out := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}
		if _, ok := seen[value]; !ok {
			seen[value] = struct{}{}
			out = append(out, value)
		}
	}
	sort.Strings(out)
	return out
}
