// Package protocol contains the version-neutral MCP compatibility contract.
//
// MCP revisions are grouped into behavioral eras because a gateway must
// translate wire behavior, not just compare date strings. The legacy era
// covers the initialize/session family used by existing Bifrost clients. The
// modern era starts with the stateless 2026-07-28 revision.
package protocol

import (
	"fmt"
	"sort"
	"strings"
)

// Protocol revisions currently relevant to FrankenGate's compatibility
// matrix. Keep these constants independent of any particular MCP SDK so the
// gateway can negotiate on each side of a proxy boundary.
const (
	Version2024_11_05 = "2024-11-05"
	Version2025_03_26 = "2025-03-26"
	Version2025_06_18 = "2025-06-18"
	Version2025_11_25 = "2025-11-25"
	Version2026_07_28 = "2026-07-28"
)

// Era identifies a family of wire behaviors. It intentionally is not a
// protocol version: several legacy revisions share the same lifecycle.
type Era string

const (
	Legacy Era = "legacy"
	Modern Era = "modern"
)

// Mode controls how a peer is selected from the mutually supported versions.
type Mode string

const (
	ModeAuto   Mode = "auto"
	ModeLegacy Mode = "legacy"
	ModePin    Mode = "pin"
)

// NegotiationPolicy is applied to one protocol leg. A gateway must construct
// one policy for the downstream leg and another for every upstream target.
type NegotiationPolicy struct {
	SupportedVersions   []string
	Mode                Mode
	PinnedVersion       string
	AllowLegacyFallback bool
}

// Result records the selected wire contract. It is safe to put this small
// value in request-scoped context or tracing metadata.
type Result struct {
	Version string
	Era     Era
}

// FeatureMatrix describes behavior that changes between MCP eras. Callers
// must gate methods and transport behavior through this matrix rather than
// checking date strings throughout the codebase.
type FeatureMatrix struct {
	Initialize              bool
	SessionID               bool
	ServerDiscover          bool
	PerRequestMetadata      bool
	StandaloneGET           bool
	ResumableStreams        bool
	ServerInitiatedRequests bool
	MultiRoundTripRequests  bool
	SubscriptionsListen     bool
	LegacyLogging           bool
	LegacyRoots             bool
	LegacySampling          bool
}

// FeaturesFor returns the wire behavior for a known MCP revision.
func FeaturesFor(version string) (FeatureMatrix, error) {
	switch strings.TrimSpace(version) {
	case Version2024_11_05, Version2025_03_26, Version2025_06_18, Version2025_11_25:
		return FeatureMatrix{
			Initialize:              true,
			SessionID:               true,
			StandaloneGET:           true,
			ResumableStreams:        true,
			ServerInitiatedRequests: true,
			LegacyLogging:           true,
			LegacyRoots:             true,
			LegacySampling:          true,
		}, nil
	case Version2026_07_28:
		return FeatureMatrix{
			ServerDiscover:         true,
			PerRequestMetadata:     true,
			MultiRoundTripRequests: true,
			SubscriptionsListen:    true,
		}, nil
	default:
		return FeatureMatrix{}, fmt.Errorf("unsupported MCP protocol version %q", version)
	}
}

// EraFor returns the behavioral era for a known revision.
func EraFor(version string) (Era, error) {
	features, err := FeaturesFor(version)
	if err != nil {
		return "", err
	}
	if features.ServerDiscover {
		return Modern, nil
	}
	return Legacy, nil
}

// Negotiate selects the highest mutually supported version. In auto mode the
// modern revision is preferred, while ModeLegacy intentionally prevents a
// modern-only feature from being silently introduced into an old connection.
// ModePin never falls back.
func Negotiate(policy NegotiationPolicy, peerVersions []string) (Result, error) {
	mode := policy.Mode
	if mode == "" {
		mode = ModeAuto
	}

	local := normalizeVersions(policy.SupportedVersions)
	peer := normalizeVersions(peerVersions)
	if len(local) == 0 {
		return Result{}, fmt.Errorf("MCP negotiation has no locally supported versions")
	}
	if len(peer) == 0 {
		return Result{}, fmt.Errorf("MCP peer advertised no supported versions")
	}

	if mode == ModePin {
		pinned := strings.TrimSpace(policy.PinnedVersion)
		if pinned == "" {
			return Result{}, fmt.Errorf("MCP pin mode requires a pinned version")
		}
		if !contains(local, pinned) || !contains(peer, pinned) {
			return Result{}, fmt.Errorf("MCP pinned version %q is not mutually supported", pinned)
		}
		return resultFor(pinned)
	}

	if mode == ModeLegacy {
		local = legacyOnly(local)
		peer = legacyOnly(peer)
	}

	common := make([]string, 0, len(local))
	for _, version := range local {
		if contains(peer, version) {
			common = append(common, version)
		}
	}
	if len(common) == 0 {
		if mode == ModeAuto && policy.AllowLegacyFallback {
			return Result{}, fmt.Errorf("MCP negotiation found no common version; legacy fallback requires a new probe against the peer")
		}
		return Result{}, fmt.Errorf("MCP negotiation found no mutually supported version")
	}

	sort.SliceStable(common, func(i, j int) bool {
		return versionRank(common[i]) > versionRank(common[j])
	})
	return resultFor(common[0])
}

func resultFor(version string) (Result, error) {
	era, err := EraFor(version)
	if err != nil {
		return Result{}, err
	}
	return Result{Version: version, Era: era}, nil
}

func normalizeVersions(versions []string) []string {
	seen := make(map[string]struct{}, len(versions))
	result := make([]string, 0, len(versions))
	for _, version := range versions {
		version = strings.TrimSpace(version)
		if version == "" {
			continue
		}
		if _, ok := seen[version]; ok {
			continue
		}
		seen[version] = struct{}{}
		result = append(result, version)
	}
	return result
}

func legacyOnly(versions []string) []string {
	result := make([]string, 0, len(versions))
	for _, version := range versions {
		era, err := EraFor(version)
		if err == nil && era == Legacy {
			result = append(result, version)
		}
	}
	return result
}

func contains(versions []string, target string) bool {
	for _, version := range versions {
		if version == target {
			return true
		}
	}
	return false
}

func versionRank(version string) int {
	switch version {
	case Version2026_07_28:
		return 5
	case Version2025_11_25:
		return 4
	case Version2025_06_18:
		return 3
	case Version2025_03_26:
		return 2
	case Version2024_11_05:
		return 1
	default:
		return 0
	}
}
