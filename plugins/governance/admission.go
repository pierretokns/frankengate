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
	"sync"
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

// SNSPublisher is the narrow AWS adapter boundary. The governance package
// does not construct AWS clients, preserving cheap tests and allowing the
// transport to inject an SDK v2 publisher, local emulator, or policy wrapper.
type SNSPublisher interface {
	Publish(context.Context, string, string, string) error // topic ARN, subject, body
}

type EmailSender interface {
	Send(context.Context, string, []string, string, string) error // from, recipients, subject, body
}

// SNSOverdraftNotifier adapts an injected publisher to the asynchronous
// OverdraftNotifier contract. It validates configuration and serializes a
// stable JSON event; delivery is still expected to run behind the bounded
// AsyncOverdraftNotifier.
type SNSOverdraftNotifier struct {
	Publisher SNSPublisher
	TopicARN  string
	Subject   string
}

func (n *SNSOverdraftNotifier) Notify(ctx context.Context, event OverdraftEvent) error {
	if n == nil || n.Publisher == nil || n.TopicARN == "" {
		return fmt.Errorf("SNS notifier is not configured")
	}
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal SNS overdraft event: %w", err)
	}
	subject := n.Subject
	if subject == "" {
		subject = "FrankenGate overdraft alert"
	}
	return n.Publisher.Publish(ctx, n.TopicARN, subject, string(body))
}

// EmailOverdraftNotifier adapts an injected mail sender. Recipient lists are
// copied at construction/use boundaries by the caller and never sourced from
// request data, preventing accidental per-request fanout or label leakage.
type EmailOverdraftNotifier struct {
	Sender     EmailSender
	From       string
	Recipients []string
	Subject    string
}

func (n *EmailOverdraftNotifier) Notify(ctx context.Context, event OverdraftEvent) error {
	if n == nil || n.Sender == nil || n.From == "" || len(n.Recipients) == 0 {
		return fmt.Errorf("email notifier is not configured")
	}
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal email overdraft event: %w", err)
	}
	subject := n.Subject
	if subject == "" {
		subject = "FrankenGate overdraft alert"
	}
	return n.Sender.Send(ctx, n.From, append([]string(nil), n.Recipients...), subject, string(body))
}

// MetricsSink is an optional, exporter-neutral governance metrics contract.
// Implementations must be non-blocking and keep label cardinality bounded;
// governance never imports Prometheus or OpenTelemetry directly.
type MetricsSink interface {
	ReservationObserved(context.Context, string, reservations.Amount)
	OverdraftObserved(context.Context, bool, reservations.Amount)
	NotifierObserved(context.Context, string)
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
	mu        sync.Mutex
	closed    bool
	delivered atomic.Uint64
	failed    atomic.Uint64
	dropped   atomic.Uint64
	observer  func(string, float64)
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
			case event, ok := <-n.events:
				if !ok {
					return
				}
				if downstream == nil {
					n.failed.Add(1)
					n.observe("failed", 1)
					continue
				}
				if err := downstream.Notify(workerCtx, event); err != nil {
					n.failed.Add(1)
					n.observe("failed", 1)
				} else {
					n.delivered.Add(1)
					n.observe("delivered", 1)
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
	n.mu.Lock()
	if n.closed {
		n.mu.Unlock()
		return fmt.Errorf("overdraft notifier is closed")
	}
	select {
	case n.events <- event:
		n.mu.Unlock()
		n.observe("enqueued", 1)
		return nil
	default:
		n.mu.Unlock()
		n.dropped.Add(1)
		n.observe("dropped", 1)
		return fmt.Errorf("overdraft notification queue is full")
	}
}

// SetMetricObserver installs a low-cardinality notification observer. The
// callback is invoked outside the notifier's mutex and never runs on the
// inference request path for delivery outcomes; nil disables observation.
func (n *AsyncOverdraftNotifier) SetMetricObserver(observer func(name string, value float64)) {
	if n == nil {
		return
	}
	n.mu.Lock()
	n.observer = observer
	n.mu.Unlock()
}

func (n *AsyncOverdraftNotifier) observe(name string, value float64) {
	n.mu.Lock()
	observer := n.observer
	n.mu.Unlock()
	if observer != nil {
		observer(name, value)
	}
}

func (n *AsyncOverdraftNotifier) Delivered() uint64 { return n.delivered.Load() }
func (n *AsyncOverdraftNotifier) Failed() uint64    { return n.failed.Load() }
func (n *AsyncOverdraftNotifier) Dropped() uint64   { return n.dropped.Load() }

func (n *AsyncOverdraftNotifier) Close() {
	if n != nil {
		n.mu.Lock()
		if n.closed {
			n.mu.Unlock()
			return
		}
		n.closed = true
		close(n.events)
		n.mu.Unlock()
		// Closing the queue drains already accepted events before returning. This
		// preserves alerts during orderly pod shutdown without adding provider
		// latency to the inference path.
		<-n.done
		n.cancel()
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
	Store            configstore.BudgetReservationStore
	Estimator        ReservationEstimator
	Lease            time.Duration
	Now              func() time.Time // injectable clock for deterministic retry/replay tests
	Overdraft        reservations.OverdraftPolicy
	Metrics          MetricsSink
	notifierMu       sync.RWMutex
	Notifier         OverdraftNotifier
	notifierObserver func(string, float64)
}

func (c *DurableReservationCoordinator) SetNotifier(notifier OverdraftNotifier) {
	if c == nil {
		return
	}
	c.notifierMu.Lock()
	old := c.Notifier
	c.Notifier = notifier
	observer := c.notifierObserver
	c.notifierMu.Unlock()
	if n, ok := notifier.(*AsyncOverdraftNotifier); ok {
		n.SetMetricObserver(observer)
	}
	// Plugin reloads replace the coordinator. Close only notifiers that expose
	// the optional lifecycle hook; the base interface remains compatible with
	// synchronous/custom implementations.
	if old != nil && old != notifier {
		if closer, ok := old.(interface{ Close() }); ok {
			closer.Close()
		}
	}
}

// SetNotifierMetricObserver forwards low-cardinality delivery metrics to the
// currently configured asynchronous notifier when one is installed.
func (c *DurableReservationCoordinator) SetNotifierMetricObserver(observer func(string, float64)) {
	if c == nil {
		return
	}
	c.notifierMu.RLock()
	notifier := c.Notifier
	c.notifierMu.RUnlock()
	c.notifierMu.Lock()
	c.notifierObserver = observer
	c.notifierMu.Unlock()
	if n, ok := notifier.(*AsyncOverdraftNotifier); ok {
		n.SetMetricObserver(observer)
	}
}

func (c *DurableReservationCoordinator) notifier() OverdraftNotifier {
	if c == nil {
		return nil
	}
	c.notifierMu.RLock()
	defer c.notifierMu.RUnlock()
	return c.Notifier
}

// Close releases asynchronous delivery resources during plugin shutdown or
// replacement. It is intentionally idempotent through the notifier's own
// lifecycle contract.
func (c *DurableReservationCoordinator) Close() {
	if c == nil {
		return
	}
	c.SetNotifier(nil)
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
		if c.Metrics != nil {
			c.Metrics.ReservationObserved(ctx, "reserved", amount)
		}
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
	if c.Metrics != nil {
		c.Metrics.ReservationObserved(ctx, "reserved", amount)
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
		if notifier := c.notifier(); (excess != reservations.Amount{}) && notifier != nil {
			if err := notifier.Notify(ctx, OverdraftEvent{ReservationID: r.ID, Reserved: r.ReservedAmount, Actual: settleAmount, Excess: excess, Allowed: c.Overdraft.Allow, Reason: c.Overdraft.Reason}); err != nil && first == nil {
				first = fmt.Errorf("overdraft notification: %w", err)
				if c.Metrics != nil {
					c.Metrics.NotifierObserved(ctx, "failed")
				}
			} else if c.Metrics != nil {
				c.Metrics.NotifierObserved(ctx, "delivered")
			}
		}
		if c.Metrics != nil && (excess != reservations.Amount{}) {
			c.Metrics.OverdraftObserved(ctx, c.Overdraft.Allow, excess)
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
