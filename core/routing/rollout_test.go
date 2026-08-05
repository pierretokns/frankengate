package routing

import (
	"errors"
	"math"
	"sync"
	"testing"
)

func testRolloutPolicy() RolloutPolicy {
	return RolloutPolicy{Experiment: "agent-card", Revision: 2, RolloutBasisPoints: 1000, MinSamples: 100, MaxErrorRate: 0.02, MaxP95LatencyMS: 250, MaxCostPerRequest: 0.10}
}

func TestRolloutPolicyEvaluation(t *testing.T) {
	policy := testRolloutPolicy()
	if got := policy.Evaluate(RolloutMetrics{Samples: 10}).Reason; got != "insufficient_samples" {
		t.Fatalf("pending reason = %q", got)
	}
	if got := policy.Evaluate(RolloutMetrics{Samples: 100, Errors: 3}).Reason; got != "error_rate" {
		t.Fatalf("rejection reason = %q", got)
	}
	decision := policy.Evaluate(RolloutMetrics{Samples: 100, Errors: 1, P95LatencyMS: 200, CostPerRequest: 0.05})
	if decision.State != GateApproved || decision.Reason != "gates_passed" {
		t.Fatalf("decision = %+v", decision)
	}
}

func TestRolloutPolicyFailsClosedOnMalformedInput(t *testing.T) {
	policy := testRolloutPolicy()
	if got := (RolloutPolicy{}).Evaluate(RolloutMetrics{}); got.State != GateRejected || got.Reason != "invalid_policy" {
		t.Fatalf("invalid policy decision = %+v", got)
	}
	if got := policy.Evaluate(RolloutMetrics{Samples: 1, P95LatencyMS: math.NaN()}); got.State != GateRejected || got.Reason != "invalid_metrics" {
		t.Fatalf("invalid metrics decision = %+v", got)
	}
	if _, err := policy.WithRevision(""); err != nil && !errors.Is(err, ErrInvalidRolloutPolicy) {
		t.Fatalf("unexpected assignment error: %v", err)
	}
}

func TestRolloutControllerPromotionAndRollback(t *testing.T) {
	c := NewRolloutController(1)
	decision := testRolloutPolicy().Evaluate(RolloutMetrics{Samples: 100, Errors: 1, P95LatencyMS: 200, CostPerRequest: 0.05})
	if err := c.Promote(decision); err != nil {
		t.Fatalf("promote: %v", err)
	}
	if err := c.Promote(decision); !errors.Is(err, ErrStaleRolloutRevision) {
		t.Fatalf("stale promote error = %v", err)
	}
	snapshot, err := c.Rollback("error budget regression")
	if err != nil {
		t.Fatalf("rollback: %v", err)
	}
	if snapshot.ActiveRevision != 1 || snapshot.State != GateRolledBack || snapshot.Decision.Reason != "error budget regression" {
		t.Fatalf("rollback snapshot = %+v", snapshot)
	}
}

func TestRolloutControllerConcurrentSnapshot(t *testing.T) {
	c := NewRolloutController(1)
	decision := testRolloutPolicy().Evaluate(RolloutMetrics{Samples: 100, Errors: 1, P95LatencyMS: 200, CostPerRequest: 0.05})
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = c.Promote(decision)
			_ = c.Snapshot()
		}()
	}
	wg.Wait()
}

func TestRolloutTraceAttributesIncludeRevision(t *testing.T) {
	assignment, err := testRolloutPolicy().WithRevision("tenant-a")
	if err != nil {
		t.Fatalf("assignment: %v", err)
	}
	if assignment.TraceAttributes()["routing.revision"] != uint64(2) {
		t.Fatalf("assignment attrs = %+v", assignment.TraceAttributes())
	}
	decision := testRolloutPolicy().Evaluate(RolloutMetrics{Samples: 100, Errors: 1, P95LatencyMS: 200, CostPerRequest: 0.05})
	if decision.TraceAttributes()["rollout.revision"] != uint64(2) {
		t.Fatalf("decision attrs = %+v", decision.TraceAttributes())
	}
}
