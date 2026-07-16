package configstore

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

// TestPostgresReserveAgainstBudgetConcurrentConnections proves the hard
// budget decision is made by PostgreSQL row locking, not by a pod-local
// counter. It intentionally races two independent transactions against a
// one-dollar budget and requires exactly one admission.
func TestPostgresReserveAgainstBudgetConcurrentConnections(t *testing.T) {
	store := setupPostgresDeadlockStore(t)
	require.NoError(t, store.DB().AutoMigrate(&tables.TableGovernanceReservation{}, &tables.TableBudget{}))
	now := time.Now().UTC()
	require.NoError(t, store.DB().Create(&tables.TableBudget{ID: "budget-concurrent", MaxLimit: 1, ResetDuration: "1h", LastReset: now}).Error)

	start := make(chan struct{})
	errs := make(chan error, 2)
	var wg sync.WaitGroup
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			_, err := store.ReserveAgainstBudget(context.Background(), BudgetReservationRequest{
				BudgetID: "budget-concurrent",
				Request: reservations.ReservationRequest{
					LogicalRequestID: reservations.LogicalRequestID("concurrent-logical"),
					AttemptID:        reservations.AttemptID("attempt-" + string(rune('1'+i))),
					AttemptEpoch:     1,
					Lane:             reservations.AccountingLaneNormal,
					Amount:           reservations.Amount{CostMicros: 600000},
					LeaseUntil:       now.Add(time.Minute),
					Now:              now,
				},
			})
			errs <- err
		}(i)
	}
	close(start)
	wg.Wait()
	close(errs)

	admitted, denied := 0, 0
	for err := range errs {
		if err == nil {
			admitted++
		} else if err == reservations.ErrOverdraftDenied {
			denied++
		} else {
			t.Fatalf("unexpected concurrent reservation error: %v", err)
		}
	}
	require.Equal(t, 1, admitted)
	require.Equal(t, 1, denied)
}
