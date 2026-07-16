package governance

import (
	"context"
	"fmt"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
)

// AdmissionRequest is the metadata available before a provider call. Cost and
// token usage are deliberately absent: the coordinator owns any conservative
// reservation estimate and may reject when it cannot make one safely.
type AdmissionRequest struct {
	Evaluation  EvaluationRequest
	Result      *EvaluationResult
	RequestType schemas.RequestType
	RequestID   string
	Attempt     int
}

// ReservationEstimator supplies a conservative preflight amount and the
// actual amount after the provider returns. It must never retain the response.
type ReservationEstimator interface {
	Estimate(context.Context, AdmissionRequest) (reservations.Amount, error)
	Actual(context.Context, AdmissionSettlement) reservations.Amount
}

type durableReservationHandle struct{ rows []reservations.Reservation }

// DurableReservationCoordinator adapts the Postgres reservation store to the
// hook lifecycle. It reserves every applicable budget before provider effects,
// rolls back partial admission, and settles/refunds each row idempotently.
// Pricing/token estimation is deliberately injected instead of guessed.
type DurableReservationCoordinator struct {
	Store     configstore.BudgetReservationStore
	Estimator ReservationEstimator
	Lease     time.Duration
}

func (c *DurableReservationCoordinator) Reserve(ctx context.Context, req AdmissionRequest) (any, error) {
	if c == nil || c.Store == nil || c.Estimator == nil {
		return nil, fmt.Errorf("durable admission is not configured")
	}
	amount, err := c.Estimator.Estimate(ctx, req)
	if err != nil {
		return nil, err
	}
	if amount.Tokens < 0 || amount.CostMicros < 0 {
		return nil, fmt.Errorf("negative reservation estimate")
	}
	ids := []string{}
	if req.Result != nil {
		for _, b := range req.Result.BudgetInfo {
			if b != nil && b.ID != "" {
				ids = append(ids, b.ID)
			}
		}
	}
	if len(ids) == 0 {
		return &durableReservationHandle{}, nil
	}
	now := time.Now().UTC()
	lease := now.Add(c.Lease)
	if c.Lease <= 0 {
		lease = now.Add(30 * time.Second)
	}
	h := &durableReservationHandle{}
	for _, id := range ids {
		r, e := c.Store.ReserveAgainstBudget(ctx, configstore.BudgetReservationRequest{BudgetID: id, Request: reservations.ReservationRequest{LogicalRequestID: reservations.LogicalRequestID(req.RequestID), AttemptID: reservations.AttemptID(fmt.Sprintf("attempt-%d", req.Attempt)), AttemptEpoch: reservations.AttemptEpoch(req.Attempt + 1), Lane: reservations.AccountingLaneNormal, Amount: amount, LeaseUntil: lease, Now: now}})
		if e != nil {
			for _, prior := range h.rows {
				_, _ = c.Store.Refund(ctx, reservations.RefundRequest{ReservationID: prior.ID, AttemptEpoch: prior.AttemptEpoch, IdempotencyKey: "admission-rollback-" + string(prior.ID), Reason: "partial admission rollback"})
			}
			return nil, e
		}
		h.rows = append(h.rows, r)
	}
	return h, nil
}

func (c *DurableReservationCoordinator) Settle(ctx context.Context, handle any, settlement AdmissionSettlement) error {
	h, ok := handle.(*durableReservationHandle)
	if !ok {
		return fmt.Errorf("invalid durable reservation handle")
	}
	amount := c.Estimator.Actual(ctx, settlement)
	var first error
	for _, r := range h.rows {
		if _, err := c.Store.Settle(ctx, reservations.SettleRequest{ReservationID: r.ID, AttemptEpoch: r.AttemptEpoch, ActualAmount: amount, IdempotencyKey: "settle-" + string(r.ID), Overdraft: reservations.OverdraftPolicy{}}); err != nil && first == nil {
			first = err
		}
	}
	return first
}

func (c *DurableReservationCoordinator) Refund(ctx context.Context, handle any, settlement AdmissionSettlement) error {
	h, ok := handle.(*durableReservationHandle)
	if !ok {
		return fmt.Errorf("invalid durable reservation handle")
	}
	var first error
	for _, r := range h.rows {
		if _, err := c.Store.Refund(ctx, reservations.RefundRequest{ReservationID: r.ID, AttemptEpoch: r.AttemptEpoch, IdempotencyKey: "refund-" + string(r.ID), Reason: "provider failure"}); err != nil && first == nil {
			first = err
		}
	}
	return first
}

// AdmissionSettlement gives the coordinator the authoritative post-provider
// result. It can calculate actual usage without placing response-sized data in
// BifrostContext.
type AdmissionSettlement struct {
	Response *schemas.BifrostResponse
	Error    *schemas.BifrostError
}

// ReservationCoordinator is an optional durable admission boundary. Handle is
// intentionally opaque; implementations should return a small identifier, not
// a response or token buffer.
type ReservationCoordinator interface {
	Reserve(context.Context, AdmissionRequest) (any, error)
	Settle(context.Context, any, AdmissionSettlement) error
	Refund(context.Context, any, AdmissionSettlement) error
}

type reservationContextKey struct{}

func reservationHandleFromContext(ctx *schemas.BifrostContext) (any, bool) {
	if ctx == nil {
		return nil, false
	}
	h := ctx.Value(reservationContextKey{})
	return h, h != nil
}

func setReservationHandle(ctx *schemas.BifrostContext, handle any) {
	if ctx != nil && handle != nil {
		ctx.SetValue(reservationContextKey{}, handle)
	}
}

func clearReservationHandle(ctx *schemas.BifrostContext) {
	if ctx != nil {
		ctx.SetValue(reservationContextKey{}, nil)
	}
}
