package a2abroker

import (
	"context"
	"errors"
	"testing"
	"time"
)

type senderFunc func(context.Context, SendRequest) (Event, error)

func (f senderFunc) Send(ctx context.Context, request SendRequest) (Event, error) {
	return f(ctx, request)
}

func TestBrokerDispatchesAndPreservesTaskHistory(t *testing.T) {
	now := time.Date(2026, time.August, 4, 12, 0, 0, 0, time.UTC)
	broker := New(func() time.Time { return now }, func() string { return "task-1" }, RetryPolicy{MaxAttempts: 3, BaseDelay: time.Second, MaxDelay: 3 * time.Second})
	task, err := broker.Submit("https://agent.example/a2a", "sha256:card", []byte(`{"message":"hello"}`))
	if err != nil {
		t.Fatal(err)
	}
	completed, err := broker.Dispatch(context.Background(), task.ID, []byte("payload"), senderFunc(func(_ context.Context, request SendRequest) (Event, error) {
		if request.TaskID != task.ID || string(request.Payload) != "payload" {
			t.Fatalf("unexpected request: %#v", request)
		}
		return Event{State: StateCompleted, At: now.Add(time.Second)}, nil
	}))
	if err != nil {
		t.Fatal(err)
	}
	if completed.State != StateCompleted || completed.Attempt != 1 || len(completed.Events) != 2 {
		t.Fatalf("unexpected completed task: %#v", completed)
	}
	if _, err := broker.Apply(task.ID, Event{State: StateWorking}); err == nil {
		t.Fatal("terminal task accepted a transition")
	}
}

func TestBrokerRetriesTransientTransportFailuresAndBoundsAttempts(t *testing.T) {
	broker := New(time.Now, func() string { return "task-2" }, RetryPolicy{MaxAttempts: 2, BaseDelay: 100 * time.Millisecond, MaxDelay: time.Second})
	task, err := broker.Submit("https://agent.example/a2a", "digest", nil)
	if err != nil {
		t.Fatal(err)
	}
	transportErr := errors.New("connection reset")
	failed, err := broker.Dispatch(context.Background(), task.ID, nil, senderFunc(func(context.Context, SendRequest) (Event, error) { return Event{}, transportErr }))
	if err != nil {
		t.Fatal(err)
	}
	if failed.State != StateWorking || failed.Attempt != 1 || failed.Error != transportErr.Error() {
		t.Fatalf("retryable failure should remain working: %#v", failed)
	}
	failed, err = broker.Dispatch(context.Background(), task.ID, nil, senderFunc(func(context.Context, SendRequest) (Event, error) { return Event{}, transportErr }))
	if err != nil {
		t.Fatal(err)
	}
	if failed.State != StateFailed || failed.Attempt != 2 {
		t.Fatalf("attempt limit not enforced: %#v", failed)
	}
	if got := broker.RetryDelay(5); got != time.Second {
		t.Fatalf("retry delay was not capped: %s", got)
	}
}

func TestBrokerRejectsInvalidTransitionsAndSupportsCancel(t *testing.T) {
	broker := New(time.Now, func() string { return "task-3" }, RetryPolicy{})
	task, err := broker.Submit("endpoint", "digest", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Apply(task.ID, Event{State: StateCompleted}); err == nil {
		t.Fatal("submitted task skipped working state")
	}
	canceled, err := broker.Cancel(task.ID, "operator requested stop")
	if err != nil {
		t.Fatal(err)
	}
	if canceled.State != StateCanceled || canceled.Error != "operator requested stop" {
		t.Fatalf("unexpected canceled task: %#v", canceled)
	}
}
