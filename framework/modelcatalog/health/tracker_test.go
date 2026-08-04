package health

import (
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

func TestTrackerSummarizesBoundedSamplesAndStaleness(t *testing.T) {
	now := time.Date(2026, time.August, 4, 12, 0, 0, 0, time.UTC)
	tracker := New(func() time.Time { return now }, time.Minute)
	for _, sample := range []Sample{
		{At: now.Add(-30 * time.Second), Latency: 100 * time.Millisecond, Succeeded: true},
		{At: now.Add(-20 * time.Second), Latency: 200 * time.Millisecond, Succeeded: true},
		{At: now.Add(-10 * time.Second), Latency: 900 * time.Millisecond, Succeeded: false},
	} {
		if err := tracker.Record("agent-1", sample); err != nil {
			t.Fatal(err)
		}
	}
	summary, ok := tracker.Summarize("agent-1")
	if !ok || summary.Status != agentcard.HealthDegraded || summary.LatencyP50Millis != 200 || summary.LatencyP95Millis != 900 || summary.ErrorRate != 1.0/3.0 {
		t.Fatalf("unexpected health summary: %#v", summary)
	}

	old := now.Add(-2 * time.Minute)
	if err := tracker.Record("agent-2", Sample{At: old, Latency: time.Second, Succeeded: true}); err != nil {
		t.Fatal(err)
	}
	stale, ok := tracker.Summarize("agent-2")
	if !ok || !stale.Stale || stale.Status != agentcard.HealthDegraded {
		t.Fatalf("unexpected stale summary: %#v", stale)
	}
}

func TestTrackerBoundsHistoryAndRejectsInvalidSamples(t *testing.T) {
	now := time.Now().UTC()
	tracker := New(func() time.Time { return now }, time.Hour)
	if err := tracker.Record("", Sample{At: now}); err == nil {
		t.Fatal("expected target validation")
	}
	if err := tracker.Record("agent", Sample{At: now, Latency: -time.Second}); err == nil {
		t.Fatal("expected latency validation")
	}
	for i := 0; i < MaxSamplesPerTarget+10; i++ {
		if err := tracker.Record("agent", Sample{At: now.Add(time.Duration(i) * time.Second), Latency: time.Millisecond, Succeeded: true}); err != nil {
			t.Fatal(err)
		}
	}
	summary, ok := tracker.Summarize("agent")
	if !ok || summary.Samples != MaxSamplesPerTarget {
		t.Fatalf("history was not bounded: %#v", summary)
	}
}
