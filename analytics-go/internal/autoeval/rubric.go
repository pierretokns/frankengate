package autoeval

import (
	"fmt"
	"math"
	"strings"
	"time"
)

func ValidateRubric(r Rubric) error {
	if r.SchemaVersion != "autoeval-rubric-v1" {
		return fmt.Errorf("unsupported rubric schema_version %q", r.SchemaVersion)
	}
	if strings.TrimSpace(r.RubricID) == "" || strings.TrimSpace(r.TaskFamily) == "" || strings.TrimSpace(r.Objective) == "" {
		return fmt.Errorf("rubric_id, task_family, and objective are required")
	}
	if len(r.Weights) == 0 {
		return fmt.Errorf("weights are required")
	}
	var total float64
	for name, weight := range r.Weights {
		if strings.TrimSpace(name) == "" || weight < 0 || math.IsNaN(weight) || math.IsInf(weight, 0) {
			return fmt.Errorf("invalid weight %q", name)
		}
		total += weight
	}
	if math.Abs(total-1) > 1e-6 {
		return fmt.Errorf("weights must sum to 1, got %f", total)
	}
	return nil
}

func Score(r Rubric, a ActionAssessment) (Judgment, error) {
	if err := ValidateRubric(r); err != nil {
		return Judgment{}, err
	}
	j := Judgment{SchemaVersion: JudgmentVersion, CaseID: a.CaseID, CandidateID: a.CandidateID, TraceID: a.TraceID, RubricID: r.RubricID, DimensionScores: map[string]float64{}, EvidenceEventIDs: append([]string(nil), a.EvidenceEventIDs...), CreatedAt: time.Now().UTC()}
	j.HardViolations = append([]string(nil), a.HardViolations...)
	if !a.Authorized {
		j.HardViolations = append(j.HardViolations, "unauthorized_action")
	}
	if !a.ValidSchema {
		j.HardViolations = append(j.HardViolations, "invalid_action_schema")
	}
	if a.FutureLeak {
		j.HardViolations = append(j.HardViolations, "future_leak")
	}
	if len(j.HardViolations) > 0 {
		j.Value = 0
		j.Confidence = 1
		j.ReasonCodes = []string{"hard_constraint_violation"}
		return j, nil
	}
	if a.InsufficientState {
		j.Abstain = true
		j.ReasonCodes = []string{"insufficient_state"}
		return j, nil
	}
	var total float64
	for name, weight := range r.Weights {
		value, ok := a.Dimensions[name]
		if !ok || value < 0 || value > 4 || math.IsNaN(value) || math.IsInf(value, 0) {
			return Judgment{}, fmt.Errorf("dimension %q must be in [0,4]", name)
		}
		j.DimensionScores[name] = value
		total += weight * value
	}
	j.Value = int(math.Round(total))
	if j.Value < 0 {
		j.Value = 0
	}
	if j.Value > 4 {
		j.Value = 4
	}
	j.Confidence = 0.75
	j.ReasonCodes = []string{"rubric_dimensions_validated"}
	return j, nil
}
