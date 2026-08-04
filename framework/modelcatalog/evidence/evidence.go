// Package evidence validates and converts evaluation results without treating
// a benchmark score as a safety, quality, or routing authorization claim.
package evidence

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

type Record struct {
	Name            string
	Metric          string
	Score           *float64
	Status          agentcard.ProvenanceStatus
	DatasetURI      string
	DatasetRevision string
	ReportURI       string
	Methodology     string
	SourceURI       string
	Verifier        string
	Confidence      *float64
	RunRevision     string
	Reproducible    *bool
	Slice           map[string]string
	ObservedAt      string
	Stale           bool
}

func (r Record) Validate() error {
	if strings.TrimSpace(r.Name) == "" {
		return fmt.Errorf("evaluation name is required")
	}
	if r.Status == "" {
		return fmt.Errorf("evaluation status is required")
	}
	if r.Score != nil && (*r.Score < 0 || *r.Score > 1) {
		return fmt.Errorf("evaluation score must be between 0 and 1")
	}
	if r.Confidence != nil && (*r.Confidence < 0 || *r.Confidence > 1) {
		return fmt.Errorf("evaluation confidence must be between 0 and 1")
	}
	if len(r.Slice) > 32 {
		return fmt.Errorf("evaluation slice must contain at most 32 entries")
	}
	for key, value := range r.Slice {
		if key == "" || len(key) > 96 || len(value) > 256 {
			return fmt.Errorf("evaluation slice contains an invalid entry")
		}
	}
	return nil
}

func (r Record) ToCardEvidence() (agentcard.EvaluationEvidence, error) {
	if err := r.Validate(); err != nil {
		return agentcard.EvaluationEvidence{}, err
	}
	result := agentcard.EvaluationEvidence{
		Name: r.Name, Metric: r.Metric, Score: cloneFloat(r.Score), Status: r.Status,
		DatasetRevision: r.DatasetRevision, Methodology: r.Methodology, Verifier: r.Verifier,
		Confidence: cloneFloat(r.Confidence), RunRevision: r.RunRevision,
		Reproducible: cloneBool(r.Reproducible), Slice: cloneMap(r.Slice), ObservedAt: r.ObservedAt, Stale: r.Stale,
	}
	if r.DatasetURI != "" {
		result.DatasetRef = &agentcard.ContentRef{URI: r.DatasetURI}
	}
	if r.ReportURI != "" {
		result.ReportRef = &agentcard.ContentRef{URI: r.ReportURI}
	}
	if r.SourceURI != "" {
		result.Source = &agentcard.ContentRef{URI: r.SourceURI}
	}
	return result, nil
}

func FromCardEvidence(evidence agentcard.EvaluationEvidence) Record {
	result := Record{
		Name: evidence.Name, Metric: evidence.Metric, Score: cloneFloat(evidence.Score), Status: evidence.Status,
		DatasetRevision: evidence.DatasetRevision, Methodology: evidence.Methodology, Verifier: evidence.Verifier,
		Confidence: cloneFloat(evidence.Confidence), RunRevision: evidence.RunRevision,
		Reproducible: cloneBool(evidence.Reproducible), Slice: cloneMap(evidence.Slice), ObservedAt: evidence.ObservedAt, Stale: evidence.Stale,
	}
	if evidence.DatasetRef != nil {
		result.DatasetURI = evidence.DatasetRef.URI
	}
	if evidence.ReportRef != nil {
		result.ReportURI = evidence.ReportRef.URI
	}
	if evidence.Source != nil {
		result.SourceURI = evidence.Source.URI
	}
	return result
}

// RoundTripJSON provides a deterministic export/import check for card
// evidence. encoding/json sorts map keys, so equivalent slices serialize
// consistently without exposing arbitrary map order to callers.
func RoundTripJSON(record Record) (Record, error) {
	if err := record.Validate(); err != nil {
		return Record{}, err
	}
	data, err := json.Marshal(record)
	if err != nil {
		return Record{}, err
	}
	var decoded Record
	if err := json.Unmarshal(data, &decoded); err != nil {
		return Record{}, err
	}
	if err := decoded.Validate(); err != nil {
		return Record{}, err
	}
	return decoded, nil
}

func Sort(records []Record) []Record {
	result := append([]Record(nil), records...)
	sort.SliceStable(result, func(i, j int) bool {
		if result[i].Name != result[j].Name {
			return result[i].Name < result[j].Name
		}
		return result[i].RunRevision < result[j].RunRevision
	})
	return result
}

func cloneFloat(value *float64) *float64 {
	if value == nil {
		return nil
	}
	copy := *value
	return &copy
}

func cloneBool(value *bool) *bool {
	if value == nil {
		return nil
	}
	copy := *value
	return &copy
}

func cloneMap(value map[string]string) map[string]string {
	if value == nil {
		return nil
	}
	copy := make(map[string]string, len(value))
	for key, item := range value {
		copy[key] = item
	}
	return copy
}
