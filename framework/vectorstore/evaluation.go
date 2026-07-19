package vectorstore

import (
	"sync"
)

// RetrievalEvaluation is a bounded, backend-neutral quality record. It is
// deliberately made up of counts and ratios only: IDs, queries, embeddings,
// principals, and payloads must never be emitted as telemetry.
type RetrievalEvaluation struct {
	Expected          int
	Retrieved         int
	RelevantRetrieved int
	ACLDenials        int
	StaleResults      int
	DeletedResults    int
	FreshResults      int
	Precision         float64
	Recall            float64
	Freshness         float64
}

// EvaluateRetrieval compares returned candidates with a labelled set and the
// authority envelope used for the search. ACL denials are supplied by the
// authorization boundary because denied candidates are intentionally absent
// from the result set. Duplicate IDs are counted once.
func EvaluateRetrieval(expectedIDs []string, results []SearchResult, aclDenials int, authority AuthorizationEnvelope) RetrievalEvaluation {
	expected := make(map[string]struct{}, len(expectedIDs))
	for _, id := range expectedIDs {
		if id != "" {
			expected[id] = struct{}{}
		}
	}
	seen := make(map[string]struct{}, len(results))
	e := RetrievalEvaluation{Expected: len(expected), ACLDenials: maxNonNegative(aclDenials)}
	for _, result := range results {
		if result.ID == "" {
			continue
		}
		if _, duplicate := seen[result.ID]; duplicate {
			continue
		}
		seen[result.ID] = struct{}{}
		e.Retrieved++
		if _, relevant := expected[result.ID]; relevant {
			e.RelevantRetrieved++
		}
		if resultFresh(result, authority) {
			e.FreshResults++
		} else {
			e.StaleResults++
		}
		if resultDeleted(result, authority) {
			e.DeletedResults++
		}
	}
	if e.Retrieved > 0 {
		e.Precision = float64(e.RelevantRetrieved) / float64(e.Retrieved)
	}
	if e.Expected > 0 {
		e.Recall = float64(e.RelevantRetrieved) / float64(e.Expected)
	}
	if e.Retrieved > 0 {
		e.Freshness = float64(e.FreshResults) / float64(e.Retrieved)
	}
	return e
}

func resultFresh(result SearchResult, authority AuthorizationEnvelope) bool {
	p := result.Properties
	return stringValue(p[AuthorizationSourceRevision]) == authority.SourceRevision &&
		stringValue(p[AuthorizationIndexRevision]) == authority.IndexRevision &&
		!resultDeleted(result, authority)
}

func resultDeleted(result SearchResult, authority AuthorizationEnvelope) bool {
	p := result.Properties
	if deleted, ok := p["fg_auth_deleted"].(bool); ok && deleted {
		return true
	}
	epoch, ok := integerValue(p[AuthorizationDeletionEpoch])
	return ok && epoch < authority.DeletionEpoch
}

func maxNonNegative(value int) int {
	if value < 0 {
		return 0
	}
	return value
}

// RetrievalQualityCounters is an intentionally low-cardinality accumulator
// suitable for exposing through Prometheus or OTEL. It has no labels and is
// safe to share between requests and goroutines.
type RetrievalQualityCounters struct {
	mu                                                                 sync.Mutex
	Retrievals, Retrieved, Relevant, ACLDenials, Stale, Deleted, Fresh int64
}

type RetrievalQualitySnapshot struct {
	Retrievals, Retrieved, Relevant, ACLDenials, Stale, Deleted, Fresh int64
}

func (c *RetrievalQualityCounters) Observe(e RetrievalEvaluation) {
	if c == nil {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.Retrievals++
	c.Retrieved += int64(e.Retrieved)
	c.Relevant += int64(e.RelevantRetrieved)
	c.ACLDenials += int64(e.ACLDenials)
	c.Stale += int64(e.StaleResults)
	c.Deleted += int64(e.DeletedResults)
	c.Fresh += int64(e.FreshResults)
}

func (c *RetrievalQualityCounters) Snapshot() RetrievalQualitySnapshot {
	if c == nil {
		return RetrievalQualitySnapshot{}
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	return RetrievalQualitySnapshot{Retrievals: c.Retrievals, Retrieved: c.Retrieved, Relevant: c.Relevant, ACLDenials: c.ACLDenials, Stale: c.Stale, Deleted: c.Deleted, Fresh: c.Fresh}
}
