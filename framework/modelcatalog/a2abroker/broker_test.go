package a2abroker

import (
	"context"
	"errors"
	"net/http"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

type senderFunc func(context.Context, SendRequest) (Event, error)

func (f senderFunc) Send(ctx context.Context, request SendRequest) (Event, error) {
	return f(ctx, request)
}

func TestBrokerDispatchWithCredentialsScopesHeadersToDeclaredDestination(t *testing.T) {
	broker := New(time.Now, func() string { return "task-credentials" }, RetryPolicy{})
	task, err := broker.Submit("https://agent.example/a2a", "sha256:card", []byte("payload"))
	if err != nil {
		t.Fatal(err)
	}
	card := &a2adiscovery.AgentCard{
		SecuritySchemes: map[string]a2adiscovery.SecurityScheme{
			"bearer": {Type: "http", Scheme: "bearer"},
		},
		Security: []map[string][]string{{"bearer": {"a2a:invoke"}}},
	}
	var got http.Header
	completed, err := broker.DispatchWithCredentials(context.Background(), task.ID, []byte("payload"), senderFunc(func(_ context.Context, request SendRequest) (Event, error) {
		got = request.Headers
		return Event{State: StateCompleted}, nil
	}), card, CredentialRequest{TenantID: "tenant-a", Scopes: []string{"a2a:invoke"}}, CredentialPolicy{AllowedHosts: []string{"agent.example"}, AllowedKinds: []CredentialKind{CredentialBearer}}, CredentialResolverFunc(func(context.Context, CredentialRequest) (Credential, error) {
		return Credential{Headers: http.Header{"Authorization": []string{"Bearer opaque"}}}, nil
	}))
	if err != nil {
		t.Fatal(err)
	}
	if completed.State != StateCompleted || got.Get("Authorization") != "Bearer opaque" {
		t.Fatalf("credential was not scoped to the send: task=%#v headers=%#v", completed, got)
	}
	got.Set("Authorization", "mutated")
	if task.State != StateSubmitted {
		t.Fatal("submit result was mutated by dispatch")
	}
}

func TestBrokerCredentialRequiredBecomesAuthRequiredWithoutSecret(t *testing.T) {
	broker := New(time.Now, func() string { return "task-auth" }, RetryPolicy{})
	task, err := broker.Submit("https://agent.example/a2a", "digest", nil)
	if err != nil {
		t.Fatal(err)
	}
	card := &a2adiscovery.AgentCard{SecuritySchemes: map[string]a2adiscovery.SecurityScheme{"oauth": {Type: "oauth2"}}}
	waiting, err := broker.DispatchWithCredentials(context.Background(), task.ID, nil, senderFunc(func(context.Context, SendRequest) (Event, error) {
		t.Fatal("sender must not run while authorization is required")
		return Event{}, nil
	}), card, CredentialRequest{TenantID: "tenant-a"}, CredentialPolicy{AllowedHosts: []string{"agent.example"}}, CredentialResolverFunc(func(context.Context, CredentialRequest) (Credential, error) {
		return Credential{}, ErrCredentialRequired
	}))
	if err != nil {
		t.Fatal(err)
	}
	if waiting.State != StateAuthRequired || waiting.Error != "authentication required" {
		t.Fatalf("unexpected auth-required task: %#v", waiting)
	}
}

func TestResolveCredentialRejectsAmbientAndUnsafeHeaders(t *testing.T) {
	card := &a2adiscovery.AgentCard{SecuritySchemes: map[string]a2adiscovery.SecurityScheme{"key": {Type: "apiKey", Name: "X-API-Key", In: "header"}}}
	_, err := ResolveCredential(context.Background(), CredentialRequest{Endpoint: "https://agent.example/a2a"}, card, CredentialPolicy{AllowedHosts: []string{"agent.example"}, AllowedKinds: []CredentialKind{CredentialAPIKey}}, CredentialResolverFunc(func(context.Context, CredentialRequest) (Credential, error) {
		return Credential{Headers: http.Header{"X-API-Key": []string{"key"}, "Cookie": []string{"ambient"}}}, nil
	}))
	if err == nil {
		t.Fatal("unsafe cookie header was accepted")
	}
	if _, err := ResolveCredential(context.Background(), CredentialRequest{Endpoint: "http://agent.example/a2a"}, card, CredentialPolicy{AllowedHosts: []string{"agent.example"}}, CredentialResolverFunc(func(context.Context, CredentialRequest) (Credential, error) {
		return Credential{}, nil
	})); err == nil {
		t.Fatal("plaintext credential endpoint was accepted")
	}
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

func TestBrokerTaskObserverReceivesSafeLifecycleMetadata(t *testing.T) {
	broker := New(nil, func() string { return "task-observed" }, RetryPolicy{})
	var observed []Event
	var observedTask Task
	broker.SetTaskObserver(TaskObserverFunc(func(task Task, event Event) {
		observedTask = task
		observed = append(observed, event)
	}))
	task, err := broker.SubmitWithTrace("https://agent.example/a2a", "card-digest", []byte("secret payload"), "trace-123")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Apply(task.ID, Event{State: StateWorking}); err != nil {
		t.Fatal(err)
	}
	if observedTask.TraceID != "trace-123" || len(observed) != 1 || observed[0].State != StateWorking {
		t.Fatalf("observer received task=%#v events=%#v", observedTask, observed)
	}
	if len(observedTask.Events) != 1 || observedTask.Events[0].Message != "" {
		t.Fatalf("observer task history unexpectedly changed: %#v", observedTask.Events)
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
