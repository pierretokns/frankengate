package admission

import (
	"context"
	"errors"
	"reflect"
	"testing"
	"time"
)

func TestMonitorRunsEffectAfterMandatoryGuardsAllow(t *testing.T) {
	var calls []Stage

	monitor, err := NewMonitor(
		WithMandatoryGuard(StageAuthentication, func(ctx context.Context, req Request) Decision {
			calls = append(calls, StageAuthentication)
			return Allow(StageAuthentication)
		}),
		WithMandatoryGuard(StageEntitlement, func(ctx context.Context, req Request) Decision {
			calls = append(calls, StageEntitlement)
			return Allow(StageEntitlement)
		}),
		WithMandatoryGuard(StageQuotaReservation, func(ctx context.Context, req Request) Decision {
			calls = append(calls, StageQuotaReservation)
			return Allow(StageQuotaReservation)
		}),
		WithMandatoryGuard(StagePrivacyEligibility, func(ctx context.Context, req Request) Decision {
			calls = append(calls, StagePrivacyEligibility)
			return Allow(StagePrivacyEligibility)
		}),
		WithMandatoryGuard(StageInvocationAuthorization, func(ctx context.Context, req Request) Decision {
			calls = append(calls, StageInvocationAuthorization)
			return Allow(StageInvocationAuthorization)
		}),
	)
	if err != nil {
		t.Fatalf("NewMonitor() error = %v", err)
	}

	result := monitor.Admit(context.Background(), Request{ID: "req-1"}, func(ctx context.Context, req Request) error {
		calls = append(calls, Stage("effect"))
		return nil
	})

	if !result.Allowed() {
		t.Fatalf("Allowed() = false, result = %+v", result)
	}

	wantCalls := []Stage{
		StageAuthentication,
		StageEntitlement,
		StageQuotaReservation,
		StagePrivacyEligibility,
		StageInvocationAuthorization,
		Stage("effect"),
	}
	if !reflect.DeepEqual(calls, wantCalls) {
		t.Fatalf("calls = %v, want %v", calls, wantCalls)
	}
}

func TestMonitorDeniesWithoutDownstreamEffect(t *testing.T) {
	for _, deniedStage := range mandatoryStages() {
		t.Run(string(deniedStage), func(t *testing.T) {
			monitor := newTestMonitor(t, map[Stage]GuardFunc{
				deniedStage: func(ctx context.Context, req Request) Decision {
					return Deny(deniedStage, "mandatory_guard_denied")
				},
			})

			effectCalled := false
			result := monitor.Admit(context.Background(), Request{ID: "req-2"}, func(ctx context.Context, req Request) error {
				effectCalled = true
				return nil
			})

			if result.Allowed() {
				t.Fatalf("Allowed() = true, result = %+v", result)
			}
			if result.Disposition != DispositionDeny {
				t.Fatalf("Disposition = %q, want %q", result.Disposition, DispositionDeny)
			}
			if result.Stage != deniedStage {
				t.Fatalf("Stage = %q, want %q", result.Stage, deniedStage)
			}
			if result.Reason != "mandatory_guard_denied" {
				t.Fatalf("Reason = %q, want mandatory_guard_denied", result.Reason)
			}
			if effectCalled {
				t.Fatal("downstream effect executed after denial")
			}
		})
	}
}

func TestMonitorFailsClosedOnGuardPanicWithoutDownstreamEffect(t *testing.T) {
	monitor := newTestMonitor(t, map[Stage]GuardFunc{
		StageQuotaReservation: func(ctx context.Context, req Request) Decision {
			panic("quota snapshot corrupt")
		},
	})

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-3"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if result.Disposition != DispositionFault {
		t.Fatalf("Disposition = %q, want %q", result.Disposition, DispositionFault)
	}
	if result.Stage != StageQuotaReservation {
		t.Fatalf("Stage = %q, want %q", result.Stage, StageQuotaReservation)
	}
	if result.Err == nil {
		t.Fatal("Err = nil, want panic error")
	}
	if effectCalled {
		t.Fatal("downstream effect executed after guard panic")
	}
}

func TestMonitorFailsClosedWhenMandatoryGuardMissingWithoutDownstreamEffect(t *testing.T) {
	monitor, err := NewMonitor(
		WithMandatoryGuard(StageAuthentication, func(ctx context.Context, req Request) Decision {
			return Allow(StageAuthentication)
		}),
		WithMandatoryGuard(StageEntitlement, func(ctx context.Context, req Request) Decision {
			return Allow(StageEntitlement)
		}),
		WithMandatoryGuard(StageQuotaReservation, func(ctx context.Context, req Request) Decision {
			return Allow(StageQuotaReservation)
		}),
		WithMandatoryGuard(StagePrivacyEligibility, func(ctx context.Context, req Request) Decision {
			return Allow(StagePrivacyEligibility)
		}),
	)
	if err != nil {
		t.Fatalf("NewMonitor() error = %v", err)
	}

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-4"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if result.Disposition != DispositionCorrupt {
		t.Fatalf("Disposition = %q, want %q", result.Disposition, DispositionCorrupt)
	}
	if result.Stage != StageInvocationAuthorization {
		t.Fatalf("Stage = %q, want %q", result.Stage, StageInvocationAuthorization)
	}
	if result.Err == nil {
		t.Fatal("Err = nil, want missing guard error")
	}
	if effectCalled {
		t.Fatal("downstream effect executed after missing mandatory guard")
	}
}

func TestMonitorReturnsDownstreamEffectError(t *testing.T) {
	monitor := newTestMonitor(t, nil)
	providerErr := errors.New("provider write failed")

	result := monitor.Admit(context.Background(), Request{ID: "req-5"}, func(ctx context.Context, req Request) error {
		return providerErr
	})

	if result.Disposition != DispositionEffectError {
		t.Fatalf("Disposition = %q, want %q", result.Disposition, DispositionEffectError)
	}
	if !errors.Is(result.Err, providerErr) {
		t.Fatalf("Err = %v, want %v", result.Err, providerErr)
	}
}

func TestMonitorFailsClosedOnGuardTimeoutWithoutDownstreamEffect(t *testing.T) {
	monitor := newTestMonitor(t, map[Stage]GuardFunc{
		StagePrivacyEligibility: func(ctx context.Context, req Request) Decision {
			<-ctx.Done()
			time.Sleep(20 * time.Millisecond)
			return Allow(StagePrivacyEligibility)
		},
	}, WithGuardTimeout(5*time.Millisecond))

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-6"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if result.Disposition != DispositionTimeout {
		t.Fatalf("Disposition = %q, want %q", result.Disposition, DispositionTimeout)
	}
	if result.Stage != StagePrivacyEligibility {
		t.Fatalf("Stage = %q, want %q", result.Stage, StagePrivacyEligibility)
	}
	if !errors.Is(result.Err, context.DeadlineExceeded) {
		t.Fatalf("Err = %v, want context deadline exceeded", result.Err)
	}
	if effectCalled {
		t.Fatal("downstream effect executed after guard timeout")
	}
}

func TestMonitorFailsClosedOnCorruptGuardDecisionWithoutDownstreamEffect(t *testing.T) {
	monitor := newTestMonitor(t, map[Stage]GuardFunc{
		StageInvocationAuthorization: func(ctx context.Context, req Request) Decision {
			return Allow(StageAuthentication)
		},
	})

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-7"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if result.Disposition != DispositionCorrupt {
		t.Fatalf("Disposition = %q, want %q", result.Disposition, DispositionCorrupt)
	}
	if result.Stage != StageInvocationAuthorization {
		t.Fatalf("Stage = %q, want %q", result.Stage, StageInvocationAuthorization)
	}
	if result.Err == nil {
		t.Fatal("Err = nil, want corrupt decision error")
	}
	if effectCalled {
		t.Fatal("downstream effect executed after corrupt guard decision")
	}
}

func TestMonitorRecordsObserverDegradationWithoutBlockingEffect(t *testing.T) {
	monitor := newTestMonitor(t, nil,
		WithObserver("privacy-eval", func(ctx context.Context, req Request) Decision {
			panic("observer unavailable")
		}),
	)

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-8"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if !result.Allowed() {
		t.Fatalf("Allowed() = false, result = %+v", result)
	}
	if !effectCalled {
		t.Fatal("downstream effect was not executed after observer degradation")
	}
	if len(result.Degradations) != 1 {
		t.Fatalf("len(Degradations) = %d, want 1", len(result.Degradations))
	}
	degradation := result.Degradations[0]
	if degradation.Name != "privacy-eval" {
		t.Fatalf("degradation.Name = %q, want privacy-eval", degradation.Name)
	}
	if degradation.Disposition != DispositionDegraded {
		t.Fatalf("degradation.Disposition = %q, want %q", degradation.Disposition, DispositionDegraded)
	}
	if degradation.Err == nil {
		t.Fatal("degradation.Err = nil, want observer panic error")
	}
}

func TestMonitorRecordsObserverTimeoutDegradationWithoutBlockingEffect(t *testing.T) {
	monitor := newTestMonitor(t, nil,
		WithObserverTimeout(5*time.Millisecond),
		WithObserver("trace-export", func(ctx context.Context, req Request) Decision {
			<-ctx.Done()
			time.Sleep(20 * time.Millisecond)
			return Allow("")
		}),
	)

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-9"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if !result.Allowed() {
		t.Fatalf("Allowed() = false, result = %+v", result)
	}
	if !effectCalled {
		t.Fatal("downstream effect was not executed after observer timeout")
	}
	if len(result.Degradations) != 1 {
		t.Fatalf("len(Degradations) = %d, want 1", len(result.Degradations))
	}
	degradation := result.Degradations[0]
	if degradation.Name != "trace-export" {
		t.Fatalf("degradation.Name = %q, want trace-export", degradation.Name)
	}
	if degradation.Disposition != DispositionDegraded {
		t.Fatalf("degradation.Disposition = %q, want %q", degradation.Disposition, DispositionDegraded)
	}
	if !errors.Is(degradation.Err, context.DeadlineExceeded) {
		t.Fatalf("degradation.Err = %v, want context deadline exceeded", degradation.Err)
	}
}

func TestMonitorRecordsExplicitObserverDegradationWithoutBlockingEffect(t *testing.T) {
	monitor := newTestMonitor(t, nil,
		WithObserver("eval-sampler", func(ctx context.Context, req Request) Decision {
			return Degrade(StagePrivacyEligibility, "sampling_budget_exhausted")
		}),
	)

	effectCalled := false
	result := monitor.Admit(context.Background(), Request{ID: "req-10"}, func(ctx context.Context, req Request) error {
		effectCalled = true
		return nil
	})

	if !result.Allowed() {
		t.Fatalf("Allowed() = false, result = %+v", result)
	}
	if !effectCalled {
		t.Fatal("downstream effect was not executed after explicit observer degradation")
	}
	if len(result.Degradations) != 1 {
		t.Fatalf("len(Degradations) = %d, want 1", len(result.Degradations))
	}
	degradation := result.Degradations[0]
	if degradation.Stage != StagePrivacyEligibility {
		t.Fatalf("degradation.Stage = %q, want %q", degradation.Stage, StagePrivacyEligibility)
	}
	if degradation.Reason != "sampling_budget_exhausted" {
		t.Fatalf("degradation.Reason = %q, want sampling_budget_exhausted", degradation.Reason)
	}
}

func newTestMonitor(t *testing.T, overrides map[Stage]GuardFunc, options ...Option) *Monitor {
	t.Helper()

	monitorOptions := make([]Option, 0, len(mandatoryStages())+len(options))
	for _, stage := range mandatoryStages() {
		stage := stage
		fn := GuardFunc(func(ctx context.Context, req Request) Decision {
			return Allow(stage)
		})
		if override := overrides[stage]; override != nil {
			fn = override
		}
		monitorOptions = append(monitorOptions, WithMandatoryGuard(stage, fn))
	}
	monitorOptions = append(monitorOptions, options...)

	monitor, err := NewMonitor(monitorOptions...)
	if err != nil {
		t.Fatalf("NewMonitor() error = %v", err)
	}
	return monitor
}
