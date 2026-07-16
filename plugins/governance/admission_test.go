package governance

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

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
	// The notifier is buffered and accepts a second event without waiting for
	// the downstream transport; delivery is eventually observed by the worker.
	require.NoError(t, notifier.Notify(ctx, OverdraftEvent{Reason: "second"}))
	cancel()
	notifier.Close()
}

type testReservationCoordinator struct {
	reserveErr error
	reserved   int
	settled    int
	refunded   int
	request    *schemas.BifrostRequest
	settlement AdmissionSettlement
}

func (c *testReservationCoordinator) Reserve(_ context.Context, req AdmissionRequest) (any, error) {
	if c.reserveErr != nil {
		return nil, c.reserveErr
	}
	c.reserved++
	c.request = req.Request
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
