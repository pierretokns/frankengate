package reservations_test

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
)

func TestReserveReturnsExistingOnlyForExactActiveIdempotentRequest(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_000, 0).UTC()
	req := reservations.ReservationRequest{
		LogicalRequestID: "req-idempotent",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount:           reservations.Amount{Tokens: 200, CostMicros: 1234},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	}

	first, err := store.Reserve(ctx, req)
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}

	retryReq := req
	retryReq.Now = now.Add(2 * time.Minute)
	retry, err := store.Reserve(ctx, retryReq)
	if err != nil {
		t.Fatalf("idempotent reserve retry: %v", err)
	}
	if retry != first {
		t.Fatalf("idempotent retry returned %+v, want identical existing %+v", retry, first)
	}

	conflictReq := req
	conflictReq.Amount.CostMicros++
	conflictReq.Now = now.Add(20 * time.Second)
	_, err = store.Reserve(ctx, conflictReq)
	if !errors.Is(err, reservations.ErrReservationConflict) {
		t.Fatalf("conflicting reserve error = %v, want ErrReservationConflict", err)
	}

	got, err := store.Get(ctx, first.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got != first {
		t.Fatalf("conflicting reserve changed stored reservation: got %+v want %+v", got, first)
	}
}

func TestReserveNeverOverwritesFinalizedReservation(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_050, 0).UTC()

	settledReq := reservations.ReservationRequest{
		LogicalRequestID: "req-final-settled",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount:           reservations.Amount{Tokens: 100, CostMicros: 1000},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	}
	settledReservation, err := store.Reserve(ctx, settledReq)
	if err != nil {
		t.Fatalf("reserve settled case: %v", err)
	}
	settled, err := store.Settle(ctx, reservations.SettleRequest{
		ReservationID:  settledReservation.ID,
		AttemptEpoch:   settledReservation.AttemptEpoch,
		ActualAmount:   reservations.Amount{Tokens: 80, CostMicros: 800},
		IdempotencyKey: "final",
		Now:            now.Add(time.Second),
	})
	if err != nil {
		t.Fatalf("settle: %v", err)
	}
	_, err = store.Reserve(ctx, settledReq)
	if !errors.Is(err, reservations.ErrAlreadyFinalized) {
		t.Fatalf("reserve over settled error = %v, want ErrAlreadyFinalized", err)
	}
	gotSettled, err := store.Get(ctx, settled.ID)
	if err != nil {
		t.Fatalf("get settled: %v", err)
	}
	if gotSettled != settled {
		t.Fatalf("reserve over settled changed stored reservation: got %+v want %+v", gotSettled, settled)
	}

	refundedReq := reservations.ReservationRequest{
		LogicalRequestID: "req-final-refunded",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneReplay,
		Amount:           reservations.Amount{Tokens: 25, CostMicros: 250},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	}
	refundReservation, err := store.Reserve(ctx, refundedReq)
	if err != nil {
		t.Fatalf("reserve refund case: %v", err)
	}
	refunded, err := store.Refund(ctx, reservations.RefundRequest{
		ReservationID:  refundReservation.ID,
		AttemptEpoch:   refundReservation.AttemptEpoch,
		IdempotencyKey: "cancel",
		Reason:         "caller cancelled",
		Now:            now.Add(time.Second),
	})
	if err != nil {
		t.Fatalf("refund: %v", err)
	}
	conflictingFinalizedReq := refundedReq
	conflictingFinalizedReq.Amount.Tokens++
	_, err = store.Reserve(ctx, conflictingFinalizedReq)
	if !errors.Is(err, reservations.ErrAlreadyFinalized) {
		t.Fatalf("reserve over refunded error = %v, want ErrAlreadyFinalized", err)
	}
	gotRefunded, err := store.Get(ctx, refunded.ID)
	if err != nil {
		t.Fatalf("get refunded: %v", err)
	}
	if gotRefunded != refunded {
		t.Fatalf("reserve over refunded changed stored reservation: got %+v want %+v", gotRefunded, refunded)
	}
}

func TestReserveValidatesRequiredFieldsAmountsEpochAndLease(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_075, 0).UTC()
	valid := reservations.ReservationRequest{
		LogicalRequestID: "req-valid",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount:           reservations.Amount{Tokens: 1, CostMicros: 0},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	}

	tests := []struct {
		name    string
		mutate  func(*reservations.ReservationRequest)
		wantErr string
	}{
		{
			name: "missing logical request id",
			mutate: func(req *reservations.ReservationRequest) {
				req.LogicalRequestID = ""
			},
			wantErr: "logical request id",
		},
		{
			name: "missing attempt id",
			mutate: func(req *reservations.ReservationRequest) {
				req.AttemptID = ""
			},
			wantErr: "attempt id",
		},
		{
			name: "zero epoch",
			mutate: func(req *reservations.ReservationRequest) {
				req.AttemptEpoch = 0
			},
			wantErr: "attempt epoch",
		},
		{
			name: "negative tokens",
			mutate: func(req *reservations.ReservationRequest) {
				req.Amount.Tokens = -1
			},
			wantErr: "tokens",
		},
		{
			name: "negative cost",
			mutate: func(req *reservations.ReservationRequest) {
				req.Amount.CostMicros = -1
			},
			wantErr: "cost",
		},
		{
			name: "zero reservation amount",
			mutate: func(req *reservations.ReservationRequest) {
				req.Amount = reservations.Amount{}
			},
			wantErr: "positive",
		},
		{
			name: "zero lease",
			mutate: func(req *reservations.ReservationRequest) {
				req.LeaseUntil = time.Time{}
			},
			wantErr: "lease",
		},
		{
			name: "lease at now",
			mutate: func(req *reservations.ReservationRequest) {
				req.LeaseUntil = now
			},
			wantErr: "after now",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := valid
			req.LogicalRequestID = reservations.LogicalRequestID(string(valid.LogicalRequestID) + "-" + strings.ReplaceAll(tt.name, " ", "-"))
			tt.mutate(&req)

			_, err := store.Reserve(ctx, req)
			if !errors.Is(err, reservations.ErrInvalidReservation) {
				t.Fatalf("reserve error = %v, want ErrInvalidReservation", err)
			}
			if !strings.Contains(err.Error(), tt.wantErr) {
				t.Fatalf("reserve error = %q, want detail containing %q", err.Error(), tt.wantErr)
			}
		})
	}
}

func TestMutationsValidateRequiredIDsEpochsAmountsAndLease(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_080, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-mutation-validation",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount:           reservations.Amount{Tokens: 10, CostMicros: 100},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}

	tests := []struct {
		name string
		run  func() error
	}{
		{
			name: "renew missing reservation id",
			run: func() error {
				_, err := store.Renew(ctx, reservations.RenewRequest{AttemptEpoch: 1, LeaseUntil: now.Add(time.Minute), Now: now})
				return err
			},
		},
		{
			name: "renew zero epoch",
			run: func() error {
				_, err := store.Renew(ctx, reservations.RenewRequest{ReservationID: reservation.ID, LeaseUntil: now.Add(time.Minute), Now: now})
				return err
			},
		},
		{
			name: "renew lease at now",
			run: func() error {
				_, err := store.Renew(ctx, reservations.RenewRequest{ReservationID: reservation.ID, AttemptEpoch: 1, LeaseUntil: now, Now: now})
				return err
			},
		},
		{
			name: "settle missing reservation id",
			run: func() error {
				_, err := store.Settle(ctx, reservations.SettleRequest{AttemptEpoch: 1, ActualAmount: reservations.Amount{Tokens: 1}, IdempotencyKey: "missing-id", Now: now})
				return err
			},
		},
		{
			name: "settle zero epoch",
			run: func() error {
				_, err := store.Settle(ctx, reservations.SettleRequest{ReservationID: reservation.ID, ActualAmount: reservations.Amount{Tokens: 1}, IdempotencyKey: "zero-epoch", Now: now})
				return err
			},
		},
		{
			name: "settle negative actual tokens",
			run: func() error {
				_, err := store.Settle(ctx, reservations.SettleRequest{ReservationID: reservation.ID, AttemptEpoch: 1, ActualAmount: reservations.Amount{Tokens: -1}, IdempotencyKey: "negative-tokens", Now: now})
				return err
			},
		},
		{
			name: "settle negative actual cost",
			run: func() error {
				_, err := store.Settle(ctx, reservations.SettleRequest{ReservationID: reservation.ID, AttemptEpoch: 1, ActualAmount: reservations.Amount{CostMicros: -1}, IdempotencyKey: "negative-cost", Now: now})
				return err
			},
		},
		{
			name: "settle missing idempotency key",
			run: func() error {
				_, err := store.Settle(ctx, reservations.SettleRequest{ReservationID: reservation.ID, AttemptEpoch: 1, ActualAmount: reservations.Amount{Tokens: 1}, Now: now})
				return err
			},
		},
		{
			name: "refund missing reservation id",
			run: func() error {
				_, err := store.Refund(ctx, reservations.RefundRequest{AttemptEpoch: 1, IdempotencyKey: "missing-id", Now: now})
				return err
			},
		},
		{
			name: "refund zero epoch",
			run: func() error {
				_, err := store.Refund(ctx, reservations.RefundRequest{ReservationID: reservation.ID, IdempotencyKey: "zero-epoch", Now: now})
				return err
			},
		},
		{
			name: "refund missing idempotency key",
			run: func() error {
				_, err := store.Refund(ctx, reservations.RefundRequest{ReservationID: reservation.ID, AttemptEpoch: 1, Now: now})
				return err
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if err := tt.run(); !errors.Is(err, reservations.ErrInvalidReservation) {
				t.Fatalf("mutation error = %v, want ErrInvalidReservation", err)
			}
		})
	}
}

func TestStaleAttemptEpochCannotRefundRenewedReservation(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_000, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-1",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount: reservations.Amount{
			Tokens:     200,
			CostMicros: 1234,
		},
		LeaseUntil: now.Add(time.Second),
		Now:        now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}

	renewed, err := store.Renew(ctx, reservations.RenewRequest{
		ReservationID: reservation.ID,
		AttemptEpoch:  2,
		LeaseUntil:    now.Add(30 * time.Second),
		Now:           now.Add(100 * time.Millisecond),
	})
	if err != nil {
		t.Fatalf("renew: %v", err)
	}
	if renewed.AttemptEpoch != 2 {
		t.Fatalf("renewed attempt epoch = %d, want 2", renewed.AttemptEpoch)
	}

	_, err = store.Refund(ctx, reservations.RefundRequest{
		ReservationID:  reservation.ID,
		AttemptEpoch:   1,
		IdempotencyKey: "stale-attempt-cleanup",
		Reason:         "stale attempt cleanup",
		Now:            now.Add(200 * time.Millisecond),
	})
	if !errors.Is(err, reservations.ErrStaleEpoch) {
		t.Fatalf("refund error = %v, want ErrStaleEpoch", err)
	}

	got, err := store.Get(ctx, reservation.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.State != reservations.ReservationStateActive {
		t.Fatalf("state = %s, want %s", got.State, reservations.ReservationStateActive)
	}
	if got.AttemptEpoch != 2 {
		t.Fatalf("attempt epoch = %d, want 2", got.AttemptEpoch)
	}
	if got.RefundedAmount != (reservations.Amount{}) {
		t.Fatalf("refunded amount = %+v, want zero", got.RefundedAmount)
	}
}

func TestSweeperCandidateCannotRefundRenewedReservation(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_100, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-2",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount: reservations.Amount{
			Tokens:     500,
			CostMicros: 9876,
		},
		LeaseUntil: now.Add(time.Second),
		Now:        now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}

	candidates, err := store.ListExpired(ctx, reservations.SweepRequest{Now: now.Add(2 * time.Second)})
	if err != nil {
		t.Fatalf("list expired: %v", err)
	}
	if len(candidates) != 1 {
		t.Fatalf("expired candidate count = %d, want 1", len(candidates))
	}
	if candidates[0].AttemptEpoch != 1 {
		t.Fatalf("candidate epoch = %d, want 1", candidates[0].AttemptEpoch)
	}

	_, err = store.Renew(ctx, reservations.RenewRequest{
		ReservationID: reservation.ID,
		AttemptEpoch:  2,
		LeaseUntil:    now.Add(time.Minute),
		Now:           now.Add(1500 * time.Millisecond),
	})
	if err != nil {
		t.Fatalf("renew: %v", err)
	}

	result, err := store.SweepExpired(ctx, reservations.SweepRequest{
		Now:        now.Add(2 * time.Second),
		Candidates: candidates,
	})
	if err != nil {
		t.Fatalf("sweep expired: %v", err)
	}
	if result.Refunded != 0 {
		t.Fatalf("sweeper refunded %d reservations, want 0", result.Refunded)
	}
	if result.StaleEpoch != 1 {
		t.Fatalf("stale epoch count = %d, want 1", result.StaleEpoch)
	}

	got, err := store.Get(ctx, reservation.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.State != reservations.ReservationStateActive {
		t.Fatalf("state = %s, want %s", got.State, reservations.ReservationStateActive)
	}
	if got.AttemptEpoch != 2 {
		t.Fatalf("attempt epoch = %d, want 2", got.AttemptEpoch)
	}
	if got.RefundedAmount != (reservations.Amount{}) {
		t.Fatalf("refunded amount = %+v, want zero", got.RefundedAmount)
	}
}

func TestRenewCannotReviveFinalizedReservation(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_150, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-finalized",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount:           reservations.Amount{Tokens: 10, CostMicros: 100},
		LeaseUntil:       now.Add(time.Second),
		Now:              now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}
	if _, err := store.Refund(ctx, reservations.RefundRequest{
		ReservationID:  reservation.ID,
		AttemptEpoch:   1,
		IdempotencyKey: "expired-sweep",
		Reason:         "expired",
		Now:            now.Add(2 * time.Second),
	}); err != nil {
		t.Fatalf("refund: %v", err)
	}

	_, err = store.Renew(ctx, reservations.RenewRequest{
		ReservationID: reservation.ID,
		AttemptEpoch:  2,
		LeaseUntil:    now.Add(time.Minute),
		Now:           now.Add(3 * time.Second),
	})
	if !errors.Is(err, reservations.ErrAlreadyFinalized) {
		t.Fatalf("renew finalized error = %v, want ErrAlreadyFinalized", err)
	}

	got, err := store.Get(ctx, reservation.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.State != reservations.ReservationStateRefunded {
		t.Fatalf("state = %s, want %s", got.State, reservations.ReservationStateRefunded)
	}
	if got.AttemptEpoch != 1 {
		t.Fatalf("attempt epoch = %d, want original epoch 1", got.AttemptEpoch)
	}
}

func TestSettleIsFencedAndIdempotent(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_200, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-3",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount: reservations.Amount{
			Tokens:     200,
			CostMicros: 2000,
		},
		LeaseUntil: now.Add(time.Minute),
		Now:        now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}

	settleReq := reservations.SettleRequest{
		ReservationID: reservation.ID,
		AttemptEpoch:  1,
		ActualAmount: reservations.Amount{
			Tokens:     125,
			CostMicros: 1500,
		},
		IdempotencyKey: "provider-final-chunk",
		Now:            now.Add(time.Second),
	}
	settled, err := store.Settle(ctx, settleReq)
	if err != nil {
		t.Fatalf("settle: %v", err)
	}
	if settled.State != reservations.ReservationStateSettled {
		t.Fatalf("state = %s, want %s", settled.State, reservations.ReservationStateSettled)
	}
	if settled.SettledAmount != settleReq.ActualAmount {
		t.Fatalf("settled amount = %+v, want %+v", settled.SettledAmount, settleReq.ActualAmount)
	}
	if settled.RefundedAmount != (reservations.Amount{Tokens: 75, CostMicros: 500}) {
		t.Fatalf("refunded amount = %+v, want unused reservation", settled.RefundedAmount)
	}

	again, err := store.Settle(ctx, settleReq)
	if err != nil {
		t.Fatalf("settle again: %v", err)
	}
	if again != settled {
		t.Fatalf("idempotent settle changed reservation: got %+v want %+v", again, settled)
	}

	_, err = store.Settle(ctx, reservations.SettleRequest{
		ReservationID:  reservation.ID,
		AttemptEpoch:   2,
		ActualAmount:   settleReq.ActualAmount,
		IdempotencyKey: "stale-final-chunk",
		Now:            now.Add(2 * time.Second),
	})
	if !errors.Is(err, reservations.ErrStaleEpoch) {
		t.Fatalf("stale settle error = %v, want ErrStaleEpoch", err)
	}
}

func TestRefundIsFencedAndIdempotent(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_250, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-refund",
		AttemptID:        "attempt-1",
		AttemptEpoch:     3,
		Lane:             reservations.AccountingLaneReplay,
		Amount:           reservations.Amount{Tokens: 70, CostMicros: 700},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}

	refundReq := reservations.RefundRequest{
		ReservationID:  reservation.ID,
		AttemptEpoch:   3,
		IdempotencyKey: "cancel-1",
		Reason:         "caller cancelled replay",
		Now:            now.Add(time.Second),
	}
	refunded, err := store.Refund(ctx, refundReq)
	if err != nil {
		t.Fatalf("refund: %v", err)
	}
	if refunded.State != reservations.ReservationStateRefunded {
		t.Fatalf("state = %s, want %s", refunded.State, reservations.ReservationStateRefunded)
	}
	if refunded.RefundedAmount != reservation.ReservedAmount {
		t.Fatalf("refunded amount = %+v, want %+v", refunded.RefundedAmount, reservation.ReservedAmount)
	}

	again, err := store.Refund(ctx, refundReq)
	if err != nil {
		t.Fatalf("refund again: %v", err)
	}
	if again != refunded {
		t.Fatalf("idempotent refund changed reservation: got %+v want %+v", again, refunded)
	}

	_, err = store.Refund(ctx, reservations.RefundRequest{
		ReservationID:  reservation.ID,
		AttemptEpoch:   3,
		IdempotencyKey: "cancel-2",
		Reason:         "different cleanup",
		Now:            now.Add(2 * time.Second),
	})
	if !errors.Is(err, reservations.ErrAlreadyFinalized) {
		t.Fatalf("conflicting refund error = %v, want ErrAlreadyFinalized", err)
	}
}

func TestExpiryAndControlledOverdraftStatesAreTyped(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_300, 0).UTC()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-4",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount: reservations.Amount{
			Tokens:     100,
			CostMicros: 1000,
		},
		LeaseUntil: now.Add(time.Second),
		Now:        now,
	})
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}
	if reservation.ExpiryStateAt(now) != reservations.ExpiryStateLive {
		t.Fatalf("expiry state now = %s, want %s", reservation.ExpiryStateAt(now), reservations.ExpiryStateLive)
	}
	if reservation.ExpiryStateAt(now.Add(2*time.Second)) != reservations.ExpiryStateExpired {
		t.Fatalf("expiry state later = %s, want %s", reservation.ExpiryStateAt(now.Add(2*time.Second)), reservations.ExpiryStateExpired)
	}

	settled, err := store.Settle(ctx, reservations.SettleRequest{
		ReservationID: reservation.ID,
		AttemptEpoch:  1,
		ActualAmount: reservations.Amount{
			Tokens:     125,
			CostMicros: 1500,
		},
		IdempotencyKey: "provider-final-chunk",
		Overdraft: reservations.OverdraftPolicy{
			Allow:  true,
			Reason: "preapproved controlled overdraft",
		},
		Now: now.Add(3 * time.Second),
	})
	if err != nil {
		t.Fatalf("settle controlled overdraft: %v", err)
	}
	if settled.OverdraftState != reservations.OverdraftStateControlled {
		t.Fatalf("overdraft state = %s, want %s", settled.OverdraftState, reservations.OverdraftStateControlled)
	}
	if settled.OverdraftAmount != (reservations.Amount{Tokens: 25, CostMicros: 500}) {
		t.Fatalf("overdraft amount = %+v, want excess actual usage", settled.OverdraftAmount)
	}
	if settled.RefundedAmount != (reservations.Amount{}) {
		t.Fatalf("refunded amount = %+v, want zero when actual exceeds reserved", settled.RefundedAmount)
	}

	denied, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: "req-4-denied",
		AttemptID:        "attempt-1",
		AttemptEpoch:     1,
		Lane:             reservations.AccountingLaneNormal,
		Amount:           reservations.Amount{Tokens: 10, CostMicros: 100},
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	})
	if err != nil {
		t.Fatalf("reserve denied overdraft case: %v", err)
	}
	_, err = store.Settle(ctx, reservations.SettleRequest{
		ReservationID:  denied.ID,
		AttemptEpoch:   1,
		ActualAmount:   reservations.Amount{Tokens: 20, CostMicros: 150},
		IdempotencyKey: "denied-overdraft",
		Now:            now.Add(4 * time.Second),
	})
	if !errors.Is(err, reservations.ErrOverdraftDenied) {
		t.Fatalf("denied overdraft error = %v, want ErrOverdraftDenied", err)
	}
	deniedGot, err := store.Get(ctx, denied.ID)
	if err != nil {
		t.Fatalf("get denied overdraft case: %v", err)
	}
	if deniedGot.OverdraftState != reservations.OverdraftStateDenied {
		t.Fatalf("denied overdraft state = %s, want %s", deniedGot.OverdraftState, reservations.OverdraftStateDenied)
	}
	if deniedGot.State != reservations.ReservationStateActive {
		t.Fatalf("denied overdraft reservation state = %s, want %s", deniedGot.State, reservations.ReservationStateActive)
	}
}

func TestAccountingSummaryKeepsNormalShadowToolAndReplayLanesDistinct(t *testing.T) {
	ctx := context.Background()
	store := reservations.NewInMemoryStore()
	now := time.Unix(1_700_000_400, 0).UTC()

	normal := reserveForLane(t, ctx, store, reservations.AccountingLaneNormal, reservations.Amount{Tokens: 10, CostMicros: 1000}, now)
	shadow := reserveForLane(t, ctx, store, reservations.AccountingLaneShadow, reservations.Amount{Tokens: 20, CostMicros: 2000}, now)
	tool := reserveForLane(t, ctx, store, reservations.AccountingLaneTool, reservations.Amount{Tokens: 30, CostMicros: 3000}, now)
	_ = reserveForLane(t, ctx, store, reservations.AccountingLaneReplay, reservations.Amount{Tokens: 40, CostMicros: 4000}, now)

	if _, err := store.Settle(ctx, reservations.SettleRequest{
		ReservationID:  normal.ID,
		AttemptEpoch:   normal.AttemptEpoch,
		ActualAmount:   reservations.Amount{Tokens: 9, CostMicros: 900},
		IdempotencyKey: "normal-final",
		Now:            now.Add(time.Second),
	}); err != nil {
		t.Fatalf("settle normal: %v", err)
	}
	if _, err := store.Refund(ctx, reservations.RefundRequest{
		ReservationID:  shadow.ID,
		AttemptEpoch:   shadow.AttemptEpoch,
		IdempotencyKey: "shadow-cancel",
		Reason:         "shadow cleanup",
		Now:            now.Add(time.Second),
	}); err != nil {
		t.Fatalf("refund shadow: %v", err)
	}
	if _, err := store.Settle(ctx, reservations.SettleRequest{
		ReservationID:  tool.ID,
		AttemptEpoch:   tool.AttemptEpoch,
		ActualAmount:   reservations.Amount{Tokens: 5, CostMicros: 500},
		IdempotencyKey: "tool-final",
		Now:            now.Add(time.Second),
	}); err != nil {
		t.Fatalf("settle tool: %v", err)
	}

	summary, err := store.AccountingSummary(ctx)
	if err != nil {
		t.Fatalf("accounting summary: %v", err)
	}

	assertLaneTotal(t, summary.ByLane[reservations.AccountingLaneNormal], reservations.LaneTotal{
		Reserved: reservations.Amount{Tokens: 10, CostMicros: 1000},
		Settled:  reservations.Amount{Tokens: 9, CostMicros: 900},
		Refunded: reservations.Amount{Tokens: 1, CostMicros: 100},
	})
	assertLaneTotal(t, summary.ByLane[reservations.AccountingLaneShadow], reservations.LaneTotal{
		Reserved: reservations.Amount{Tokens: 20, CostMicros: 2000},
		Refunded: reservations.Amount{Tokens: 20, CostMicros: 2000},
	})
	assertLaneTotal(t, summary.ByLane[reservations.AccountingLaneTool], reservations.LaneTotal{
		Reserved: reservations.Amount{Tokens: 30, CostMicros: 3000},
		Settled:  reservations.Amount{Tokens: 5, CostMicros: 500},
		Refunded: reservations.Amount{Tokens: 25, CostMicros: 2500},
	})
	assertLaneTotal(t, summary.ByLane[reservations.AccountingLaneReplay], reservations.LaneTotal{
		Reserved:    reservations.Amount{Tokens: 40, CostMicros: 4000},
		Outstanding: reservations.Amount{Tokens: 40, CostMicros: 4000},
	})
}

func reserveForLane(t *testing.T, ctx context.Context, store *reservations.InMemoryStore, lane reservations.AccountingLane, amount reservations.Amount, now time.Time) reservations.Reservation {
	t.Helper()

	reservation, err := store.Reserve(ctx, reservations.ReservationRequest{
		LogicalRequestID: reservations.LogicalRequestID("req-lane-" + string(lane)),
		AttemptID:        reservations.AttemptID("attempt-" + string(lane)),
		AttemptEpoch:     1,
		Lane:             lane,
		Amount:           amount,
		LeaseUntil:       now.Add(time.Minute),
		Now:              now,
	})
	if err != nil {
		t.Fatalf("reserve %s: %v", lane, err)
	}
	return reservation
}

func assertLaneTotal(t *testing.T, got reservations.LaneTotal, want reservations.LaneTotal) {
	t.Helper()

	if got != want {
		t.Fatalf("lane total = %+v, want %+v", got, want)
	}
}
