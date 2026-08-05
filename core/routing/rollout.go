package routing

import (
	"errors"
	"fmt"
	"math"
	"sync"
)

var (
	ErrInvalidRolloutPolicy  = errors.New("invalid rollout policy")
	ErrInvalidRolloutMetrics = errors.New("invalid rollout metrics")
	ErrStaleRolloutRevision  = errors.New("stale rollout revision")
	ErrNoRollbackTarget      = errors.New("no last-known-good rollout revision")
)

// GateState is the durable state of a rollout decision. Pending is never
// promotable; rejected and rolled_back are explicit evidence that a candidate
// did not become the active revision.
type GateState string

const (
	GatePending    GateState = "pending"
	GateApproved   GateState = "approved"
	GateRejected   GateState = "rejected"
	GateRolledBack GateState = "rolled_back"
)

// RolloutPolicy is the bounded, deterministic contract for promoting a model
// or Agent Card revision. Thresholds are inclusive: a candidate passes when
// its observed value is less than or equal to the configured limit.
type RolloutPolicy struct {
	Experiment         string  `json:"experiment"`
	Revision           uint64  `json:"revision"`
	RolloutBasisPoints int     `json:"rollout_basis_points"`
	MinSamples         int     `json:"min_samples"`
	MaxErrorRate       float64 `json:"max_error_rate"`
	MaxP95LatencyMS    float64 `json:"max_p95_latency_ms"`
	MaxCostPerRequest  float64 `json:"max_cost_per_request"`
}

func (p RolloutPolicy) Validate() error {
	if p.Experiment == "" || p.Revision == 0 || p.RolloutBasisPoints < 0 || p.RolloutBasisPoints > basisPoints || p.MinSamples <= 0 ||
		!finiteNonNegative(p.MaxErrorRate) || p.MaxErrorRate > 1 || !finiteNonNegative(p.MaxP95LatencyMS) || !finiteNonNegative(p.MaxCostPerRequest) {
		return fmt.Errorf("%w: experiment, revision, rollout, sample count, and finite non-negative thresholds are required", ErrInvalidRolloutPolicy)
	}
	return nil
}

// WithRevision returns the existing deterministic assignment with the
// immutable candidate revision attached for trace and audit evidence.
func (p RolloutPolicy) WithRevision(subject string) (Assignment, error) {
	if err := p.Validate(); err != nil {
		return Assignment{}, err
	}
	assignment := Assign(subject, p.Experiment, p.RolloutBasisPoints)
	assignment.Revision = p.Revision
	return assignment, nil
}

type RolloutMetrics struct {
	Samples        int     `json:"samples"`
	Errors         int     `json:"errors"`
	P95LatencyMS   float64 `json:"p95_latency_ms"`
	CostPerRequest float64 `json:"cost_per_request"`
}

type GateDecision struct {
	Experiment     string    `json:"experiment"`
	Revision       uint64    `json:"revision"`
	State          GateState `json:"state"`
	Reason         string    `json:"reason"`
	Samples        int       `json:"samples"`
	ErrorRate      float64   `json:"error_rate"`
	P95LatencyMS   float64   `json:"p95_latency_ms"`
	CostPerRequest float64   `json:"cost_per_request"`
}

func (p RolloutPolicy) Evaluate(m RolloutMetrics) GateDecision {
	d := GateDecision{Experiment: p.Experiment, Revision: p.Revision, Samples: m.Samples, P95LatencyMS: m.P95LatencyMS, CostPerRequest: m.CostPerRequest}
	if err := p.Validate(); err != nil {
		d.State, d.Reason = GateRejected, "invalid_policy"
		return d
	}
	if m.Samples < 0 || m.Errors < 0 || m.Errors > m.Samples || !finiteNonNegative(m.P95LatencyMS) || !finiteNonNegative(m.CostPerRequest) {
		d.State, d.Reason = GateRejected, "invalid_metrics"
		return d
	}
	if m.Samples > 0 {
		d.ErrorRate = float64(m.Errors) / float64(m.Samples)
	}
	if m.Samples < p.MinSamples {
		d.State, d.Reason = GatePending, "insufficient_samples"
		return d
	}
	switch {
	case d.ErrorRate > p.MaxErrorRate:
		d.State, d.Reason = GateRejected, "error_rate"
	case d.P95LatencyMS > p.MaxP95LatencyMS:
		d.State, d.Reason = GateRejected, "p95_latency"
	case d.CostPerRequest > p.MaxCostPerRequest:
		d.State, d.Reason = GateRejected, "cost_per_request"
	default:
		d.State, d.Reason = GateApproved, "gates_passed"
	}
	return d
}

func (d GateDecision) TraceAttributes() map[string]any {
	return map[string]any{
		"rollout.experiment":       d.Experiment,
		"rollout.revision":         d.Revision,
		"rollout.gate":             string(d.State),
		"rollout.reason":           d.Reason,
		"rollout.samples":          d.Samples,
		"rollout.error_rate":       d.ErrorRate,
		"rollout.p95_latency_ms":   d.P95LatencyMS,
		"rollout.cost_per_request": d.CostPerRequest,
	}
}

// RolloutSnapshot is the small immutable operator view of a controller. The
// revision and generation make stale promotion attempts auditable.
type RolloutSnapshot struct {
	ActiveRevision        uint64       `json:"active_revision"`
	LastKnownGoodRevision uint64       `json:"last_known_good_revision"`
	State                 GateState    `json:"state"`
	Decision              GateDecision `json:"decision"`
	Generation            uint64       `json:"generation"`
}

type RolloutController struct {
	mu       sync.RWMutex
	snapshot RolloutSnapshot
}

func NewRolloutController(lastKnownGood uint64) *RolloutController {
	return &RolloutController{snapshot: RolloutSnapshot{ActiveRevision: lastKnownGood, LastKnownGoodRevision: lastKnownGood, State: GateApproved}}
}

func (c *RolloutController) Snapshot() RolloutSnapshot {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.snapshot
}

// Promote atomically activates an approved revision. Revisions are monotonic;
// a controller never allows an older or malformed candidate to overwrite the
// active state. The previous active revision becomes the rollback target.
func (c *RolloutController) Promote(decision GateDecision) error {
	if c == nil || decision.State != GateApproved || decision.Revision == 0 || decision.Experiment == "" {
		return fmt.Errorf("%w: only a valid approved decision can be promoted", ErrInvalidRolloutPolicy)
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.snapshot.ActiveRevision != 0 && decision.Revision <= c.snapshot.ActiveRevision {
		return fmt.Errorf("%w: candidate %d is not newer than active %d", ErrStaleRolloutRevision, decision.Revision, c.snapshot.ActiveRevision)
	}
	if c.snapshot.ActiveRevision != 0 {
		c.snapshot.LastKnownGoodRevision = c.snapshot.ActiveRevision
	}
	c.snapshot.ActiveRevision = decision.Revision
	c.snapshot.State = GateApproved
	c.snapshot.Decision = decision
	c.snapshot.Generation++
	return nil
}

// Rollback restores the retained last-known-good revision. It is deliberately
// explicit and records the reason so an operator action is visible in traces
// and audit records without retaining request content.
func (c *RolloutController) Rollback(reason string) (RolloutSnapshot, error) {
	if c == nil {
		return RolloutSnapshot{}, ErrNoRollbackTarget
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.snapshot.LastKnownGoodRevision == 0 || c.snapshot.LastKnownGoodRevision == c.snapshot.ActiveRevision {
		return c.snapshot, ErrNoRollbackTarget
	}
	c.snapshot.ActiveRevision = c.snapshot.LastKnownGoodRevision
	c.snapshot.State = GateRolledBack
	c.snapshot.Decision.State = GateRolledBack
	c.snapshot.Decision.Reason = reason
	c.snapshot.Generation++
	return c.snapshot, nil
}

func finiteNonNegative(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value >= 0
}
