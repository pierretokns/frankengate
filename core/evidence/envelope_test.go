package evidence_test

import (
	"encoding/json"
	"fmt"
	"math"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/evidence"
)

func TestValidateGatewayAttemptEnvelopeRequiresPrivacyAndAuthority(t *testing.T) {
	env := validGatewayAttemptEnvelope()

	if err := env.Validate(); err != nil {
		t.Fatalf("valid envelope failed validation: %v", err)
	}

	t.Run("missing privacy receipt fails closed", func(t *testing.T) {
		env := validGatewayAttemptEnvelope()
		env.Privacy = evidence.PrivacyReceipt{}

		if err := env.Validate(); err == nil {
			t.Fatal("expected missing privacy receipt to fail validation")
		}
	})

	t.Run("missing authority revision fails closed", func(t *testing.T) {
		env := validGatewayAttemptEnvelope()
		env.Revisions.Authority = ""

		if err := env.Validate(); err == nil {
			t.Fatal("expected missing authority revision to fail validation")
		}
	})
}

func TestValidateFailsClosedForMissingControlPlaneFields(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*evidence.AgentEvidenceEnvelope)
	}{
		{name: "tenant id", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.TenantID = "" }},
		{name: "subject id", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.Subject.ID = "" }},
		{name: "purpose", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.Purpose = "" }},
		{name: "residency", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.Residency = "" }},
		{name: "acl readers", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.ACL.Readers = nil }},
		{name: "privacy policy revision", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Privacy.PolicyRevision = "" }},
		{name: "privacy transform revision", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Privacy.TransformRevision = "" }},
		{name: "sampling decision", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Sampling.Decision = "" }},
		{name: "missingness status", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Missingness.Status = "" }},
		{name: "deletion lineage", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Deletion.LineageID = "" }},
		{name: "policy revision", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Revisions.Policy = "" }},
		{name: "privacy revision", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Revisions.Privacy = "" }},
		{name: "immutable source revision", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Revisions.Gateway = ""
			env.Revisions.Route = ""
		}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := validGatewayAttemptEnvelope()
			tt.mutate(&env)

			if err := env.Validate(); err == nil {
				t.Fatalf("expected missing %s to fail validation", tt.name)
			}
		})
	}
}

func TestBehavioralFrictionSupportsDerivedSignalsAndStageLatency(t *testing.T) {
	env := validGatewayAttemptEnvelope()
	env.Observation = evidence.Observation{
		Type: evidence.ObservationBehavioralFriction,
		BehavioralFriction: &evidence.BehavioralFrictionEvidence{
			WindowID: "window_01",
			Signals: []evidence.BehavioralSignal{
				{Type: evidence.BehavioralCorrection, Count: 1},
				{Type: evidence.BehavioralCitationMiss, Count: 1},
				{Type: evidence.BehavioralStageLatency, Count: 1, LatencyMs: 250},
			},
		},
	}
	if err := env.Validate(); err != nil {
		t.Fatalf("derived behavioral signals should validate: %v", err)
	}
}

func TestBehavioralStageLatencyRequiresBoundedLatency(t *testing.T) {
	env := validGatewayAttemptEnvelope()
	env.Observation = evidence.Observation{
		Type: evidence.ObservationBehavioralFriction,
		BehavioralFriction: &evidence.BehavioralFrictionEvidence{
			WindowID: "window_01",
			Signals:  []evidence.BehavioralSignal{{Type: evidence.BehavioralStageLatency, Count: 1}},
		},
	}
	if err := env.Validate(); err == nil {
		t.Fatal("stage latency without latency_ms should be rejected")
	}
}

func TestValidateRejectsUnknownEnumValues(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*evidence.AgentEvidenceEnvelope)
	}{
		{name: "producer kind", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Producer.Kind = "browser-plugin" }},
		{name: "purpose", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.Purpose = "training" }},
		{name: "subject kind", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.Subject.Kind = "person" }},
		{name: "visibility", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.ACL.Visibility = "global" }},
		{name: "privacy disposition", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Privacy.Disposition = "raw" }},
		{name: "sampling decision", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Sampling.Decision = "maybe" }},
		{name: "missingness status", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Missingness.Status = "unknownish" }},
		{name: "deletion state", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Deletion.DeletionState = "gone" }},
		{name: "observation type", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Observation.Type = "raw_transcript" }},
		{name: "attempt outcome", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Observation.GatewayAttempt.Outcome = "partly_ok" }},
		{name: "terminal outcome", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationTerminalOutcome,
				TerminalOutcome: &evidence.TerminalOutcomeEvidence{
					SessionID:         "session_01",
					TaskID:            "task_01",
					Outcome:           "kind-of",
					Source:            evidence.TerminalOutcomeCollector,
					CompletedAt:       time.Unix(1700000100, 0).UTC(),
					GatewayRequestIDs: []string{"req_01"},
				},
			}
		}},
		{name: "terminal outcome source", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationTerminalOutcome,
				TerminalOutcome: &evidence.TerminalOutcomeEvidence{
					SessionID:         "session_01",
					TaskID:            "task_01",
					Outcome:           evidence.TerminalOutcomeSucceeded,
					Source:            "clipboard",
					CompletedAt:       time.Unix(1700000100, 0).UTC(),
					GatewayRequestIDs: []string{"req_01"},
				},
			}
		}},
		{name: "test status", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationDeterministicTest,
				DeterministicTest: &evidence.DeterministicTestEvidence{
					RunID:          "run_01",
					Suite:          "go-test",
					Case:           "TestFoo",
					Status:         "flaky",
					ToolRevision:   "go@1.26.4",
					ArtifactDigest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
				},
			}
		}},
		{name: "user report type", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationUserReport,
				UserReport: &evidence.UserReportEvidence{
					ReportID:   "report_01",
					ReportType: "freeform",
					ReasonCode: "wrong-file",
				},
			}
		}},
		{name: "behavioral signal type", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationBehavioralFriction,
				BehavioralFriction: &evidence.BehavioralFrictionEvidence{
					WindowID: "window_01",
					Signals:  []evidence.BehavioralSignal{{Type: "typed-secret", Count: 1}},
				},
			}
		}},
		{name: "perceived scale", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationPerceivedFriction,
				PerceivedFriction: &evidence.PerceivedFrictionEvidence{
					InstrumentID: "survey_01",
					Scale:        "mood",
					Score:        4,
					MaxScore:     5,
				},
			}
		}},
		{name: "judge outcome", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationJudgeEvidence,
				JudgeEvidence: &evidence.JudgeEvidence{
					JudgeID:        "judge_01",
					RubricRevision: "rubric@7",
					Outcome:        "maybe",
				},
			}
		}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := validGatewayAttemptEnvelope()
			tt.mutate(&env)

			if err := env.Validate(); err == nil {
				t.Fatalf("expected unknown enum value for %s to fail validation", tt.name)
			}
		})
	}
}

func TestValidatePrivacyDispositionMatchesContentTiers(t *testing.T) {
	tests := []struct {
		name        string
		disposition evidence.PrivacyDisposition
		content     []evidence.ContentReference
		wantErr     bool
	}{
		{
			name:        "metadata only permits no content refs",
			disposition: evidence.PrivacyMetadataOnly,
			content:     nil,
		},
		{
			name:        "metadata only rejects redacted content",
			disposition: evidence.PrivacyMetadataOnly,
			content:     []evidence.ContentReference{{Tier: evidence.ContentRedacted, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}},
			wantErr:     true,
		},
		{
			name:        "redacted permits redacted and derived digests",
			disposition: evidence.PrivacyRedacted,
			content: []evidence.ContentReference{
				{Tier: evidence.ContentRedacted, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
				{Tier: evidence.ContentDerivedDigest, Digest: "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"},
			},
		},
		{
			name:        "redacted rejects vault refs",
			disposition: evidence.PrivacyRedacted,
			content:     []evidence.ContentReference{{Tier: evidence.ContentVaultRef, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", VaultURI: "vault://tenant/object"}},
			wantErr:     true,
		},
		{
			name:        "derived only permits derived digest",
			disposition: evidence.PrivacyDerivedOnly,
			content:     []evidence.ContentReference{{Tier: evidence.ContentDerivedDigest, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}},
		},
		{
			name:        "derived only rejects redacted content",
			disposition: evidence.PrivacyDerivedOnly,
			content:     []evidence.ContentReference{{Tier: evidence.ContentRedacted, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}},
			wantErr:     true,
		},
		{
			name:        "vault only permits vault refs",
			disposition: evidence.PrivacyVaultOnly,
			content:     []evidence.ContentReference{{Tier: evidence.ContentVaultRef, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", VaultURI: "vault://tenant/object"}},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := validGatewayAttemptEnvelope()
			env.Privacy.Disposition = tt.disposition
			env.Observation.Content = tt.content

			err := env.Validate()
			if tt.wantErr && err == nil {
				t.Fatal("expected disposition/content mismatch to fail validation")
			}
			if !tt.wantErr && err != nil {
				t.Fatalf("expected disposition/content combination to validate: %v", err)
			}
		})
	}
}

func TestValidateRejectsUnsafeStringsAndOversizedCollections(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*evidence.AgentEvidenceEnvelope)
	}{
		{name: "newline in id", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.ID = "env_01\nraw=secret" }},
		{name: "space in tenant id", mutate: func(env *evidence.AgentEvidenceEnvelope) { env.Tenant.TenantID = "tenant a" }},
		{name: "unsafe reason string", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Missingness.Status = evidence.MissingnessPartial
			env.Missingness.Reason = "user pasted password=secret"
		}},
		{name: "oversized readers", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Tenant.ACL.Readers = make([]string, 65)
			for i := range env.Tenant.ACL.Readers {
				env.Tenant.ACL.Readers[i] = "user:user_123"
			}
		}},
		{name: "oversized derived artifacts", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Deletion.DerivedArtifacts = make([]string, 65)
			for i := range env.Deletion.DerivedArtifacts {
				env.Deletion.DerivedArtifacts[i] = "index:gateway-attempts"
			}
		}},
		{name: "oversized behavioral signals", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			signals := make([]evidence.BehavioralSignal, 33)
			for i := range signals {
				signals[i] = evidence.BehavioralSignal{Type: evidence.BehavioralRetry, Count: 1}
			}
			env.Observation = evidence.Observation{
				Type: evidence.ObservationBehavioralFriction,
				BehavioralFriction: &evidence.BehavioralFrictionEvidence{
					WindowID: "window_01",
					Signals:  signals,
				},
			}
		}},
		{name: "unsafe judge score key", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationJudgeEvidence,
				JudgeEvidence: &evidence.JudgeEvidence{
					JudgeID:        "judge_01",
					RubricRevision: "rubric@7",
					Outcome:        evidence.JudgePassed,
					Scores:         map[string]float64{"correctness\nsecret": 0.92},
				},
			}
		}},
		{name: "oversized judge scores", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			scores := make(map[string]float64)
			for i := 0; i < 33; i++ {
				scores[fmt.Sprintf("score-%02d", i)] = 0.5
			}
			env.Observation = evidence.Observation{
				Type: evidence.ObservationJudgeEvidence,
				JudgeEvidence: &evidence.JudgeEvidence{
					JudgeID:        "judge_01",
					RubricRevision: "rubric@7",
					Outcome:        evidence.JudgePassed,
					Scores:         scores,
				},
			}
		}},
		{name: "content digest must be safe digest", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Privacy.Disposition = evidence.PrivacyRedacted
			env.Observation.Content = []evidence.ContentReference{{Tier: evidence.ContentRedacted, Digest: "not a digest"}}
		}},
		{name: "content digest must have full sha256 length", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Privacy.Disposition = evidence.PrivacyRedacted
			env.Observation.Content = []evidence.ContentReference{{Tier: evidence.ContentRedacted, Digest: "sha256:abc123"}}
		}},
		{name: "content digest must be lowercase", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Privacy.Disposition = evidence.PrivacyRedacted
			env.Observation.Content = []evidence.ContentReference{{Tier: evidence.ContentRedacted, Digest: "sha256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}}
		}},
		{name: "sampling rate rejects NaN", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Sampling.Rate = math.NaN()
		}},
		{name: "sampling rate rejects infinity", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Sampling.Rate = math.Inf(1)
		}},
		{name: "perceived friction rejects NaN", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationPerceivedFriction,
				PerceivedFriction: &evidence.PerceivedFrictionEvidence{
					InstrumentID: "survey_01", Scale: evidence.PerceivedEase, Score: math.NaN(), MaxScore: 5,
				},
			}
		}},
		{name: "judge score rejects infinity", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Observation = evidence.Observation{
				Type: evidence.ObservationJudgeEvidence,
				JudgeEvidence: &evidence.JudgeEvidence{
					JudgeID: "judge_01", RubricRevision: "rubric@7", Outcome: evidence.JudgePassed,
					Scores: map[string]float64{"correctness": math.Inf(1)},
				},
			}
		}},
		{name: "vault uri must be safe", mutate: func(env *evidence.AgentEvidenceEnvelope) {
			env.Privacy.Disposition = evidence.PrivacyVaultOnly
			env.Observation.Content = []evidence.ContentReference{{Tier: evidence.ContentVaultRef, Digest: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", VaultURI: "https://example.com/raw"}}
		}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := validGatewayAttemptEnvelope()
			tt.mutate(&env)
			if err := env.Validate(); err == nil {
				t.Fatalf("expected unsafe field %s to fail validation", tt.name)
			}
		})
	}
}

func TestDecodeStrictRejectsDuplicateKeysRecursively(t *testing.T) {
	tests := []string{
		`{"version":"agent-evidence-envelope/v1","version":"agent-evidence-envelope/v1"}`,
		`{"version":"agent-evidence-envelope/v1","producer":{"kind":"gateway","kind":"collector"}}`,
		`{"version":"agent-evidence-envelope/v1","observation":{"type":"gateway_attempt","gateway_attempt":{"request_id":"req_01","request_id":"req_02"}}}`,
		`{"version":"agent-evidence-envelope/v1","observation":{"content":[{"tier":"metadata_only","tier":"redacted"}]}}`,
	}

	for _, input := range tests {
		if _, err := evidence.DecodeStrict([]byte(input)); err == nil {
			t.Fatalf("expected duplicate key payload to fail: %s", input)
		}
	}
}

func TestValidateAcceptsEveryObservationType(t *testing.T) {
	tests := []struct {
		name        string
		observation evidence.Observation
	}{
		{
			name:        "gateway attempt",
			observation: validGatewayAttemptEnvelope().Observation,
		},
		{
			name: "terminal outcome",
			observation: evidence.Observation{
				Type: evidence.ObservationTerminalOutcome,
				TerminalOutcome: &evidence.TerminalOutcomeEvidence{
					SessionID:         "session_01",
					TaskID:            "task_01",
					Outcome:           evidence.TerminalOutcomeSucceeded,
					Source:            evidence.TerminalOutcomeCollector,
					CompletedAt:       time.Unix(1700000100, 0).UTC(),
					GatewayRequestIDs: []string{"req_01"},
				},
			},
		},
		{
			name: "deterministic test",
			observation: evidence.Observation{
				Type: evidence.ObservationDeterministicTest,
				DeterministicTest: &evidence.DeterministicTestEvidence{
					RunID:            "run_01",
					Suite:            "go-test",
					Case:             "TestFoo",
					Status:           evidence.TestPassed,
					ToolRevision:     "go@1.26.4",
					ArtifactDigest:   "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
					TranscriptDigest: "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
				},
			},
		},
		{
			name: "user report",
			observation: evidence.Observation{
				Type: evidence.ObservationUserReport,
				UserReport: &evidence.UserReportEvidence{
					ReportID:            "report_01",
					ReportType:          evidence.UserReportCorrection,
					ReasonCode:          "wrong-file",
					TargetObservationID: "env_01",
				},
			},
		},
		{
			name: "behavioral friction",
			observation: evidence.Observation{
				Type: evidence.ObservationBehavioralFriction,
				BehavioralFriction: &evidence.BehavioralFrictionEvidence{
					WindowID: "window_01",
					Signals: []evidence.BehavioralSignal{
						{Type: evidence.BehavioralRetry, Count: 2},
						{Type: evidence.BehavioralToolFailure, Count: 1},
					},
				},
			},
		},
		{
			name: "perceived friction",
			observation: evidence.Observation{
				Type: evidence.ObservationPerceivedFriction,
				PerceivedFriction: &evidence.PerceivedFrictionEvidence{
					InstrumentID: "survey_01",
					Scale:        evidence.PerceivedEase,
					Score:        4,
					MaxScore:     5,
				},
			},
		},
		{
			name: "judge evidence",
			observation: evidence.Observation{
				Type: evidence.ObservationJudgeEvidence,
				JudgeEvidence: &evidence.JudgeEvidence{
					JudgeID:           "judge_01",
					RubricRevision:    "rubric@7",
					Outcome:           evidence.JudgePassed,
					Scores:            map[string]float64{"correctness": 0.92},
					ExplanationDigest: "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
				},
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := validGatewayAttemptEnvelope()
			env.ID = "env_" + strings.ReplaceAll(tt.name, " ", "-")
			env.Observation = tt.observation

			if err := env.Validate(); err != nil {
				t.Fatalf("expected %s to validate: %v", tt.name, err)
			}
		})
	}
}

func TestValidateRejectsRawContentAndAmbiguousObservationBodies(t *testing.T) {
	t.Run("raw content reference tier is prohibited", func(t *testing.T) {
		env := validGatewayAttemptEnvelope()
		env.Observation.Content = []evidence.ContentReference{{
			Tier:   evidence.ContentTier("raw"),
			Digest: "sha256:raw",
		}}

		if err := env.Validate(); err == nil {
			t.Fatal("expected raw content tier to fail validation")
		}
	})

	t.Run("observation type must match exactly one body", func(t *testing.T) {
		env := validGatewayAttemptEnvelope()
		env.Observation.TerminalOutcome = &evidence.TerminalOutcomeEvidence{
			SessionID:         "session_01",
			TaskID:            "task_01",
			Outcome:           evidence.TerminalOutcomeSucceeded,
			Source:            evidence.TerminalOutcomeCollector,
			CompletedAt:       time.Unix(1700000100, 0).UTC(),
			GatewayRequestIDs: []string{"req_01"},
		}

		if err := env.Validate(); err == nil {
			t.Fatal("expected multiple observation bodies to fail validation")
		}
	})
}

func TestDecodeStrictRejectsRawContentFieldsAndRoundTrips(t *testing.T) {
	env := validGatewayAttemptEnvelope()
	data, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal valid envelope: %v", err)
	}

	decoded, err := evidence.DecodeStrict(data)
	if err != nil {
		t.Fatalf("strict decode valid envelope: %v", err)
	}
	if err := decoded.Validate(); err != nil {
		t.Fatalf("decoded envelope failed validation: %v", err)
	}

	encoded, err := evidence.EncodeCanonical(decoded)
	if err != nil {
		t.Fatalf("encode canonical: %v", err)
	}
	decodedAgain, err := evidence.DecodeStrict(encoded)
	if err != nil {
		t.Fatalf("strict decode canonical envelope: %v", err)
	}
	if decodedAgain.ID != env.ID || decodedAgain.Revisions.Authority != env.Revisions.Authority {
		t.Fatalf("roundtrip lost join keys: got id=%q authority=%q", decodedAgain.ID, decodedAgain.Revisions.Authority)
	}

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatalf("unmarshal valid envelope to map: %v", err)
	}
	observation := raw["observation"].(map[string]any)
	observation["raw_content"] = "do not store this"
	rawData, err := json.Marshal(raw)
	if err != nil {
		t.Fatalf("marshal raw-content envelope: %v", err)
	}
	if _, err := evidence.DecodeStrict(rawData); err == nil {
		t.Fatal("expected raw_content field to fail strict decode")
	}

	if _, err := evidence.DecodeStrict(append(data, []byte(` {"version":"agent-evidence-envelope/v1"}`)...)); err == nil {
		t.Fatal("expected trailing JSON value to fail strict decode")
	}
}

func FuzzDecodeStrictRoundTrip(f *testing.F) {
	env := validGatewayAttemptEnvelope()
	data, err := json.Marshal(env)
	if err != nil {
		f.Fatalf("marshal seed: %v", err)
	}
	f.Add(string(data))
	f.Add(`{"version":"agent-evidence-envelope/v1","observation":{"raw_content":"secret"}}`)
	f.Add(`{"version":"agent-evidence-envelope/v1","version":"agent-evidence-envelope/v1"}`)
	f.Add(`{"version":"agent-evidence-envelope/v1","producer":{"kind":"gateway","kind":"collector"}}`)
	f.Add(`{"version":"agent-evidence-envelope/v1","missingness":{"status":"partial","reason":"password=secret"}}`)
	f.Add(`{"version":"agent-evidence-envelope/v1","producer":{"kind":"browser-plugin"}}`)
	f.Add(`not-json`)

	f.Fuzz(func(t *testing.T, input string) {
		env, err := evidence.DecodeStrict([]byte(input))
		if err != nil {
			return
		}
		encoded, err := evidence.EncodeCanonical(env)
		if err != nil {
			t.Fatalf("canonical encode after strict decode: %v", err)
		}
		if _, err := evidence.DecodeStrict(encoded); err != nil {
			t.Fatalf("canonical output failed strict decode: %v", err)
		}
	})
}

func validGatewayAttemptEnvelope() evidence.AgentEvidenceEnvelope {
	return evidence.AgentEvidenceEnvelope{
		Version:    evidence.VersionV1,
		ID:         "env_01",
		ObservedAt: time.Unix(1700000000, 0).UTC(),
		Producer: evidence.ProducerRef{
			Kind:     evidence.ProducerGateway,
			ID:       "gateway-pod-a",
			Revision: "collector@sha256:1111111111111111111111111111111111111111111111111111111111111111",
		},
		Tenant: evidence.TenantScope{
			TenantID:  "tenant_a",
			Purpose:   evidence.PurposeEvaluation,
			Residency: "us",
			Subject: evidence.SubjectRef{
				Kind: evidence.SubjectUser,
				ID:   "user_123",
			},
			ACL: evidence.AccessControl{
				Visibility: evidence.VisibilityPrivate,
				Readers:    []string{"user:user_123"},
			},
		},
		Privacy: evidence.PrivacyReceipt{
			ID:                "privacy_receipt_01",
			PolicyRevision:    "privacy-policy@17",
			TransformRevision: "redactor@sha256:2222222222222222222222222222222222222222222222222222222222222222",
			Disposition:       evidence.PrivacyMetadataOnly,
			RetentionClass:    "ephemeral-30d",
			DeletionPolicyID:  "delete-policy-01",
		},
		Sampling: evidence.SamplingInfo{
			Decision: evidence.SamplingIncluded,
			Rate:     1,
			Seed:     "seed_01",
		},
		Missingness: evidence.MissingnessInfo{
			Status: evidence.MissingnessComplete,
		},
		Deletion: evidence.DeletionLineage{
			LineageID:        "deletion_lineage_01",
			DeletionState:    evidence.DeletionActive,
			SubjectToDelete:  true,
			DerivedArtifacts: []string{"index:gateway-attempts"},
		},
		Revisions: evidence.RevisionJoinKeys{
			Authority: "authority@42",
			Policy:    "policy@42",
			Privacy:   "privacy@17",
			Route:     "route@9",
			Gateway:   "gateway@sha256:3333333333333333333333333333333333333333333333333333333333333333",
		},
		Observation: evidence.Observation{
			Type: evidence.ObservationGatewayAttempt,
			GatewayAttempt: &evidence.GatewayAttemptEvidence{
				RequestID:    "req_01",
				AttemptID:    "attempt_01",
				Provider:     "openai",
				Model:        "gpt-4.1",
				RequestType:  "chat.completion",
				Outcome:      evidence.AttemptSucceeded,
				FallbackSlot: 0,
			},
		},
	}
}
