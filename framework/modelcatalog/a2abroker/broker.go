// Package a2abroker contains the protocol-neutral outbound A2A task broker.
// Network transports are injected so task state and retry policy remain
// testable and do not become part of the model inference hot path.
package a2abroker

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"
)

type State string

const (
	StateSubmitted     State = "submitted"
	StateWorking       State = "working"
	StateInputRequired State = "input_required"
	StateAuthRequired  State = "auth_required"
	StateCompleted     State = "completed"
	StateFailed        State = "failed"
	StateCanceled      State = "canceled"
	StateRejected      State = "rejected"
)

func (s State) Terminal() bool {
	return s == StateCompleted || s == StateFailed || s == StateCanceled || s == StateRejected
}

type Task struct {
	ID         string
	Endpoint   string
	CardDigest string
	TraceID    string
	State      State
	Attempt    int
	CreatedAt  time.Time
	UpdatedAt  time.Time
	Error      string
	Events     []Event
}

type Event struct {
	State     State
	Message   string
	Retryable bool
	At        time.Time
	Error     string
}

type SendRequest struct {
	TaskID     string
	Endpoint   string
	CardDigest string
	Payload    []byte
	// Headers contains only gateway-selected downstream credentials. It is
	// deliberately kept on the injected transport request, never on Task or
	// Event, so task history and observability cannot accidentally persist raw
	// tokens.
	Headers http.Header
}

type Sender interface {
	Send(context.Context, SendRequest) (Event, error)
}

// TaskObserver is an optional, non-authoritative lifecycle hook for OTel,
// metrics, and audit projections. It receives task metadata only; payloads
// and credential headers are intentionally not part of the callback.
type TaskObserver interface {
	ObserveTaskEvent(Task, Event)
}

type TaskObserverFunc func(Task, Event)

func (f TaskObserverFunc) ObserveTaskEvent(task Task, event Event) { f(task, event) }

type RetryPolicy struct {
	MaxAttempts int
	BaseDelay   time.Duration
	MaxDelay    time.Duration
}

func (p RetryPolicy) withDefaults() RetryPolicy {
	if p.MaxAttempts <= 0 {
		p.MaxAttempts = 3
	}
	if p.BaseDelay <= 0 {
		p.BaseDelay = 100 * time.Millisecond
	}
	if p.MaxDelay <= 0 {
		p.MaxDelay = 5 * time.Second
	}
	return p
}

type Broker struct {
	mu       sync.RWMutex
	now      func() time.Time
	ids      func() string
	policy   RetryPolicy
	tasks    map[string]Task
	observer TaskObserver
}

func New(now func() time.Time, ids func() string, policy RetryPolicy) *Broker {
	if now == nil {
		now = time.Now
	}
	if ids == nil {
		ids = func() string { return fmt.Sprintf("task-%d", now().UnixNano()) }
	}
	return &Broker{now: now, ids: ids, policy: policy.withDefaults(), tasks: make(map[string]Task)}
}

func (b *Broker) Submit(endpoint, cardDigest string, payload []byte) (Task, error) {
	return b.SubmitWithTrace(endpoint, cardDigest, payload, "")
}

// SubmitWithTrace binds a caller-owned trace ID to task metadata so lifecycle
// events can be correlated with the gateway's existing OTel trace. The trace
// ID is never used as a credential or endpoint selector.
func (b *Broker) SubmitWithTrace(endpoint, cardDigest string, payload []byte, traceID string) (Task, error) {
	if b == nil {
		return Task{}, fmt.Errorf("broker is nil")
	}
	if endpoint == "" || cardDigest == "" {
		return Task{}, fmt.Errorf("endpoint and card digest are required")
	}
	now := b.now().UTC()
	task := Task{ID: b.ids(), Endpoint: endpoint, CardDigest: cardDigest, TraceID: traceID, State: StateSubmitted, Attempt: 0, CreatedAt: now, UpdatedAt: now}
	if task.ID == "" {
		return Task{}, fmt.Errorf("task id generator returned empty id")
	}
	b.mu.Lock()
	if _, exists := b.tasks[task.ID]; exists {
		b.mu.Unlock()
		return Task{}, fmt.Errorf("task id %q already exists", task.ID)
	}
	b.tasks[task.ID] = task
	b.mu.Unlock()
	return cloneTask(task), nil
}

func (b *Broker) SetTaskObserver(observer TaskObserver) {
	if b == nil {
		return
	}
	b.mu.Lock()
	b.observer = observer
	b.mu.Unlock()
}

func (b *Broker) Dispatch(ctx context.Context, taskID string, payload []byte, sender Sender) (Task, error) {
	return b.dispatch(ctx, taskID, payload, sender, nil)
}

func (b *Broker) dispatch(ctx context.Context, taskID string, payload []byte, sender Sender, headers http.Header) (Task, error) {
	if sender == nil {
		return Task{}, fmt.Errorf("sender is required")
	}
	task, ok := b.Get(taskID)
	if !ok {
		return Task{}, fmt.Errorf("task %q not found", taskID)
	}
	if task.State.Terminal() {
		return Task{}, fmt.Errorf("task %q is already terminal", taskID)
	}
	if task.Attempt >= b.policy.MaxAttempts {
		return b.Apply(taskID, Event{State: StateFailed, Error: "maximum attempts exhausted", At: b.now()})
	}
	task, err := b.Apply(taskID, Event{State: StateWorking, At: b.now()})
	if err != nil {
		return Task{}, err
	}
	task.Attempt++
	b.mu.Lock()
	task.UpdatedAt = b.now().UTC()
	b.tasks[taskID] = task
	b.mu.Unlock()

	event, sendErr := sender.Send(ctx, SendRequest{TaskID: task.ID, Endpoint: task.Endpoint, CardDigest: task.CardDigest, Payload: append([]byte(nil), payload...), Headers: cloneHeaders(headers)})
	if sendErr != nil {
		if task.Attempt >= b.policy.MaxAttempts {
			return b.Apply(taskID, Event{State: StateFailed, Error: sendErr.Error(), At: b.now()})
		}
		return b.Apply(taskID, Event{State: StateWorking, Retryable: true, Error: sendErr.Error(), At: b.now()})
	}
	if event.At.IsZero() {
		event.At = b.now()
	}
	return b.Apply(taskID, event)
}

func (b *Broker) Apply(taskID string, event Event) (Task, error) {
	if b == nil {
		return Task{}, fmt.Errorf("broker is nil")
	}
	if !validState(event.State) {
		return Task{}, fmt.Errorf("invalid task state %q", event.State)
	}
	b.mu.Lock()
	task, ok := b.tasks[taskID]
	if !ok {
		b.mu.Unlock()
		return Task{}, fmt.Errorf("task %q not found", taskID)
	}
	if task.State.Terminal() {
		b.mu.Unlock()
		return Task{}, fmt.Errorf("task %q is already terminal", taskID)
	}
	if !validTransition(task.State, event.State) {
		b.mu.Unlock()
		return Task{}, fmt.Errorf("invalid task transition %q -> %q", task.State, event.State)
	}
	if event.At.IsZero() {
		event.At = b.now()
	}
	event.At = event.At.UTC()
	task.State = event.State
	task.UpdatedAt = event.At
	task.Error = event.Error
	task.Events = append(task.Events, event)
	b.tasks[taskID] = task
	result := cloneTask(task)
	observer := b.observer
	b.mu.Unlock()
	if observer != nil {
		notifyTaskObserver(observer, result, event)
	}
	return result, nil
}

func notifyTaskObserver(observer TaskObserver, task Task, event Event) {
	defer func() { _ = recover() }()
	observer.ObserveTaskEvent(task, event)
}

func (b *Broker) Cancel(taskID, reason string) (Task, error) {
	if reason == "" {
		reason = "canceled by caller"
	}
	return b.Apply(taskID, Event{State: StateCanceled, Error: reason, At: b.now()})
}

func (b *Broker) Get(taskID string) (Task, bool) {
	if b == nil {
		return Task{}, false
	}
	b.mu.RLock()
	task, ok := b.tasks[taskID]
	b.mu.RUnlock()
	if !ok {
		return Task{}, false
	}
	return cloneTask(task), true
}

func (b *Broker) RetryDelay(attempt int) time.Duration {
	if attempt <= 0 {
		return 0
	}
	delay := b.policy.BaseDelay
	for i := 1; i < attempt; i++ {
		if delay >= b.policy.MaxDelay/2 {
			return b.policy.MaxDelay
		}
		delay *= 2
	}
	if delay > b.policy.MaxDelay {
		return b.policy.MaxDelay
	}
	return delay
}

func validState(state State) bool {
	switch state {
	case StateSubmitted, StateWorking, StateInputRequired, StateAuthRequired, StateCompleted, StateFailed, StateCanceled, StateRejected:
		return true
	default:
		return false
	}
}

func validTransition(from, to State) bool {
	if to == StateCanceled {
		return !from.Terminal()
	}
	switch from {
	case StateSubmitted:
		return to == StateWorking || to == StateAuthRequired || to == StateRejected || to == StateFailed
	case StateWorking:
		return to == StateWorking || to == StateInputRequired || to == StateAuthRequired || to == StateCompleted || to == StateFailed || to == StateRejected
	case StateInputRequired:
		return to == StateWorking || to == StateFailed || to == StateRejected
	case StateAuthRequired:
		return to == StateWorking || to == StateFailed || to == StateRejected
	default:
		return false
	}
}

func cloneHeaders(headers http.Header) http.Header {
	if len(headers) == 0 {
		return nil
	}
	return headers.Clone()
}

func cloneTask(task Task) Task {
	task.Events = append([]Event(nil), task.Events...)
	return task
}
