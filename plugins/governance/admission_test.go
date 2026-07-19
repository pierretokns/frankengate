package governance

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

func TestWebhookOverdraftNotifierSignsAndRetriesTransientFailures(t *testing.T) {
	var attempts int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if got := r.Header.Get("Idempotency-Key"); got != "reservation-1" {
			t.Errorf("idempotency key = %q, want reservation-1", got)
		}
		if got := r.Header.Get("X-FrankenGate-Signature"); got == "" {
			t.Error("missing webhook signature")
		}
		if attempts == 1 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	n := &WebhookOverdraftNotifier{URL: server.URL, SigningKey: []byte("secret"), MaxAttempts: 2, Backoff: time.Millisecond}
	err := n.Notify(context.Background(), OverdraftEvent{ReservationID: "reservation-1", Excess: reservations.Amount{Tokens: 1}})
	require.NoError(t, err)
	require.Equal(t, 2, attempts)
}

func TestWebhookOverdraftNotifierDoesNotRetryClientErrors(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		attempts++
		w.WriteHeader(http.StatusBadRequest)
	}))
	defer server.Close()
	n := &WebhookOverdraftNotifier{URL: server.URL, MaxAttempts: 3, Backoff: time.Millisecond}
	err := n.Notify(context.Background(), OverdraftEvent{ReservationID: "reservation-2"})
	require.Error(t, err)
	require.Equal(t, 1, attempts)
}

type fakeSNSPublisher struct {
	topic, subject, body string
	attempts             int
	failures             int
}

func (p *fakeSNSPublisher) Publish(_ context.Context, topic, subject, body string) error {
	p.attempts++
	if p.attempts <= p.failures {
		return errors.New("transient SNS failure")
	}
	p.topic, p.subject, p.body = topic, subject, body
	return nil
}

type fakeEmailSender struct {
	from, subject, body string
	recipients          []string
}

func (s *fakeEmailSender) Send(_ context.Context, from string, recipients []string, subject, body string) error {
	s.from, s.recipients, s.subject, s.body = from, append([]string(nil), recipients...), subject, body
	return nil
}

func TestNativeOverdraftNotifiersUseInjectedAdapters(t *testing.T) {
	event := OverdraftEvent{ReservationID: "r-1", Allowed: true}
	sns := &fakeSNSPublisher{}
	if err := (&SNSOverdraftNotifier{Publisher: sns, TopicARN: "arn:aws:sns:us-east-1:1:topic"}).Notify(context.Background(), event); err != nil {
		t.Fatal(err)
	}
	if sns.topic == "" || !strings.Contains(sns.body, "r-1") {
		t.Fatalf("unexpected SNS payload: %#v", sns)
	}
	mail := &fakeEmailSender{}
	if err := (&EmailOverdraftNotifier{Sender: mail, From: "alerts@example.com", Recipients: []string{"ops@example.com"}}).Notify(context.Background(), event); err != nil {
		t.Fatal(err)
	}
	if mail.from == "" || len(mail.recipients) != 1 || !strings.Contains(mail.body, "r-1") {
		t.Fatalf("unexpected email payload: %#v", mail)
	}
}

func TestSNSOverdraftNotifierRetriesTransientFailuresWithBound(t *testing.T) {
	sns := &fakeSNSPublisher{failures: 2}
	n := &SNSOverdraftNotifier{Publisher: sns, TopicARN: "arn:aws:sns:us-east-1:1:topic", MaxAttempts: 3, Backoff: time.Millisecond}
	require.NoError(t, n.Notify(context.Background(), OverdraftEvent{ReservationID: "retry-me"}))
	require.Equal(t, 3, sns.attempts)

	sns = &fakeSNSPublisher{failures: 5}
	n.Publisher = sns
	require.Error(t, n.Notify(context.Background(), OverdraftEvent{ReservationID: "bounded"}))
	require.Equal(t, 3, sns.attempts)
}

func TestGovernanceConfigRedactsWebhookSigningKey(t *testing.T) {
	plugin := &GovernancePlugin{}
	redacted, err := plugin.RedactConfig(map[string]any{
		"reservation_webhook_url":         "https://alerts.internal/hook",
		"reservation_webhook_signing_key": "super-secret-signing-key",
	})
	require.NoError(t, err)
	b, err := json.Marshal(redacted)
	require.NoError(t, err)
	require.NotContains(t, string(b), "super-secret-signing-key")
}

type testBudgetReservationStore struct{ *reservations.InMemoryStore }

func (s testBudgetReservationStore) ReserveAgainstBudget(ctx context.Context, req configstore.BudgetReservationRequest) (reservations.Reservation, error) {
	return s.Reserve(ctx, req.Request)
}

type excessUsageEstimator struct{}

func (excessUsageEstimator) Estimate(context.Context, AdmissionRequest) (reservations.Amount, error) {
	return reservations.Amount{Tokens: 10, CostMicros: 10}, nil
}

func (excessUsageEstimator) Actual(context.Context, AdmissionSettlement) reservations.Amount {
	return reservations.Amount{Tokens: 20, CostMicros: 20}
}

type overdraftNotifier struct{ events []OverdraftEvent }

func (n *overdraftNotifier) Notify(_ context.Context, event OverdraftEvent) error {
	n.events = append(n.events, event)
	return nil
}

func TestAsyncOverdraftNotifierDoesNotBlockCaller(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	downstream := &overdraftNotifier{}
	notifier := NewAsyncOverdraftNotifier(ctx, downstream, 1)
	require.NoError(t, notifier.Notify(ctx, OverdraftEvent{Reason: "first"}))
	// A full queue may reject immediately, but must never wait on the
	// downstream transport or block the request path.
	_ = notifier.Notify(ctx, OverdraftEvent{Reason: "second"})
	notifier.Close()
	cancel()
}

func TestAsyncOverdraftNotifierCloseDrainsAcceptedEvents(t *testing.T) {
	ctx := context.Background()
	downstream := &overdraftNotifier{}
	notifier := NewAsyncOverdraftNotifier(ctx, downstream, 2)
	require.NoError(t, notifier.Notify(ctx, OverdraftEvent{ReservationID: "queued-1"}))
	require.NoError(t, notifier.Notify(ctx, OverdraftEvent{ReservationID: "queued-2"}))
	notifier.Close()
	require.Len(t, downstream.events, 2)
	require.Equal(t, uint64(2), notifier.Delivered())
	require.Error(t, notifier.Notify(ctx, OverdraftEvent{ReservationID: "after-close"}))
}

func TestAsyncOverdraftNotifierMetricObserver(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	var mu sync.Mutex
	counts := map[string]int{}
	notifier := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 2)
	notifier.SetMetricObserver(func(name string, _ float64) {
		mu.Lock()
		counts[name]++
		mu.Unlock()
	})
	require.NoError(t, notifier.Notify(ctx, OverdraftEvent{}))
	notifier.Close()
	mu.Lock()
	defer mu.Unlock()
	require.Equal(t, 1, counts["enqueued"])
	require.Equal(t, 1, counts["delivered"])
}

func TestDurableReservationCoordinatorSetNotifierClosesPreviousAsyncNotifier(t *testing.T) {
	ctx := context.Background()
	old := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 1)
	newNotifier := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 1)
	coordinator := &DurableReservationCoordinator{}
	coordinator.SetNotifier(old)
	coordinator.SetNotifier(newNotifier)
	// A reload must not leave the old worker running or accepting events.
	require.Error(t, old.Notify(ctx, OverdraftEvent{ReservationID: "stale"}))
	coordinator.Close()
	require.Error(t, newNotifier.Notify(ctx, OverdraftEvent{ReservationID: "closed"}))
}

func TestGovernancePluginReloadNotifierUsesLifecycleSafeSwap(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	first := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 1)
	second := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 1)
	coordinator := &DurableReservationCoordinator{}
	coordinator.SetNotifier(first)
	plugin := &GovernancePlugin{}
	plugin.SetReservationCoordinator(coordinator)
	if err := plugin.ReloadNotifier(second); err != nil {
		t.Fatalf("reload notifier: %v", err)
	}
	if err := first.Notify(ctx, OverdraftEvent{ReservationID: "closed"}); err == nil {
		t.Fatal("old notifier remained usable after reload")
	}
	if err := second.Notify(ctx, OverdraftEvent{ReservationID: "open"}); err != nil {
		t.Fatalf("new notifier unusable after reload: %v", err)
	}
}

func TestDurableReservationCoordinatorReappliesNotifierObserverOnReload(t *testing.T) {
	ctx := context.Background()
	coordinator := &DurableReservationCoordinator{}
	var mu sync.Mutex
	delivered := 0
	coordinator.SetNotifierMetricObserver(func(name string, _ float64) {
		if name == "delivered" {
			mu.Lock()
			delivered++
			mu.Unlock()
		}
	})
	first := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 1)
	coordinator.SetNotifier(first)
	second := NewAsyncOverdraftNotifier(ctx, &overdraftNotifier{}, 1)
	coordinator.SetNotifier(second)
	require.NoError(t, second.Notify(ctx, OverdraftEvent{}))
	coordinator.Close()
	mu.Lock()
	defer mu.Unlock()
	require.Equal(t, 1, delivered)
}

type testReservationCoordinator struct {
	reserveErr error
	reserved   int
	settled    int
	refunded   int
	renewed    int
	request    *schemas.BifrostRequest
	result     *EvaluationResult
	settlement AdmissionSettlement
}

func (c *testReservationCoordinator) Renew(context.Context, any) error {
	c.renewed++
	return nil
}

func (c *testReservationCoordinator) Reserve(_ context.Context, req AdmissionRequest) (any, error) {
	if c.reserveErr != nil {
		return nil, c.reserveErr
	}
	c.reserved++
	c.request = req.Request
	c.result = req.Result
	return "reservation-1", nil
}

func TestPreLLMHookPassesRequestEnvelopeToAdmissionEstimator(t *testing.T) {
	p := admissionTestPlugin(t)
	coordinator := &testReservationCoordinator{}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	req := admissionRequest()
	_, shortCircuit, err := p.PreLLMHook(ctx, req)
	require.NoError(t, err)
	require.Nil(t, shortCircuit)
	require.Same(t, req, coordinator.request)
}

func TestMCPHooksUseDurableAdmissionBoundary(t *testing.T) {
	p := admissionTestPlugin(t)
	coordinator := &testReservationCoordinator{}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	req := &schemas.BifrostMCPRequest{RequestType: schemas.MCPRequestTypeExecuteTool}
	_, shortCircuit, err := p.PreMCPHook(ctx, req)
	require.NoError(t, err)
	require.Nil(t, shortCircuit)
	require.Equal(t, 1, coordinator.reserved)
	require.NotNil(t, coordinator.result, "MCP admission must receive evaluated budgets")
	_, _, err = p.PostMCPHook(ctx, &schemas.BifrostMCPResponse{ExtraFields: schemas.BifrostMCPResponseExtraFields{MCPRequestType: schemas.MCPRequestTypeExecuteTool}}, nil)
	require.NoError(t, err)
	require.Equal(t, 1, coordinator.settled)
}

func TestMCPPolicyRejectionDoesNotReserve(t *testing.T) {
	vk := buildVKForMCPStamping([]string{"allowed"})
	p := newPluginForMCPStamping(t, vk, false)
	coordinator := &testReservationCoordinator{}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyVirtualKey, mcpTestVKValue)
	name := "sentry-blocked"
	req := &schemas.BifrostMCPRequest{
		RequestType: schemas.MCPRequestTypeChatToolCall,
		ChatAssistantMessageToolCall: &schemas.ChatAssistantMessageToolCall{
			Function: schemas.ChatAssistantMessageToolCallFunction{Name: &name},
		},
	}
	_, shortCircuit, err := p.PreMCPHook(ctx, req)
	require.NoError(t, err)
	require.NotNil(t, shortCircuit)
	require.Equal(t, 0, coordinator.reserved)
}

func TestConfiguredReservationEstimatorUsesCeilingAndObservedUsage(t *testing.T) {
	e := ConfiguredReservationEstimator{MaxTokens: 1000, CostMicrosPerToken: 2}
	reserved, err := e.Estimate(context.Background(), AdmissionRequest{})
	require.NoError(t, err)
	require.Equal(t, int64(1000), reserved.Tokens)
	require.Equal(t, int64(2000), reserved.CostMicros)
	response := &schemas.BifrostResponse{ChatResponse: &schemas.BifrostChatResponse{Usage: &schemas.BifrostLLMUsage{TotalTokens: 37}}}
	actual := e.Actual(context.Background(), AdmissionSettlement{Response: response})
	require.Equal(t, int64(37), actual.Tokens)
	require.Equal(t, int64(74), actual.CostMicros)
	responseUsage := &schemas.ResponsesResponseUsage{TotalTokens: 19}
	response = &schemas.BifrostResponse{ResponsesResponse: &schemas.BifrostResponsesResponse{Usage: responseUsage}}
	actual = e.Actual(context.Background(), AdmissionSettlement{Response: response})
	require.Equal(t, int64(19), actual.Tokens)
	require.Equal(t, int64(38), actual.CostMicros)
}

func TestDurableReservationCoordinatorRenewsAllBudgetLeases(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	now := time.Date(2026, 7, 16, 12, 0, 0, 0, time.UTC)
	coordinator := &DurableReservationCoordinator{
		Store:     store,
		Estimator: ConfiguredReservationEstimator{MaxTokens: 10, CostMicrosPerToken: 2},
		Lease:     time.Minute,
		Now:       func() time.Time { return now },
	}
	result := &EvaluationResult{BudgetInfo: []*configstoreTables.TableBudget{{ID: "renew-budget"}}}
	handle, err := coordinator.Reserve(context.Background(), AdmissionRequest{Result: result, RequestID: "renew-request"})
	require.NoError(t, err)
	require.NoError(t, coordinator.Renew(context.Background(), handle))
	row, err := store.Get(context.Background(), handle.(*durableReservationHandle).rows[0].ID)
	require.NoError(t, err)
	require.Equal(t, now.Add(time.Minute), row.LeaseUntil)
}

func TestDurableCoordinatorSettlesReservedAmountWhenUsageMissing(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	coordinator := &DurableReservationCoordinator{Store: store, Estimator: ConfiguredReservationEstimator{MaxTokens: 100, CostMicrosPerToken: 3}}
	req := AdmissionRequest{RequestID: "missing-usage", Attempt: 0, Result: &EvaluationResult{BudgetInfo: []*configstoreTables.TableBudget{{ID: "budget-1"}}}}
	handle, err := coordinator.Reserve(context.Background(), req)
	require.NoError(t, err)
	require.NoError(t, coordinator.Settle(context.Background(), handle, AdmissionSettlement{}))
	h := handle.(*durableReservationHandle)
	got, err := store.Get(context.Background(), h.rows[0].ID)
	require.NoError(t, err)
	require.Equal(t, h.rows[0].ReservedAmount, got.SettledAmount)
}

func TestDurableCoordinatorDeduplicatesBudgetOwnersBeforeReservation(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	coordinator := &DurableReservationCoordinator{
		Store: store, Estimator: ConfiguredReservationEstimator{MaxTokens: 10, CostMicrosPerToken: 3},
	}
	// A refreshed evaluation can contain the same owner in both the flattened
	// budget list and a VK/provider budget list. One request must consume one
	// reservation per owner, never charge the same owner twice.
	result := &EvaluationResult{
		BudgetInfo: []*configstoreTables.TableBudget{{ID: "shared-owner"}, {ID: "shared-owner"}},
		VirtualKey: &configstoreTables.TableVirtualKey{
			Budgets: []configstoreTables.TableBudget{{ID: "shared-owner"}},
		},
	}
	handle, err := coordinator.Reserve(context.Background(), AdmissionRequest{RequestID: "dedupe-owner", Result: result})
	require.NoError(t, err)
	require.Len(t, handle.(*durableReservationHandle).rows, 1)
}

func TestDurableCoordinatorIsIdempotentAcrossReplicaCoordinators(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	estimator := ConfiguredReservationEstimator{MaxTokens: 100, CostMicrosPerToken: 3}
	now := time.Unix(1_700_000_000, 0).UTC()
	first := &DurableReservationCoordinator{Store: store, Estimator: estimator, Lease: time.Minute, Now: func() time.Time { return now }}
	second := &DurableReservationCoordinator{Store: store, Estimator: estimator, Lease: time.Minute, Now: func() time.Time { return now }}
	req := AdmissionRequest{RequestID: "shared-replica-request", Result: &EvaluationResult{BudgetInfo: []*configstoreTables.TableBudget{{ID: "budget-1"}}}}
	h1, err := first.Reserve(context.Background(), req)
	require.NoError(t, err)
	h2, err := second.Reserve(context.Background(), req)
	require.NoError(t, err)
	require.Equal(t, h1.(*durableReservationHandle).rows[0].ID, h2.(*durableReservationHandle).rows[0].ID)
	require.NoError(t, first.Settle(context.Background(), h1, AdmissionSettlement{}))
	require.NoError(t, second.Settle(context.Background(), h2, AdmissionSettlement{}))
}

func TestDurableCoordinatorControlledOverdraftPolicy(t *testing.T) {
	result := &EvaluationResult{BudgetInfo: []*configstoreTables.TableBudget{{ID: "budget-overdraft"}}}
	for _, tc := range []struct {
		name    string
		allow   bool
		want    reservations.OverdraftState
		wantErr error
	}{
		{name: "denied by default", allow: false, want: reservations.OverdraftStateDenied, wantErr: reservations.ErrOverdraftDenied},
		{name: "explicitly approved", allow: true, want: reservations.OverdraftStateControlled},
	} {
		t.Run(tc.name, func(t *testing.T) {
			store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
			notifier := &overdraftNotifier{}
			coordinator := &DurableReservationCoordinator{Store: store, Estimator: excessUsageEstimator{}, Notifier: notifier, Overdraft: reservations.OverdraftPolicy{Allow: tc.allow, Reason: "approved research overdraft"}}
			handle, err := coordinator.Reserve(context.Background(), AdmissionRequest{RequestID: tc.name, Result: result})
			require.NoError(t, err)
			err = coordinator.Settle(context.Background(), handle, AdmissionSettlement{})
			if tc.wantErr != nil {
				require.ErrorIs(t, err, tc.wantErr)
			} else {
				require.NoError(t, err)
			}
			row, getErr := store.Get(context.Background(), handle.(*durableReservationHandle).rows[0].ID)
			require.NoError(t, getErr)
			require.Equal(t, tc.want, row.OverdraftState)
			require.Len(t, notifier.events, 1)
			require.Equal(t, tc.allow, notifier.events[0].Allowed)
		})
	}
}

type admissionMetricsSink struct {
	reservations int
	overdrafts   int
	notifiers    []string
}

func (m *admissionMetricsSink) ReservationObserved(context.Context, string, reservations.Amount) {
	m.reservations++
}
func (m *admissionMetricsSink) OverdraftObserved(context.Context, bool, reservations.Amount) {
	m.overdrafts++
}
func (m *admissionMetricsSink) NotifierObserved(_ context.Context, outcome string) {
	m.notifiers = append(m.notifiers, outcome)
}

func TestDurableCoordinatorEmitsExporterNeutralMetrics(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	metrics := &admissionMetricsSink{}
	coordinator := &DurableReservationCoordinator{
		Store: store, Estimator: excessUsageEstimator{}, Metrics: metrics,
		Notifier: &overdraftNotifier{}, Overdraft: reservations.OverdraftPolicy{Allow: true},
	}
	handle, err := coordinator.Reserve(context.Background(), AdmissionRequest{
		RequestID: "metrics", Result: &EvaluationResult{BudgetInfo: []*configstoreTables.TableBudget{{ID: "budget-metrics"}}},
	})
	require.NoError(t, err)
	require.NoError(t, coordinator.Settle(context.Background(), handle, AdmissionSettlement{}))
	require.Equal(t, 1, metrics.reservations)
	require.Equal(t, 1, metrics.overdrafts)
	require.Equal(t, []string{"delivered"}, metrics.notifiers)
}

func TestDurableCoordinatorDoesNotCountAsyncEnqueueAsDelivered(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	metrics := &admissionMetricsSink{}
	ctx := context.Background()
	downstream := &failingOverdraftNotifier{err: errors.New("downstream unavailable")}
	async := NewAsyncOverdraftNotifier(ctx, downstream, 1)
	coordinator := &DurableReservationCoordinator{
		Store: store, Estimator: excessUsageEstimator{}, Metrics: metrics,
		Notifier: async, Overdraft: reservations.OverdraftPolicy{Allow: true},
	}
	coordinator.SetNotifierMetricObserver(func(outcome string, _ float64) {
		metrics.NotifierObserved(context.Background(), outcome)
	})
	handle, err := coordinator.Reserve(ctx, AdmissionRequest{
		RequestID: "async-metrics", Result: &EvaluationResult{BudgetInfo: []*configstoreTables.TableBudget{{ID: "budget-async-metrics"}}},
	})
	require.NoError(t, err)
	require.NoError(t, coordinator.Settle(ctx, handle, AdmissionSettlement{}))
	async.Close()
	require.Equal(t, []string{"enqueued", "failed"}, metrics.notifiers,
		"async enqueue must not be reported as delivered before downstream completion")
}

type failingOverdraftNotifier struct{ err error }

func (n *failingOverdraftNotifier) Notify(context.Context, OverdraftEvent) error { return n.err }

func (c *testReservationCoordinator) Settle(context.Context, any, AdmissionSettlement) error {
	c.settled++
	return nil
}
func (c *testReservationCoordinator) Refund(context.Context, any, AdmissionSettlement) error {
	c.refunded++
	return nil
}

func admissionTestPlugin(t *testing.T) *GovernancePlugin {
	t.Helper()
	logger := NewMockLogger()
	store, err := NewLocalGovernanceStore(context.Background(), logger, nil, &configstore.GovernanceConfig{}, nil)
	require.NoError(t, err)
	p, err := InitFromStore(context.Background(), &Config{IsVkMandatory: boolPtr(false)}, logger, store, nil, nil, nil, nil)
	require.NoError(t, err)
	return p
}

func admissionRequest() *schemas.BifrostRequest {
	return &schemas.BifrostRequest{RequestType: schemas.ChatCompletionRequest, ChatRequest: &schemas.BifrostChatRequest{Provider: schemas.OpenAI, Model: "gpt-4"}}
}

func TestPreLLMHookReservationDenialFailsClosed(t *testing.T) {
	p := admissionTestPlugin(t)
	coordinator := &testReservationCoordinator{reserveErr: errors.New("budget reservation denied")}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	_, shortCircuit, err := p.PreLLMHook(ctx, admissionRequest())
	require.NoError(t, err)
	require.NotNil(t, shortCircuit)
	require.Equal(t, "governance_reservation_denied", *shortCircuit.Error.Type)
	require.Equal(t, 0, coordinator.reserved)
}

func TestPostLLMHookReservationSettlementIsIdempotentAtPluginBoundary(t *testing.T) {
	p := admissionTestPlugin(t)
	coordinator := &testReservationCoordinator{}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	_, shortCircuit, err := p.PreLLMHook(ctx, admissionRequest())
	require.NoError(t, err)
	require.Nil(t, shortCircuit)
	require.Equal(t, 1, coordinator.reserved)
	_, _, _ = p.PostLLMHook(ctx, nil, &schemas.BifrostError{Error: &schemas.ErrorField{Message: "provider failed"}})
	_, _, _ = p.PostLLMHook(ctx, nil, &schemas.BifrostError{Error: &schemas.ErrorField{Message: "duplicate terminal hook"}})
	require.Equal(t, 1, coordinator.refunded)
}

func TestPostLLMHookStreamingReservationWaitsForTerminalChunk(t *testing.T) {
	p := admissionTestPlugin(t)
	coordinator := &testReservationCoordinator{}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	req := admissionRequest()
	req.RequestType = schemas.ChatCompletionStreamRequest
	_, shortCircuit, err := p.PreLLMHook(ctx, req)
	require.NoError(t, err)
	require.Nil(t, shortCircuit)
	chunk := &schemas.BifrostResponse{ChatResponse: &schemas.BifrostChatResponse{ExtraFields: schemas.BifrostResponseExtraFields{RequestType: schemas.ChatCompletionStreamRequest}}}
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, false)
	_, _, _ = p.PostLLMHook(ctx, chunk, nil)
	require.Equal(t, 0, coordinator.refunded)
	require.Equal(t, 1, coordinator.renewed)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)
	_, _, _ = p.PostLLMHook(ctx, chunk, nil)
	require.Equal(t, 1, coordinator.settled)
}

func TestPreLLMHookReservesEachFallbackAttempt(t *testing.T) {
	p := admissionTestPlugin(t)
	coordinator := &testReservationCoordinator{}
	p.SetReservationCoordinator(coordinator)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyRequestID, "logical-request")
	_, shortCircuit, err := p.PreLLMHook(ctx, admissionRequest())
	require.NoError(t, err)
	require.Nil(t, shortCircuit)
	ctx.SetValue(schemas.BifrostContextKeyFallbackIndex, 1)
	_, shortCircuit, err = p.PreLLMHook(ctx, admissionRequest())
	require.NoError(t, err)
	require.Nil(t, shortCircuit)
	require.Equal(t, 2, coordinator.reserved)
}
