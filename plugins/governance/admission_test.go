package governance

import (
	"context"
	"errors"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/stretchr/testify/require"
)

type testReservationCoordinator struct {
	reserveErr error
	reserved   int
	settled    int
	refunded   int
}

func (c *testReservationCoordinator) Reserve(context.Context, AdmissionRequest) (any, error) {
	if c.reserveErr != nil {
		return nil, c.reserveErr
	}
	c.reserved++
	return "reservation-1", nil
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
