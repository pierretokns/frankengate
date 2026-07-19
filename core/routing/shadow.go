package routing

import (
	"context"
	"time"
)

// ShadowConfig is the explicit, fail-closed contract for sampled shadow
// execution. Shadow calls are opt-in and must be bounded by Timeout. The
// caller is responsible for supplying a side-effect-free shadow function
// (typically a cloned request with writes, billing, and tool execution
// disabled).
type ShadowConfig struct {
	Enabled            bool
	Experiment         string
	RolloutBasisPoints int
	Timeout            time.Duration
}

// ShadowResult describes a bounded comparison between the primary result and
// an optional side-effect-disabled shadow result. Shadow execution is best
// effort: primary success/error is never changed by a shadow failure, timeout,
// or comparison error.
type ShadowResult[T any] struct {
	Primary        T
	PrimaryErr     error
	Shadow         T
	ShadowErr      error
	ShadowRan      bool
	ShadowTimedOut bool
	Compared       bool
	Equivalent     bool
}

// RunShadow executes primary synchronously, then gives the shadow function a
// bounded child context. The shadow function must be side-effect-disabled and
// must honor ctx cancellation. A nil shadow or non-positive timeout disables
// shadow execution while preserving the primary result.
func RunShadow[T any](ctx context.Context, timeout time.Duration, primary func(context.Context) (T, error), shadow func(context.Context) (T, error), compare func(T, T) bool) ShadowResult[T] {
	result := ShadowResult[T]{}
	if primary == nil {
		return result
	}
	if ctx == nil {
		ctx = context.Background()
	}
	result.Primary, result.PrimaryErr = primary(ctx)
	if shadow == nil || timeout <= 0 {
		return result
	}

	result.ShadowRan = true
	shadowCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	valueCh := make(chan struct {
		value T
		err   error
	}, 1)
	go func() {
		value, err := shadow(shadowCtx)
		valueCh <- struct {
			value T
			err   error
		}{value: value, err: err}
	}()

	select {
	case outcome := <-valueCh:
		result.Shadow, result.ShadowErr = outcome.value, outcome.err
		if result.ShadowErr == nil && compare != nil {
			result.Compared = true
			result.Equivalent = safeCompare(compare, result.Primary, result.Shadow)
		}
	case <-shadowCtx.Done():
		result.ShadowErr = shadowCtx.Err()
		result.ShadowTimedOut = true
	}
	return result
}

// RunShadowAsync executes primary synchronously and schedules a sampled shadow
// comparison without adding shadow latency to the caller. The observer runs
// after the bounded shadow completes and must be non-blocking (or own its
// queue). Shadow failures are intentionally observable only through the
// callback; they can never alter the primary result.
func RunShadowAsync[T any](ctx context.Context, subject string, config ShadowConfig, primary func(context.Context) (T, error), shadow func(context.Context) (T, error), compare func(T, T) bool, observe func(Assignment, ShadowResult[T])) (T, error) {
	var zero T
	if primary == nil {
		return zero, context.Canceled
	}
	if ctx == nil {
		ctx = context.Background()
	}
	primaryValue, primaryErr := primary(ctx)
	if !config.Enabled || config.Timeout <= 0 || shadow == nil {
		return primaryValue, primaryErr
	}
	assignment := Assign(subject, config.Experiment, config.RolloutBasisPoints)
	if !assignment.InTreatment {
		return primaryValue, primaryErr
	}
	go func() {
		// The transport context is commonly canceled as soon as the response is
		// written. Preserve only its values for asynchronous evidence; the
		// explicit shadow timeout, rather than client disconnect, owns lifetime.
		shadowBase := context.WithoutCancel(ctx)
		result := RunShadow(shadowBase, config.Timeout,
			func(context.Context) (T, error) { return primaryValue, primaryErr },
			shadow, compare)
		if observe != nil {
			observe(assignment, result)
		}
	}()
	return primaryValue, primaryErr
}

func safeCompare[T any](compare func(T, T) bool, primary, shadow T) (equivalent bool) {
	defer func() {
		if recover() != nil {
			equivalent = false
		}
	}()
	return compare(primary, shadow)
}
