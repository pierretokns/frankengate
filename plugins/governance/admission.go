package governance

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync/atomic"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
)

// AdmissionRequest is the metadata available before a provider call. Cost and
// token usage are deliberately absent: the coordinator owns any conservative
// reservation estimate and may reject when it cannot make one safely.
type AdmissionRequest struct {
	Evaluation EvaluationRequest
	Result     *EvaluationResult
	// Request is the original request envelope. Estimators may use its bounded
	// request metadata (for example max output tokens) without retaining the
	// response or placing stream-sized data in context.
	Request     *schemas.BifrostRequest
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

// OverdraftEvent is emitted after a request exceeds its reservation. The
// notifier is intentionally transport-agnostic: deployments can adapt it to
// SNS, SQS, webhook, email, or an internal alert bus without coupling the
// request hot path to an AWS client.
type OverdraftEvent struct {
	ReservationID reservations.ReservationID
	Reserved      reservations.Amount
	Actual        reservations.Amount
	Excess        reservations.Amount
	Allowed       bool
	Reason        string
}

type OverdraftNotifier interface {
	Notify(context.Context, OverdraftEvent) error
}

// WebhookOverdraftNotifier delivers redacted overdraft events to an operator
// endpoint. It is intended to run behind AsyncOverdraftNotifier, never in the
// inference request path. Retries are bounded and only transient failures are
// retried; every request carries a stable idempotency key.
type WebhookOverdraftNotifier struct {
	URL         string
	SigningKey  []byte
	Client      *http.Client
	MaxAttempts int
	Backoff     time.Duration
}

func (n *WebhookOverdraftNotifier) Notify(ctx context.Context, event OverdraftEvent) error {
	if n == nil || n.URL == "" {
		return fmt.Errorf("overdraft webhook URL is not configured")
	}
	attempts := n.MaxAttempts
	if attempts <= 0 {
		attempts = 3
	}
	backoff := n.Backoff
	if backoff <= 0 {
		backoff = 100 * time.Millisecond
	}
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal overdraft webhook: %w", err)
	}
	idempotencyKey := string(event.ReservationID)
	if idempotencyKey == "" {
		return fmt.Errorf("overdraft webhook event has no reservation id")
	}
	client := n.Client
	if client == nil {
		client = http.DefaultClient
	}
	var last error
	for attempt := 0; attempt < attempts; attempt++ {
		req, reqErr := http.NewRequestWithContext(ctx, http.MethodPost, n.URL, bytes.NewReader(body))
		if reqErr != nil {
			return fmt.Errorf("create overdraft webhook request: %w", reqErr)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Idempotency-Key", idempotencyKey)
		if len(n.SigningKey) > 0 {
			mac := hmac.New(sha256.New, n.SigningKey)
			_, _ = mac.Write(body)
			req.Header.Set("X-FrankenGate-Signature", hex.EncodeToString(mac.Sum(nil)))
		}
		resp, doErr := client.Do(req)
		if doErr == nil {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if resp.StatusCode >= 200 && resp.StatusCode < 300 {
				return nil
			}
			last = fmt.Errorf("webhook returned HTTP %d", resp.StatusCode)
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				return last
			}
		} else {
			last = doErr
		}
		if attempt+1 < attempts {
			timer := time.NewTimer(backoff * time.Duration(1<<attempt))
			select {
			case <-ctx.Done():
				timer.Stop()
				return ctx.Err()
			case <-timer.C:
			}
		}
	}
	return fmt.Errorf("overdraft webhook delivery failed after %d attempts: %w", attempts, last)
}

// AsyncOverdraftNotifier decouples alert delivery from request settlement.
// Events are bounded; when the buffer is full, Notify returns an error so the
// caller can record the delivery failure without blocking on an external SNS
// or webhook round trip.
type AsyncOverdraftNotifier struct {
	events    chan OverdraftEvent
	done      chan struct{}
	cancel    context.CancelFunc
	delivered atomic.Uint64
	failed    atomic.Uint64
	dropped   atomic.Uint64
}

func NewAsyncOverdraftNotifier(ctx context.Context, downstream OverdraftNotifier, buffer int) *AsyncOverdraftNotifier {
	if buffer <= 0 {
		buffer = 256
	}
	workerCtx, cancel := context.WithCancel(ctx)
	n := &AsyncOverdraftNotifier{events: make(chan OverdraftEvent, buffer), done: make(chan struct{}), cancel: cancel}
	go func() {
		defer close(n.done)
		for {
			select {
			case <-workerCtx.Done():
				return
			case event := <-n.events:
				if downstream == nil {
					n.failed.Add(1)
					continue
				}
				if err := downstream.Notify(workerCtx, event); err != nil {
					n.failed.Add(1)
				} else {
					n.delivered.Add(1)
				}
			}
		}
	}()
	return n
}

func (n *AsyncOverdraftNotifier) Notify(_ context.Context, event OverdraftEvent) error {
	if n == nil {
		return fmt.Errorf("overdraft notifier is nil")
	}
	select {
	case n.events <- event:
		return nil
	default:
		n.dropped.Add(1)
		return fmt.Errorf("overdraft notification queue is full")
	}
}

func (n *AsyncOverdraftNotifier) Delivered() uint64 { return n.delivered.Load() }
func (n *AsyncOverdraftNotifier) Failed() uint64    { return n.failed.Load() }
func (n *AsyncOverdraftNotifier) Dropped() uint64   { return n.dropped.Load() }

func (n *AsyncOverdraftNotifier) Close() {
	if n != nil {
		n.cancel()
		<-n.done
	}
}

// ConfiguredReservationEstimator provides a deterministic, conservative
// reservation for deployments that do not have a provider-specific preflight
// tokenizer. It reserves a configured token ceiling and per-token cost, then
// settles to observed usage when the response exposes it. The ceiling is
// intentionally explicit so enterprise deployments cannot silently run with
// guessed zero-cost admission.
type ConfiguredReservationEstimator struct {
	MaxTokens          int64
	CostMicrosPerToken int64
}

func (e ConfiguredReservationEstimator) Estimate(context.Context, AdmissionRequest) (reservations.Amount, error) {
	if e.MaxTokens <= 0 || e.CostMicrosPerToken <= 0 {
		return reservations.Amount{}, fmt.Errorf("reservation max_tokens and cost_micros_per_token must be positive")
	}
	return reservations.Amount{Tokens: e.MaxTokens, CostMicros: e.MaxTokens * e.CostMicrosPerToken}, nil
}

func (e ConfiguredReservationEstimator) Actual(_ context.Context, settlement AdmissionSettlement) reservations.Amount {
	if settlement.Response != nil && settlement.Response.ChatResponse != nil && settlement.Response.ChatResponse.Usage != nil {
		u := settlement.Response.ChatResponse.Usage
		amount := reservations.Amount{Tokens: int64(u.TotalTokens)}
		if u.Cost != nil && u.Cost.TotalCost > 0 {
			amount.CostMicros = int64(u.Cost.TotalCost * 1_000_000)
		} else {
			amount.CostMicros = int64(u.TotalTokens) * e.CostMicrosPerToken
		}
		return amount
	}
	if settlement.Response != nil && settlement.Response.ResponsesResponse != nil && settlement.Response.ResponsesResponse.Usage != nil {
		u := settlement.Response.ResponsesResponse.Usage
		amount := reservations.Amount{Tokens: int64(u.TotalTokens)}
		if u.Cost != nil && u.Cost.TotalCost > 0 {
			amount.CostMicros = int64(u.Cost.TotalCost * 1_000_000)
		} else {
			amount.CostMicros = int64(u.TotalTokens) * e.CostMicrosPerToken
		}
		return amount
	}
	if settlement.Response != nil && settlement.Response.ResponsesStreamResponse != nil && settlement.Response.ResponsesStreamResponse.Response != nil && settlement.Response.ResponsesStreamResponse.Response.Usage != nil {
		u := settlement.Response.ResponsesStreamResponse.Response.Usage
		amount := reservations.Amount{Tokens: int64(u.TotalTokens)}
		if u.Cost != nil && u.Cost.TotalCost > 0 {
			amount.CostMicros = int64(u.Cost.TotalCost * 1_000_000)
		} else {
			amount.CostMicros = int64(u.TotalTokens) * e.CostMicrosPerToken
		}
		return amount
	}
	return reservations.Amount{}
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
	Now       func() time.Time // injectable clock for deterministic retry/replay tests
	Overdraft reservations.OverdraftPolicy
	Notifier  OverdraftNotifier
}

func (c *DurableReservationCoordinator) SetNotifier(notifier OverdraftNotifier) {
	if c != nil {
		c.Notifier = notifier
	}
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
		// Some governance evaluation paths retain the applicable budget rows on
		// the evaluated VK but do not populate BudgetInfo (notably VK-scoped
		// model-config budgets loaded after a config refresh). Never silently
		// downgrade durable admission to a zero-row handle in that case.
		if len(ids) == 0 && req.Result.VirtualKey != nil {
			seen := make(map[string]struct{})
			for _, b := range req.Result.VirtualKey.Budgets {
				if b.ID != "" {
					ids = append(ids, b.ID)
					seen[b.ID] = struct{}{}
				}
			}
			for _, pc := range req.Result.VirtualKey.ProviderConfigs {
				for _, b := range pc.Budgets {
					if b.ID != "" {
						if _, ok := seen[b.ID]; !ok {
							ids = append(ids, b.ID)
							seen[b.ID] = struct{}{}
						}
					}
				}
			}
		}
	}
	if len(ids) == 0 {
		return &durableReservationHandle{}, nil
	}
	now := time.Now().UTC()
	if c.Now != nil {
		now = c.Now().UTC()
	}
	lease := now.Add(c.Lease)
	if c.Lease <= 0 {
		lease = now.Add(30 * time.Second)
	}
	h := &durableReservationHandle{}
	requests := make([]configstore.BudgetReservationRequest, 0, len(ids))
	for _, id := range ids {
		requests = append(requests, configstore.BudgetReservationRequest{BudgetID: id, Request: reservations.ReservationRequest{LogicalRequestID: reservations.LogicalRequestID(req.RequestID), AttemptID: reservations.AttemptID(fmt.Sprintf("attempt-%d", req.Attempt)), AttemptEpoch: reservations.AttemptEpoch(req.Attempt + 1), Lane: reservations.AccountingLaneNormal, Amount: amount, LeaseUntil: lease, Now: now}})
	}
	if multi, ok := c.Store.(configstore.MultiBudgetReservationStore); ok {
		rows, e := multi.ReserveAgainstBudgets(ctx, requests)
		if e != nil {
			return nil, e
		}
		h.rows = append(h.rows, rows...)
		return h, nil
	}
	for _, request := range requests {
		r, e := c.Store.ReserveAgainstBudget(ctx, request)
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
		// Providers that do not expose usage must not turn a successful request
		// into a free request. Keep the conservative reservation as the settled
		// amount; callers can reconcile the exact cost later from durable logs.
		settleAmount := amount
		if settleAmount.Tokens == 0 && settleAmount.CostMicros == 0 {
			settleAmount = r.ReservedAmount
		}
		excess := reservations.Amount{}
		if settleAmount.Tokens > r.ReservedAmount.Tokens {
			excess.Tokens = settleAmount.Tokens - r.ReservedAmount.Tokens
		}
		if settleAmount.CostMicros > r.ReservedAmount.CostMicros {
			excess.CostMicros = settleAmount.CostMicros - r.ReservedAmount.CostMicros
		}
		if (excess != reservations.Amount{}) && c.Notifier != nil {
			if err := c.Notifier.Notify(ctx, OverdraftEvent{ReservationID: r.ID, Reserved: r.ReservedAmount, Actual: settleAmount, Excess: excess, Allowed: c.Overdraft.Allow, Reason: c.Overdraft.Reason}); err != nil && first == nil {
				first = fmt.Errorf("overdraft notification: %w", err)
			}
		}
		if _, err := c.Store.Settle(ctx, reservations.SettleRequest{ReservationID: r.ID, AttemptEpoch: r.AttemptEpoch, ActualAmount: settleAmount, IdempotencyKey: "settle-" + string(r.ID), Overdraft: c.Overdraft}); err != nil && first == nil {
			first = err
		}
	}
	return first
}

// Renew extends active reservation leases while a stream is still producing
// chunks. It is intentionally separate from settlement so a sweeper cannot
// reclaim a live stream between nonterminal callbacks.
func (c *DurableReservationCoordinator) Renew(ctx context.Context, handle any) error {
	h, ok := handle.(*durableReservationHandle)
	if !ok {
		return fmt.Errorf("invalid durable reservation handle")
	}
	now := time.Now().UTC()
	if c.Now != nil {
		now = c.Now().UTC()
	}
	lease := c.Lease
	if lease <= 0 {
		lease = 30 * time.Second
	}
	var first error
	for i := range h.rows {
		r, err := c.Store.Renew(ctx, reservations.RenewRequest{
			ReservationID: h.rows[i].ID,
			AttemptEpoch:  h.rows[i].AttemptEpoch,
			LeaseUntil:    now.Add(lease),
			Now:           now,
		})
		if err != nil {
			if first == nil {
				first = err
			}
			continue
		}
		h.rows[i] = r
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

// ReservationRenewer is an optional extension used by streaming hooks. Older
// coordinators remain valid and simply do not participate in lease renewal.
type ReservationRenewer interface {
	Renew(context.Context, any) error
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
