package configstore

import (
	"context"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

func TestRDBReservationLifecycleIsIdempotentAndFenced(t *testing.T) {
	store := setupRDBTestStore(t)
	require.NoError(t, store.DB().AutoMigrate(&tables.TableGovernanceReservation{}))
	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Microsecond)
	req := reservations.ReservationRequest{LogicalRequestID: "logical-1", AttemptID: "attempt-1", AttemptEpoch: 3, Lane: reservations.AccountingLaneNormal, Amount: reservations.Amount{Tokens: 10, CostMicros: 100}, LeaseUntil: now.Add(time.Minute), Now: now}
	first, err := store.Reserve(ctx, req)
	require.NoError(t, err)
	retry, err := store.Reserve(ctx, req)
	require.NoError(t, err)
	require.Equal(t, first.ID, retry.ID)
	_, err = store.Renew(ctx, reservations.RenewRequest{ReservationID: first.ID, AttemptEpoch: 2, LeaseUntil: now.Add(2 * time.Minute)})
	require.ErrorIs(t, err, reservations.ErrStaleEpoch)
	settled, err := store.Settle(ctx, reservations.SettleRequest{ReservationID: first.ID, AttemptEpoch: 3, ActualAmount: reservations.Amount{Tokens: 8, CostMicros: 80}, IdempotencyKey: "settle-1", Now: now})
	require.NoError(t, err)
	require.Equal(t, int64(2), settled.RefundedAmount.Tokens)
	retrySettle, err := store.Settle(ctx, reservations.SettleRequest{ReservationID: first.ID, AttemptEpoch: 3, ActualAmount: reservations.Amount{Tokens: 8, CostMicros: 80}, IdempotencyKey: "settle-1", Now: now})
	require.NoError(t, err)
	require.Equal(t, settled.ID, retrySettle.ID)
	_, err = store.Reserve(ctx, req)
	require.ErrorIs(t, err, reservations.ErrAlreadyFinalized)
	_, err = store.Refund(ctx, reservations.RefundRequest{ReservationID: first.ID, AttemptEpoch: 3, IdempotencyKey: "refund-1", Now: now})
	require.ErrorIs(t, err, reservations.ErrAlreadyFinalized)
}

func TestRDBReserveAgainstBudgetLocksAndRejectsOverspend(t *testing.T) {
	store := setupRDBTestStore(t)
	require.NoError(t, store.DB().AutoMigrate(&tables.TableGovernanceReservation{}, &tables.TableBudget{}))
	now := time.Now().UTC()
	require.NoError(t, store.DB().Create(&tables.TableBudget{ID: "budget-1", MaxLimit: 1, ResetDuration: "1h", LastReset: now}).Error)
	base := reservations.ReservationRequest{LogicalRequestID: "logical-budget", AttemptID: "attempt-1", AttemptEpoch: 1, Lane: reservations.AccountingLaneNormal, Amount: reservations.Amount{CostMicros: 600000}, LeaseUntil: now.Add(time.Minute), Now: now}
	first, err := store.ReserveAgainstBudget(context.Background(), BudgetReservationRequest{BudgetID: "budget-1", Request: base})
	require.NoError(t, err)
	_, err = store.Settle(context.Background(), reservations.SettleRequest{ReservationID: first.ID, AttemptEpoch: 1, ActualAmount: base.Amount, IdempotencyKey: "settle-budget", Now: now})
	require.NoError(t, err)
	var budget tables.TableBudget
	require.NoError(t, store.DB().First(&budget, "id = ?", "budget-1").Error)
	require.InDelta(t, 0.6, budget.CurrentUsage, 0.000001)
	base.AttemptID = "attempt-2"
	base.Amount.CostMicros = 500001
	_, err = store.ReserveAgainstBudget(context.Background(), BudgetReservationRequest{BudgetID: "budget-1", Request: base})
	require.ErrorIs(t, err, reservations.ErrOverdraftDenied)
}
