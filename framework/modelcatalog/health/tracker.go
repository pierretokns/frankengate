// Package health keeps bounded operational evidence separate from card
// discovery and inference. Callers can use the resulting summary for ranking
// only after capability and policy admission succeeds.
package health

import (
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

const MaxSamplesPerTarget = 256

type Sample struct {
	At        time.Time
	Latency   time.Duration
	Succeeded bool
}

type Summary struct {
	Status           agentcard.HealthStatus
	LastCheckedAt    time.Time
	LatencyP50Millis int64
	LatencyP95Millis int64
	ErrorRate        float64
	Samples          int
	Stale            bool
}

type Tracker struct {
	mu      sync.RWMutex
	now     func() time.Time
	maxAge  time.Duration
	samples map[string][]Sample
}

func New(now func() time.Time, maxAge time.Duration) *Tracker {
	if now == nil {
		now = time.Now
	}
	if maxAge <= 0 {
		maxAge = 5 * time.Minute
	}
	return &Tracker{now: now, maxAge: maxAge, samples: make(map[string][]Sample)}
}

func (t *Tracker) Record(target string, sample Sample) error {
	if t == nil {
		return fmt.Errorf("health tracker is nil")
	}
	if target == "" {
		return fmt.Errorf("health target is required")
	}
	if sample.At.IsZero() {
		return fmt.Errorf("sample timestamp is required")
	}
	if sample.Latency < 0 {
		return fmt.Errorf("sample latency must be non-negative")
	}
	t.mu.Lock()
	defer t.mu.Unlock()
	items := append(t.samples[target], Sample{At: sample.At.UTC(), Latency: sample.Latency, Succeeded: sample.Succeeded})
	if len(items) > MaxSamplesPerTarget {
		items = append([]Sample(nil), items[len(items)-MaxSamplesPerTarget:]...)
	}
	t.samples[target] = items
	return nil
}

func (t *Tracker) Summarize(target string) (Summary, bool) {
	if t == nil {
		return Summary{}, false
	}
	t.mu.RLock()
	items := append([]Sample(nil), t.samples[target]...)
	t.mu.RUnlock()
	if len(items) == 0 {
		return Summary{}, false
	}
	latencies := make([]int64, 0, len(items))
	var failures int
	var last time.Time
	for _, item := range items {
		if item.At.After(last) {
			last = item.At
		}
		if !item.Succeeded {
			failures++
		}
		latencies = append(latencies, item.Latency.Milliseconds())
	}
	sort.Slice(latencies, func(i, j int) bool { return latencies[i] < latencies[j] })
	now := t.now().UTC()
	status := agentcard.HealthHealthy
	errorRate := float64(failures) / float64(len(items))
	if errorRate >= 0.5 {
		status = agentcard.HealthDown
	} else if errorRate > 0 || now.Sub(last) > t.maxAge {
		status = agentcard.HealthDegraded
	}
	return Summary{
		Status: status, LastCheckedAt: last, LatencyP50Millis: percentile(latencies, 0.50),
		LatencyP95Millis: percentile(latencies, 0.95), ErrorRate: errorRate,
		Samples: len(items), Stale: now.Sub(last) > t.maxAge,
	}, true
}

func percentile(sorted []int64, fraction float64) int64 {
	if len(sorted) == 0 {
		return 0
	}
	index := int(math.Ceil(fraction*float64(len(sorted)))) - 1
	if index < 0 {
		index = 0
	}
	if index >= len(sorted) {
		index = len(sorted) - 1
	}
	return sorted[index]
}
