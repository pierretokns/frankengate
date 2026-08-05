package protocol

import "testing"

func TestEraForGroupsLegacyRevisions(t *testing.T) {
	for _, version := range []string{
		Version2024_11_05,
		Version2025_03_26,
		Version2025_06_18,
		Version2025_11_25,
	} {
		era, err := EraFor(version)
		if err != nil {
			t.Fatalf("EraFor(%q): %v", version, err)
		}
		if era != Legacy {
			t.Fatalf("EraFor(%q) = %q, want %q", version, era, Legacy)
		}
	}
}

func TestModernFeatureMatrix(t *testing.T) {
	features, err := FeaturesFor(Version2026_07_28)
	if err != nil {
		t.Fatal(err)
	}
	if !features.ServerDiscover || !features.PerRequestMetadata || !features.MultiRoundTripRequests || !features.SubscriptionsListen {
		t.Fatalf("modern feature matrix is incomplete: %+v", features)
	}
	if features.Initialize || features.SessionID || features.StandaloneGET || features.ResumableStreams {
		t.Fatalf("modern feature matrix incorrectly enables legacy lifecycle: %+v", features)
	}
}

func TestNegotiatePrefersModernVersion(t *testing.T) {
	result, err := Negotiate(NegotiationPolicy{
		SupportedVersions: []string{Version2025_03_26, Version2026_07_28},
	}, []string{Version2026_07_28, Version2025_03_26})
	if err != nil {
		t.Fatal(err)
	}
	if result.Version != Version2026_07_28 || result.Era != Modern {
		t.Fatalf("got %+v, want modern 2026-07-28", result)
	}
}

func TestNegotiateFallsBackToLegacyWhenModernIsUnavailable(t *testing.T) {
	result, err := Negotiate(NegotiationPolicy{
		SupportedVersions:   []string{Version2025_03_26, Version2026_07_28},
		AllowLegacyFallback: true,
	}, []string{Version2025_03_26})
	if err != nil {
		t.Fatal(err)
	}
	if result.Version != Version2025_03_26 || result.Era != Legacy {
		t.Fatalf("got %+v, want legacy 2025-03-26", result)
	}
}

func TestNegotiateLegacyModeRejectsModernOnlyPeer(t *testing.T) {
	_, err := Negotiate(NegotiationPolicy{
		SupportedVersions: []string{Version2025_11_25, Version2026_07_28},
		Mode:              ModeLegacy,
	}, []string{Version2026_07_28})
	if err == nil {
		t.Fatal("legacy mode unexpectedly negotiated a modern-only peer")
	}
}

func TestNegotiatePinNeverFallsBack(t *testing.T) {
	_, err := Negotiate(NegotiationPolicy{
		SupportedVersions:   []string{Version2025_03_26, Version2026_07_28},
		Mode:                ModePin,
		PinnedVersion:       Version2026_07_28,
		AllowLegacyFallback: true,
	}, []string{Version2025_03_26})
	if err == nil {
		t.Fatal("pin mode unexpectedly fell back to legacy")
	}
}

func TestNegotiateDeduplicatesAndTrimsVersions(t *testing.T) {
	result, err := Negotiate(NegotiationPolicy{
		SupportedVersions: []string{" ", Version2025_03_26, Version2025_03_26},
	}, []string{Version2025_03_26, " "})
	if err != nil {
		t.Fatal(err)
	}
	if result.Version != Version2025_03_26 {
		t.Fatalf("got %q, want %q", result.Version, Version2025_03_26)
	}
}

func TestNegotiateRejectsInvalidInputs(t *testing.T) {
	tests := []struct {
		name   string
		policy NegotiationPolicy
		peer   []string
	}{
		{name: "no local versions", peer: []string{Version2025_03_26}},
		{name: "no peer versions", policy: NegotiationPolicy{SupportedVersions: []string{Version2025_03_26}}},
		{name: "pin without version", policy: NegotiationPolicy{SupportedVersions: []string{Version2025_03_26}, Mode: ModePin}, peer: []string{Version2025_03_26}},
		{name: "unknown peer", policy: NegotiationPolicy{SupportedVersions: []string{"2099-01-01"}}, peer: []string{"2099-01-01"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if _, err := Negotiate(tt.policy, tt.peer); err == nil {
				t.Fatal("Negotiate unexpectedly succeeded")
			}
		})
	}
}
