package vectorstore

import (
	"sync"
	"testing"
)

func TestEvaluateRetrievalQualityAndFreshness(t *testing.T) {
	authority := testAuthority()
	good := authorizedProps()
	stale := authorizedProps()
	stale[AuthorizationSourceRevision] = "old"
	deleted := authorizedProps()
	deleted["fg_auth_deleted"] = true
	e := EvaluateRetrieval([]string{"a", "b", "missing"}, []SearchResult{
		{ID: "a", Properties: good},
		{ID: "x", Properties: stale},
		{ID: "b", Properties: deleted},
		{ID: "a", Properties: good}, // duplicates must not inflate scores
	}, 2, authority)
	if e.Expected != 3 || e.Retrieved != 3 || e.RelevantRetrieved != 2 {
		t.Fatalf("unexpected counts: %+v", e)
	}
	if e.Precision != 2.0/3.0 || e.Recall != 2.0/3.0 {
		t.Fatalf("unexpected quality ratios: %+v", e)
	}
	if e.ACLDenials != 2 || e.StaleResults != 2 || e.DeletedResults != 1 || e.FreshResults != 1 || e.Freshness != 1.0/3.0 {
		t.Fatalf("unexpected freshness counts: %+v", e)
	}
}

func TestRetrievalQualityCountersIsBoundedAndConcurrent(t *testing.T) {
	var counters RetrievalQualityCounters
	e := RetrievalEvaluation{Retrieved: 2, RelevantRetrieved: 1, ACLDenials: 1, StaleResults: 1, DeletedResults: 1, FreshResults: 1}
	var wg sync.WaitGroup
	for i := 0; i < 32; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				counters.Observe(e)
			}
		}()
	}
	wg.Wait()
	s := counters.Snapshot()
	if s.Retrievals != 3200 || s.Retrieved != 6400 || s.ACLDenials != 3200 {
		t.Fatalf("unexpected snapshot: %+v", s)
	}
}
