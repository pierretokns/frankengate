package routing

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

func TestRunShadowPrimaryIsolatedFromShadowFailure(t *testing.T) {
	wantErr := errors.New("shadow failed")
	result := RunShadow(context.Background(), time.Second,
		func(context.Context) (string, error) { return "primary", nil },
		func(context.Context) (string, error) { return "", wantErr },
		func(string, string) bool { t.Fatal("comparison must not run after shadow failure"); return false },
	)
	if result.Primary != "primary" || result.PrimaryErr != nil {
		t.Fatalf("primary result changed: %#v", result)
	}
	if !result.ShadowRan || !errors.Is(result.ShadowErr, wantErr) || result.Compared {
		t.Fatalf("unexpected shadow result: %#v", result)
	}
}

func TestRunShadowAsyncReturnsPrimaryBeforeShadowCompletes(t *testing.T) {
	started := make(chan struct{})
	release := make(chan struct{})
	observed := make(chan ShadowResult[string], 1)
	start := time.Now()
	got, err := RunShadowAsync(context.Background(), "user-1", ShadowConfig{
		Enabled: true, Experiment: "model-v2", RolloutBasisPoints: 10000, Timeout: time.Second,
	}, func(context.Context) (string, error) { return "primary", nil }, func(context.Context) (string, error) {
		close(started)
		<-release
		return "shadow", nil
	}, func(a, b string) bool { return a == b }, func(_ Assignment, result ShadowResult[string]) { observed <- result })
	if err != nil || got != "primary" {
		t.Fatalf("primary result = %q, %v", got, err)
	}
	if elapsed := time.Since(start); elapsed > 100*time.Millisecond {
		t.Fatalf("primary was blocked by shadow for %s", elapsed)
	}
	<-started
	close(release)
	select {
	case result := <-observed:
		if !result.ShadowRan || result.Shadow != "shadow" || !result.Compared {
			t.Fatalf("unexpected shadow result: %#v", result)
		}
	case <-time.After(time.Second):
		t.Fatal("shadow observer did not run")
	}
}

func TestRunShadowAsyncSamplingAndFailureIsolation(t *testing.T) {
	var mu sync.Mutex
	observations := 0
	got, err := RunShadowAsync(context.Background(), "user-1", ShadowConfig{
		Enabled: true, Experiment: "model-v2", RolloutBasisPoints: 0, Timeout: time.Second,
	}, func(context.Context) (int, error) { return 7, nil }, func(context.Context) (int, error) {
		return 99, errors.New("must not run")
	}, nil, func(Assignment, ShadowResult[int]) { mu.Lock(); observations++; mu.Unlock() })
	if err != nil || got != 7 {
		t.Fatalf("primary changed: %d, %v", got, err)
	}
	time.Sleep(10 * time.Millisecond)
	mu.Lock()
	defer mu.Unlock()
	if observations != 0 {
		t.Fatalf("invalid rollout scheduled shadow: %d", observations)
	}
}

func TestRunShadowComparesSuccessfulResults(t *testing.T) {
	result := RunShadow(context.Background(), time.Second,
		func(context.Context) (int, error) { return 2, nil },
		func(context.Context) (int, error) { return 2, nil },
		func(primary, shadow int) bool { return primary == shadow },
	)
	if !result.Compared || !result.Equivalent || result.ShadowTimedOut {
		t.Fatalf("expected equivalent comparison: %#v", result)
	}
}

func TestRunShadowTimeoutDoesNotChangePrimary(t *testing.T) {
	result := RunShadow(context.Background(), 5*time.Millisecond,
		func(context.Context) (string, error) { return "primary", nil },
		func(ctx context.Context) (string, error) {
			<-ctx.Done()
			return "", ctx.Err()
		},
		nil,
	)
	if result.Primary != "primary" || result.PrimaryErr != nil || !result.ShadowTimedOut {
		t.Fatalf("timeout affected primary result: %#v", result)
	}
}

func TestRunShadowDisabledWithoutShadowOrTimeout(t *testing.T) {
	called := false
	result := RunShadow(context.Background(), 0,
		func(context.Context) (int, error) { return 7, nil },
		func(context.Context) (int, error) { called = true; return 0, nil },
		nil,
	)
	if called || result.ShadowRan || result.Primary != 7 {
		t.Fatalf("shadow was not disabled: %#v", result)
	}
}

func TestRunShadowNilPrimaryFailsClosed(t *testing.T) {
	called := false
	result := RunShadow(context.Background(), time.Second, nil,
		func(context.Context) (int, error) { called = true; return 1, nil }, nil)
	if called || result.ShadowRan || result.PrimaryErr != nil || result.Primary != 0 {
		t.Fatalf("nil primary should fail closed without running shadow: %#v", result)
	}
}

func TestRunShadowNormalizesNilContext(t *testing.T) {
	result := RunShadow[int](nil, 0,
		func(ctx context.Context) (int, error) {
			if ctx == nil {
				t.Fatal("primary received nil context")
			}
			return 9, nil
		}, nil, nil)
	if result.Primary != 9 || result.PrimaryErr != nil {
		t.Fatalf("unexpected normalized-context result: %#v", result)
	}
}

func TestRunShadowComparisonPanicIsIsolated(t *testing.T) {
	result := RunShadow(context.Background(), time.Second,
		func(context.Context) (int, error) { return 1, nil },
		func(context.Context) (int, error) { return 2, nil },
		func(int, int) bool { panic("comparison failure") },
	)
	if !result.Compared || result.Equivalent {
		t.Fatalf("comparison panic should be recorded as non-equivalent: %#v", result)
	}
}
