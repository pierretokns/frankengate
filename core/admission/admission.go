// Package admission provides a small mandatory reference-monitor membrane for
// request admission before downstream provider effects are allowed to execute.
package admission

import (
	"context"
	"fmt"
	"time"
)

// Stage is a typed admission checkpoint.
type Stage string

const (
	StageAuthentication          Stage = "authentication"
	StageEntitlement             Stage = "entitlement"
	StageQuotaReservation        Stage = "quota_reservation"
	StagePrivacyEligibility      Stage = "privacy_eligibility"
	StageInvocationAuthorization Stage = "invocation_authorization"
)

var mandatoryStageOrder = [...]Stage{
	StageAuthentication,
	StageEntitlement,
	StageQuotaReservation,
	StagePrivacyEligibility,
	StageInvocationAuthorization,
}

// Disposition is the typed outcome of a guard or observer.
type Disposition string

const (
	DispositionAllow       Disposition = "allow"
	DispositionDeny        Disposition = "deny"
	DispositionDegraded    Disposition = "degraded"
	DispositionFault       Disposition = "fault"
	DispositionCorrupt     Disposition = "corrupt"
	DispositionEffectError Disposition = "effect_error"
	DispositionTimeout     Disposition = "timeout"
)

// Request is the immutable admission subject passed through guards.
type Request struct {
	ID string
}

// Decision is a guard or observer outcome.
type Decision struct {
	Stage       Stage
	Disposition Disposition
	Reason      string
	Err         error
}

// GuardFunc implements one mandatory admission check.
type GuardFunc func(context.Context, Request) Decision

// ObserverFunc implements one best-effort observer. Observer failures never
// admit a request that mandatory guards denied, and never block an admitted
// downstream effect.
type ObserverFunc func(context.Context, Request) Decision

// EffectFunc is the downstream side effect admitted by the monitor.
type EffectFunc func(context.Context, Request) error

// Option configures a Monitor.
type Option func(*Monitor) error

// Monitor evaluates mandatory guards before invoking downstream effects.
type Monitor struct {
	guards          map[Stage]GuardFunc
	guardTimeout    time.Duration
	observerTimeout time.Duration
	observers       []observer
}

type observer struct {
	name string
	fn   ObserverFunc
}

// Allow returns an allow decision for a stage.
func Allow(stage Stage) Decision {
	return Decision{Stage: stage, Disposition: DispositionAllow}
}

// Deny returns a fail-closed decision for a mandatory stage.
func Deny(stage Stage, reason string) Decision {
	return Decision{Stage: stage, Disposition: DispositionDeny, Reason: reason}
}

// Degrade returns an explicit best-effort observer degradation decision.
func Degrade(stage Stage, reason string) Decision {
	return Decision{Stage: stage, Disposition: DispositionDegraded, Reason: reason}
}

// NewMonitor builds a configured admission monitor.
func NewMonitor(options ...Option) (*Monitor, error) {
	monitor := &Monitor{
		guards: make(map[Stage]GuardFunc, len(mandatoryStages())),
	}
	for _, option := range options {
		if option == nil {
			continue
		}
		if err := option(monitor); err != nil {
			return nil, err
		}
	}
	return monitor, nil
}

// WithMandatoryGuard installs the guard for one mandatory stage.
func WithMandatoryGuard(stage Stage, fn GuardFunc) Option {
	return func(monitor *Monitor) error {
		if !isMandatoryStage(stage) {
			return fmt.Errorf("admission: unknown mandatory stage %q", stage)
		}
		if fn == nil {
			return fmt.Errorf("admission: nil guard for stage %q", stage)
		}
		monitor.guards[stage] = fn
		return nil
	}
}

// WithGuardTimeout bounds each mandatory guard. A timed-out mandatory guard
// fails closed and the downstream effect is not invoked.
func WithGuardTimeout(timeout time.Duration) Option {
	return func(monitor *Monitor) error {
		if timeout < 0 {
			return fmt.Errorf("admission: negative guard timeout %s", timeout)
		}
		monitor.guardTimeout = timeout
		return nil
	}
}

// WithObserver installs a best-effort observer. Observer failures are reported
// as degradation records but do not block downstream effects.
func WithObserver(name string, fn ObserverFunc) Option {
	return func(monitor *Monitor) error {
		if name == "" {
			return fmt.Errorf("admission: empty observer name")
		}
		if fn == nil {
			return fmt.Errorf("admission: nil observer %q", name)
		}
		monitor.observers = append(monitor.observers, observer{name: name, fn: fn})
		return nil
	}
}

// WithObserverTimeout bounds each best-effort observer. Timed-out observers are
// recorded as degradations and do not block downstream effects.
func WithObserverTimeout(timeout time.Duration) Option {
	return func(monitor *Monitor) error {
		if timeout < 0 {
			return fmt.Errorf("admission: negative observer timeout %s", timeout)
		}
		monitor.observerTimeout = timeout
		return nil
	}
}

// Admit runs the reference monitor and invokes effect only after all mandatory
// guards allow the request.
func (monitor *Monitor) Admit(ctx context.Context, req Request, effect EffectFunc) Result {
	for _, stage := range mandatoryStages() {
		guard := monitor.guards[stage]
		decision := runGuard(ctx, req, stage, guard, monitor.guardTimeout)
		decision = validateMandatoryDecision(stage, decision)
		if decision.Disposition != DispositionAllow {
			return Result{Disposition: decision.Disposition, Stage: stage, Reason: decision.Reason, Err: decision.Err}
		}
	}
	degradations := monitor.runObservers(ctx, req)
	if effect != nil {
		if err := effect(ctx, req); err != nil {
			return Result{Disposition: DispositionEffectError, Err: err, Degradations: degradations}
		}
	}
	return Result{Disposition: DispositionAllow, Degradations: degradations}
}

// Result describes the monitor's final admission outcome.
type Result struct {
	Disposition  Disposition
	Stage        Stage
	Reason       string
	Err          error
	Degradations []ObserverDegradation
}

// ObserverDegradation records a best-effort observer failure or explicit
// degradation without preventing downstream effects.
type ObserverDegradation struct {
	Name        string
	Stage       Stage
	Disposition Disposition
	Reason      string
	Err         error
}

// Allowed reports whether all mandatory guards admitted the request.
func (result Result) Allowed() bool {
	return result.Disposition == DispositionAllow
}

func mandatoryStages() []Stage {
	return mandatoryStageOrder[:]
}

func isMandatoryStage(stage Stage) bool {
	for _, mandatoryStage := range mandatoryStages() {
		if stage == mandatoryStage {
			return true
		}
	}
	return false
}

func runGuard(ctx context.Context, req Request, stage Stage, guard GuardFunc, timeout time.Duration) Decision {
	if guard == nil {
		return Decision{
			Stage:       stage,
			Disposition: DispositionCorrupt,
			Reason:      "missing_mandatory_guard",
			Err:         fmt.Errorf("admission: missing mandatory guard %q", stage),
		}
	}

	if timeout > 0 {
		guardCtx, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()

		decisionCh := make(chan Decision, 1)
		go func() {
			decisionCh <- runGuardWithoutTimeout(guardCtx, req, stage, guard)
		}()

		select {
		case decision := <-decisionCh:
			return decision
		case <-guardCtx.Done():
			return Decision{
				Stage:       stage,
				Disposition: DispositionTimeout,
				Reason:      "guard_timeout",
				Err:         guardCtx.Err(),
			}
		}
	}

	return runGuardWithoutTimeout(ctx, req, stage, guard)
}

func runGuardWithoutTimeout(ctx context.Context, req Request, stage Stage, guard GuardFunc) (decision Decision) {
	defer func() {
		if recovered := recover(); recovered != nil {
			decision = Decision{
				Stage:       stage,
				Disposition: DispositionFault,
				Reason:      "guard_panic",
				Err:         fmt.Errorf("admission: mandatory guard %q panicked: %v", stage, recovered),
			}
		}
	}()
	return guard(ctx, req)
}

func validateMandatoryDecision(stage Stage, decision Decision) Decision {
	if decision.Stage != stage {
		return corruptDecision(stage, "guard_stage_mismatch", fmt.Errorf("admission: mandatory guard %q returned decision for stage %q", stage, decision.Stage))
	}

	switch decision.Disposition {
	case DispositionAllow, DispositionDeny, DispositionFault, DispositionTimeout, DispositionCorrupt:
		return decision
	default:
		return corruptDecision(stage, "guard_unknown_disposition", fmt.Errorf("admission: mandatory guard %q returned unknown disposition %q", stage, decision.Disposition))
	}
}

func corruptDecision(stage Stage, reason string, err error) Decision {
	return Decision{
		Stage:       stage,
		Disposition: DispositionCorrupt,
		Reason:      reason,
		Err:         err,
	}
}

func (monitor *Monitor) runObservers(ctx context.Context, req Request) []ObserverDegradation {
	if len(monitor.observers) == 0 {
		return nil
	}

	degradations := make([]ObserverDegradation, 0, len(monitor.observers))
	for _, observer := range monitor.observers {
		decision := runObserver(ctx, req, observer, monitor.observerTimeout)
		switch decision.Disposition {
		case DispositionAllow:
			continue
		case DispositionDegraded:
			degradations = append(degradations, ObserverDegradation{
				Name:        observer.name,
				Stage:       decision.Stage,
				Disposition: DispositionDegraded,
				Reason:      decision.Reason,
				Err:         decision.Err,
			})
		default:
			degradations = append(degradations, ObserverDegradation{
				Name:        observer.name,
				Stage:       decision.Stage,
				Disposition: DispositionDegraded,
				Reason:      "observer_corrupt_decision",
				Err:         fmt.Errorf("admission: observer %q returned non-best-effort disposition %q", observer.name, decision.Disposition),
			})
		}
	}
	return degradations
}

func runObserver(ctx context.Context, req Request, observer observer, timeout time.Duration) Decision {
	if timeout > 0 {
		observerCtx, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()

		decisionCh := make(chan Decision, 1)
		go func() {
			decisionCh <- runObserverWithoutTimeout(observerCtx, req, observer)
		}()

		select {
		case decision := <-decisionCh:
			return decision
		case <-observerCtx.Done():
			return Decision{
				Disposition: DispositionDegraded,
				Reason:      "observer_timeout",
				Err:         observerCtx.Err(),
			}
		}
	}

	return runObserverWithoutTimeout(ctx, req, observer)
}

func runObserverWithoutTimeout(ctx context.Context, req Request, observer observer) (decision Decision) {
	defer func() {
		if recovered := recover(); recovered != nil {
			decision = Decision{
				Disposition: DispositionDegraded,
				Reason:      "observer_panic",
				Err:         fmt.Errorf("admission: observer %q panicked: %v", observer.name, recovered),
			}
		}
	}()
	return observer.fn(ctx, req)
}
