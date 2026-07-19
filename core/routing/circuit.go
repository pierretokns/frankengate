package routing

import (
	"sync"
	"time"
)

// CircuitDecision is the auditable result of a provider admission check. It
// contains no provider credentials and is safe to attach to a trace.
type CircuitDecision struct {
	Provider string `json:"provider"`
	Allowed  bool   `json:"allowed"`
	State    string `json:"state"`
	Reason   string `json:"reason"`
}

const (
	circuitClosed   = "closed"
	circuitOpen     = "open"
	circuitHalfOpen = "half_open"
)

type circuitEntry struct {
	failures      int
	state         string
	openedAt      time.Time
	probeInFlight bool
}

// ProviderCircuit is a bounded, process-local circuit gate. It is intended to
// sit immediately before provider/fallback dispatch; it never retries or
// changes request payloads. Callers must record the outcome of an admitted
// attempt with RecordSuccess or RecordFailure.
//
// The map is bounded by MaxProviders: unknown providers are rejected once the
// bound is reached rather than allowing an unbounded cardinality attack.
type ProviderCircuit struct {
	mu               sync.Mutex
	entries          map[string]*circuitEntry
	maxProviders     int
	failureThreshold int
	cooldown         time.Duration
	now              func() time.Time
}

type ProviderCircuitConfig struct {
	MaxProviders     int
	FailureThreshold int
	Cooldown         time.Duration
}

func NewProviderCircuit(cfg ProviderCircuitConfig) *ProviderCircuit {
	if cfg.MaxProviders <= 0 {
		cfg.MaxProviders = 128
	}
	if cfg.FailureThreshold <= 0 {
		cfg.FailureThreshold = 3
	}
	if cfg.Cooldown <= 0 {
		cfg.Cooldown = 10 * time.Second
	}
	return &ProviderCircuit{entries: make(map[string]*circuitEntry), maxProviders: cfg.MaxProviders, failureThreshold: cfg.FailureThreshold, cooldown: cfg.Cooldown, now: time.Now}
}

// Allow admits one request. In half-open state only one probe is admitted;
// concurrent callers receive a deterministic rejection until it completes.
func (c *ProviderCircuit) Allow(provider string) CircuitDecision {
	c.mu.Lock()
	defer c.mu.Unlock()
	if provider == "" {
		return CircuitDecision{Allowed: false, State: circuitOpen, Reason: "empty_provider"}
	}
	e := c.entries[provider]
	if e == nil {
		if len(c.entries) >= c.maxProviders {
			return CircuitDecision{Provider: provider, Allowed: false, State: circuitOpen, Reason: "provider_limit"}
		}
		e = &circuitEntry{state: circuitClosed}
		c.entries[provider] = e
	}
	if e.state == circuitOpen && c.now().Sub(e.openedAt) >= c.cooldown {
		e.state = circuitHalfOpen
		e.probeInFlight = false
	}
	if e.state == circuitOpen {
		return CircuitDecision{Provider: provider, Allowed: false, State: e.state, Reason: "cooldown"}
	}
	if e.state == circuitHalfOpen {
		if e.probeInFlight {
			return CircuitDecision{Provider: provider, Allowed: false, State: e.state, Reason: "probe_in_flight"}
		}
		e.probeInFlight = true
		return CircuitDecision{Provider: provider, Allowed: true, State: e.state, Reason: "probe"}
	}
	return CircuitDecision{Provider: provider, Allowed: true, State: e.state, Reason: "healthy"}
}

func (c *ProviderCircuit) RecordSuccess(provider string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if e := c.entries[provider]; e != nil {
		e.failures = 0
		e.state = circuitClosed
		e.probeInFlight = false
	}
}

func (c *ProviderCircuit) RecordFailure(provider string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e := c.entries[provider]
	if e == nil {
		return
	}
	e.probeInFlight = false
	e.failures++
	if e.failures >= c.failureThreshold {
		e.state = circuitOpen
		e.openedAt = c.now()
	}
}
