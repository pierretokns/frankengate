// Package routing contains small, deterministic primitives shared by routing
// policy implementations. It deliberately has no provider or request-path
// dependencies.
package routing

import "crypto/sha256"

const basisPoints = 10_000

// Assignment is the side-effect-free result of evaluating a rollout. Keeping
// the bucket and configured rollout alongside the boolean makes it possible for
// callers to emit an auditable decision without re-hashing the request. It is
// intentionally a policy primitive: it does not execute either provider or
// reserve budget for a shadow request.
type Assignment struct {
	Subject            string `json:"subject"`
	Experiment         string `json:"experiment"`
	Revision           uint64 `json:"revision,omitempty"`
	Bucket             uint32 `json:"bucket"`
	RolloutBasisPoints int    `json:"rollout_basis_points"`
	InTreatment        bool   `json:"in_treatment"`
}

// TraceAttributes returns bounded, non-secret assignment metadata suitable for
// trace-level evidence. The subject is intentionally excluded because it may
// contain an identity or tenant identifier; callers can join it through their
// existing privacy-safe trace correlation fields.
func (a Assignment) TraceAttributes() map[string]any {
	attrs := map[string]any{
		"routing.experiment":           a.Experiment,
		"routing.bucket":               a.Bucket,
		"routing.rollout_basis_points": a.RolloutBasisPoints,
		"routing.in_treatment":         a.InTreatment,
	}
	if a.Revision != 0 {
		attrs["routing.revision"] = a.Revision
	}
	return attrs
}

// ApplyTraceAttributes sends the privacy-safe assignment metadata to a trace
// attribute sink. A nil sink is a no-op so optional observability cannot affect
// routing behavior.
func (a Assignment) ApplyTraceAttributes(set func(string, any)) {
	if set == nil {
		return
	}
	for key, value := range a.TraceAttributes() {
		set(key, value)
	}
}

// Assign evaluates a deterministic rollout and returns its complete decision.
// Empty subjects/namespaces and invalid percentages fail closed. Callers may
// use InTreatment to gate a canary and retain Assignment for telemetry.
func Assign(subject, experiment string, rolloutBasisPoints int) Assignment {
	assignment := Assignment{
		Subject:            subject,
		Experiment:         experiment,
		RolloutBasisPoints: rolloutBasisPoints,
	}
	if subject == "" || experiment == "" || rolloutBasisPoints <= 0 || rolloutBasisPoints > basisPoints {
		return assignment
	}
	assignment.Bucket = Bucket(subject, experiment)
	assignment.InTreatment = int(assignment.Bucket) < rolloutBasisPoints
	return assignment
}

// Bucket returns a stable value in [0, basisPoints) for a subject and
// experiment. The experiment namespace prevents assignments from correlating
// across independent rollouts.
func Bucket(subject, experiment string) uint32 {
	digest := sha256.Sum256([]byte(experiment + "\x00" + subject))
	value := uint32(digest[0])<<24 | uint32(digest[1])<<16 | uint32(digest[2])<<8 | uint32(digest[3])
	return value % basisPoints
}

// InTreatment reports whether a subject belongs to a rollout percentage
// expressed in basis points (0..10000). Invalid percentages fail closed.
func InTreatment(subject, experiment string, rolloutBasisPoints int) bool {
	if rolloutBasisPoints <= 0 || rolloutBasisPoints > basisPoints {
		return false
	}
	return int(Bucket(subject, experiment)) < rolloutBasisPoints
}
