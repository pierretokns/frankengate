// Package reservations models fenced quota/budget reservations for logical
// requests and their provider/tool/replay attempts.
package reservations

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

var (
	ErrAlreadyFinalized    = errors.New("reservation already finalized")
	ErrInvalidReservation  = errors.New("invalid reservation")
	ErrNotFound            = errors.New("reservation not found")
	ErrOverdraftDenied     = errors.New("reservation overdraft denied")
	ErrReservationConflict = errors.New("reservation conflict")
	ErrStaleEpoch          = errors.New("stale reservation epoch")
)

type LogicalRequestID string
type AttemptID string
type ReservationID string
type AttemptEpoch uint64

type AccountingLane string

const (
	AccountingLaneNormal AccountingLane = "normal"
	AccountingLaneShadow AccountingLane = "shadow"
	AccountingLaneTool   AccountingLane = "tool"
	AccountingLaneReplay AccountingLane = "replay"
)

type ReservationState string

const (
	ReservationStateActive   ReservationState = "active"
	ReservationStateSettled  ReservationState = "settled"
	ReservationStateRefunded ReservationState = "refunded"
)

type ExpiryState string

const (
	ExpiryStateNoLease ExpiryState = "no_lease"
	ExpiryStateLive    ExpiryState = "live"
	ExpiryStateExpired ExpiryState = "expired"
)

type OverdraftState string

const (
	OverdraftStateNone       OverdraftState = "none"
	OverdraftStateControlled OverdraftState = "controlled"
	OverdraftStateDenied     OverdraftState = "denied"
)

type OverdraftPolicy struct {
	Allow  bool
	Reason string
	// ApprovalRequired makes controlled overdraft admission fail closed until
	// an explicit approval is present.  This is intentionally carried with the
	// durable settlement request rather than inferred from dashboard metadata.
	ApprovalRequired bool
	Approved         bool
}

type Amount struct {
	Tokens     int64
	CostMicros int64
}

type Reservation struct {
	ID               ReservationID
	LogicalRequestID LogicalRequestID
	AttemptID        AttemptID
	AttemptEpoch     AttemptEpoch
	Lane             AccountingLane
	ReservedAmount   Amount
	SettledAmount    Amount
	RefundedAmount   Amount
	OverdraftAmount  Amount
	LeaseUntil       time.Time
	State            ReservationState
	OverdraftState   OverdraftState
	OverdraftReason  string
	SettlementKey    string
	RefundKey        string
	CreatedAt        time.Time
	UpdatedAt        time.Time
}

type ReservationRequest struct {
	LogicalRequestID LogicalRequestID
	AttemptID        AttemptID
	AttemptEpoch     AttemptEpoch
	Lane             AccountingLane
	Amount           Amount
	LeaseUntil       time.Time
	Now              time.Time
}

type RenewRequest struct {
	ReservationID ReservationID
	AttemptEpoch  AttemptEpoch
	LeaseUntil    time.Time
	Now           time.Time
}

type RefundRequest struct {
	ReservationID  ReservationID
	AttemptEpoch   AttemptEpoch
	IdempotencyKey string
	Reason         string
	Now            time.Time
}

type SettleRequest struct {
	ReservationID  ReservationID
	AttemptEpoch   AttemptEpoch
	ActualAmount   Amount
	IdempotencyKey string
	Overdraft      OverdraftPolicy
	Now            time.Time
}

type SweepRequest struct {
	Now        time.Time
	Candidates []SweepCandidate
}

type SweepCandidate struct {
	ReservationID ReservationID
	AttemptEpoch  AttemptEpoch
	LeaseUntil    time.Time
}

type SweepResult struct {
	Refunded   int
	StaleEpoch int
	Live       int
}

type AccountingSummary struct {
	ByLane map[AccountingLane]LaneTotal
}

type LaneTotal struct {
	Reserved    Amount
	Settled     Amount
	Refunded    Amount
	Outstanding Amount
	Overdraft   Amount
}

type Store interface {
	Reserve(context.Context, ReservationRequest) (Reservation, error)
	Renew(context.Context, RenewRequest) (Reservation, error)
	Settle(context.Context, SettleRequest) (Reservation, error)
	Refund(context.Context, RefundRequest) (Reservation, error)
	ListExpired(context.Context, SweepRequest) ([]SweepCandidate, error)
	SweepExpired(context.Context, SweepRequest) (SweepResult, error)
	AccountingSummary(context.Context) (AccountingSummary, error)
	Get(context.Context, ReservationID) (Reservation, error)
}

type InMemoryStore struct {
	mu           sync.Mutex
	reservations map[ReservationID]Reservation
}

func NewInMemoryStore() *InMemoryStore {
	return &InMemoryStore{
		reservations: make(map[ReservationID]Reservation),
	}
}

func (store *InMemoryStore) Reserve(_ context.Context, req ReservationRequest) (Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	lane := req.Lane
	if lane == "" {
		lane = AccountingLaneNormal
	}
	if err := validateReservationIdentity(req, lane); err != nil {
		return Reservation{}, err
	}
	id := reservationID(req.LogicalRequestID, req.AttemptID, req.AttemptEpoch, lane)
	store.mu.Lock()
	defer store.mu.Unlock()
	existing, exists := store.reservations[id]
	if exists {
		if existing.State != ReservationStateActive {
			return Reservation{}, ErrAlreadyFinalized
		}
		if sameReservationRequest(existing, req, lane) {
			return existing, nil
		}
		return Reservation{}, ErrReservationConflict
	}
	if err := validateNewReservationRequest(req, now); err != nil {
		return Reservation{}, err
	}
	reservation := Reservation{
		ID:               id,
		LogicalRequestID: req.LogicalRequestID,
		AttemptID:        req.AttemptID,
		AttemptEpoch:     req.AttemptEpoch,
		Lane:             lane,
		ReservedAmount:   req.Amount,
		LeaseUntil:       req.LeaseUntil,
		State:            ReservationStateActive,
		OverdraftState:   OverdraftStateNone,
		CreatedAt:        now,
		UpdatedAt:        now,
	}

	store.reservations[id] = reservation
	return reservation, nil
}

func (store *InMemoryStore) Renew(_ context.Context, req RenewRequest) (Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	if err := validateRenewRequest(req, now); err != nil {
		return Reservation{}, err
	}

	store.mu.Lock()
	defer store.mu.Unlock()

	reservation, ok := store.reservations[req.ReservationID]
	if !ok {
		return Reservation{}, ErrNotFound
	}
	if req.AttemptEpoch < reservation.AttemptEpoch {
		return Reservation{}, ErrStaleEpoch
	}
	if reservation.State != ReservationStateActive {
		return Reservation{}, ErrAlreadyFinalized
	}
	reservation.AttemptEpoch = req.AttemptEpoch
	reservation.LeaseUntil = req.LeaseUntil
	reservation.UpdatedAt = now
	store.reservations[req.ReservationID] = reservation
	return reservation, nil
}

func (store *InMemoryStore) Settle(_ context.Context, req SettleRequest) (Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	if err := validateSettleRequest(req); err != nil {
		return Reservation{}, err
	}

	store.mu.Lock()
	defer store.mu.Unlock()

	reservation, ok := store.reservations[req.ReservationID]
	if !ok {
		return Reservation{}, ErrNotFound
	}
	if req.AttemptEpoch != reservation.AttemptEpoch {
		return Reservation{}, ErrStaleEpoch
	}
	if reservation.State == ReservationStateSettled {
		if reservation.SettlementKey == req.IdempotencyKey && reservation.SettledAmount == req.ActualAmount {
			return reservation, nil
		}
		return Reservation{}, ErrAlreadyFinalized
	}
	if reservation.State == ReservationStateRefunded {
		return Reservation{}, ErrAlreadyFinalized
	}
	excess := excessAmount(req.ActualAmount, reservation.ReservedAmount)
	if excess != (Amount{}) {
		reservation.OverdraftAmount = excess
		reservation.OverdraftReason = req.Overdraft.Reason
		// Dashboard/alert metadata is not an authorization decision.  A caller
		// must provide the effective policy on the settlement request, and an
		// approval-required policy must carry an explicit approval bit.
		if !req.Overdraft.Allow || (req.Overdraft.ApprovalRequired && !req.Overdraft.Approved) {
			reservation.OverdraftState = OverdraftStateDenied
			reservation.UpdatedAt = now
			store.reservations[req.ReservationID] = reservation
			return Reservation{}, ErrOverdraftDenied
		}
		reservation.OverdraftState = OverdraftStateControlled
	} else {
		reservation.OverdraftAmount = Amount{}
		reservation.OverdraftReason = ""
		reservation.OverdraftState = OverdraftStateNone
	}
	reservation.State = ReservationStateSettled
	reservation.SettledAmount = req.ActualAmount
	reservation.RefundedAmount = unusedAmount(reservation.ReservedAmount, req.ActualAmount)
	reservation.SettlementKey = req.IdempotencyKey
	reservation.UpdatedAt = now
	store.reservations[req.ReservationID] = reservation
	return reservation, nil
}

func (store *InMemoryStore) Refund(_ context.Context, req RefundRequest) (Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	if err := validateRefundRequest(req); err != nil {
		return Reservation{}, err
	}

	store.mu.Lock()
	defer store.mu.Unlock()

	reservation, ok := store.reservations[req.ReservationID]
	if !ok {
		return Reservation{}, ErrNotFound
	}
	if req.AttemptEpoch != reservation.AttemptEpoch {
		return Reservation{}, ErrStaleEpoch
	}
	if reservation.State == ReservationStateRefunded {
		if reservation.RefundKey == req.IdempotencyKey {
			return reservation, nil
		}
		return Reservation{}, ErrAlreadyFinalized
	}
	if reservation.State == ReservationStateSettled {
		return Reservation{}, ErrAlreadyFinalized
	}
	reservation.State = ReservationStateRefunded
	reservation.RefundedAmount = reservation.ReservedAmount
	reservation.RefundKey = req.IdempotencyKey
	reservation.UpdatedAt = now
	store.reservations[req.ReservationID] = reservation
	return reservation, nil
}

func (store *InMemoryStore) ListExpired(_ context.Context, req SweepRequest) ([]SweepCandidate, error) {
	store.mu.Lock()
	defer store.mu.Unlock()

	var candidates []SweepCandidate
	for _, reservation := range store.reservations {
		if reservation.State != ReservationStateActive {
			continue
		}
		if !isExpired(reservation, req.Now) {
			continue
		}
		candidates = append(candidates, SweepCandidate{
			ReservationID: reservation.ID,
			AttemptEpoch:  reservation.AttemptEpoch,
			LeaseUntil:    reservation.LeaseUntil,
		})
	}
	return candidates, nil
}

func (store *InMemoryStore) SweepExpired(ctx context.Context, req SweepRequest) (SweepResult, error) {
	candidates := req.Candidates
	if candidates == nil {
		var err error
		candidates, err = store.ListExpired(ctx, req)
		if err != nil {
			return SweepResult{}, err
		}
	}

	store.mu.Lock()
	defer store.mu.Unlock()

	var result SweepResult
	for _, candidate := range candidates {
		reservation, ok := store.reservations[candidate.ReservationID]
		if !ok {
			result.StaleEpoch++
			continue
		}
		if candidate.AttemptEpoch != reservation.AttemptEpoch {
			result.StaleEpoch++
			continue
		}
		if reservation.State != ReservationStateActive || !isExpired(reservation, req.Now) {
			result.Live++
			continue
		}
		reservation.State = ReservationStateRefunded
		reservation.RefundedAmount = reservation.ReservedAmount
		reservation.UpdatedAt = req.Now
		store.reservations[reservation.ID] = reservation
		result.Refunded++
	}
	return result, nil
}

func (store *InMemoryStore) AccountingSummary(_ context.Context) (AccountingSummary, error) {
	store.mu.Lock()
	defer store.mu.Unlock()

	summary := AccountingSummary{ByLane: make(map[AccountingLane]LaneTotal)}
	for _, reservation := range store.reservations {
		total := summary.ByLane[reservation.Lane]
		total.Reserved = addAmount(total.Reserved, reservation.ReservedAmount)
		switch reservation.State {
		case ReservationStateActive:
			total.Outstanding = addAmount(total.Outstanding, reservation.ReservedAmount)
		case ReservationStateSettled:
			total.Settled = addAmount(total.Settled, reservation.SettledAmount)
			total.Refunded = addAmount(total.Refunded, reservation.RefundedAmount)
			total.Overdraft = addAmount(total.Overdraft, reservation.OverdraftAmount)
		case ReservationStateRefunded:
			total.Refunded = addAmount(total.Refunded, reservation.RefundedAmount)
		}
		summary.ByLane[reservation.Lane] = total
	}
	return summary, nil
}

func (store *InMemoryStore) Get(_ context.Context, id ReservationID) (Reservation, error) {
	store.mu.Lock()
	defer store.mu.Unlock()

	reservation, ok := store.reservations[id]
	if !ok {
		return Reservation{}, ErrNotFound
	}
	return reservation, nil
}

func reservationID(logicalRequestID LogicalRequestID, attemptID AttemptID, epoch AttemptEpoch, lane AccountingLane) ReservationID {
	return ReservationID(fmt.Sprintf("%s:%s:%d:%s", logicalRequestID, attemptID, epoch, lane))
}

func validateReservationIdentity(req ReservationRequest, lane AccountingLane) error {
	if req.LogicalRequestID == "" {
		return fmt.Errorf("%w: logical request id is required", ErrInvalidReservation)
	}
	if req.AttemptID == "" {
		return fmt.Errorf("%w: attempt id is required", ErrInvalidReservation)
	}
	if req.AttemptEpoch == 0 {
		return fmt.Errorf("%w: attempt epoch must be nonzero", ErrInvalidReservation)
	}
	if lane == "" {
		return fmt.Errorf("%w: accounting lane is required", ErrInvalidReservation)
	}
	return nil
}

func validateNewReservationRequest(req ReservationRequest, now time.Time) error {
	if req.Amount.Tokens < 0 {
		return fmt.Errorf("%w: tokens must be nonnegative", ErrInvalidReservation)
	}
	if req.Amount.CostMicros < 0 {
		return fmt.Errorf("%w: cost micros must be nonnegative", ErrInvalidReservation)
	}
	if req.Amount.Tokens == 0 && req.Amount.CostMicros == 0 {
		return fmt.Errorf("%w: reservation amount must be positive", ErrInvalidReservation)
	}
	if req.LeaseUntil.IsZero() {
		return fmt.Errorf("%w: lease is required", ErrInvalidReservation)
	}
	if !req.LeaseUntil.After(now) {
		return fmt.Errorf("%w: lease must be after now", ErrInvalidReservation)
	}
	return nil
}

func validateRenewRequest(req RenewRequest, now time.Time) error {
	if err := validateMutationIdentity(req.ReservationID, req.AttemptEpoch); err != nil {
		return err
	}
	if req.LeaseUntil.IsZero() {
		return fmt.Errorf("%w: lease is required", ErrInvalidReservation)
	}
	if !req.LeaseUntil.After(now) {
		return fmt.Errorf("%w: lease must be after now", ErrInvalidReservation)
	}
	return nil
}

func validateSettleRequest(req SettleRequest) error {
	if err := validateMutationIdentity(req.ReservationID, req.AttemptEpoch); err != nil {
		return err
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("%w: idempotency key is required", ErrInvalidReservation)
	}
	if req.ActualAmount.Tokens < 0 {
		return fmt.Errorf("%w: tokens must be nonnegative", ErrInvalidReservation)
	}
	if req.ActualAmount.CostMicros < 0 {
		return fmt.Errorf("%w: cost micros must be nonnegative", ErrInvalidReservation)
	}
	return nil
}

func validateRefundRequest(req RefundRequest) error {
	if err := validateMutationIdentity(req.ReservationID, req.AttemptEpoch); err != nil {
		return err
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("%w: idempotency key is required", ErrInvalidReservation)
	}
	return nil
}

func validateMutationIdentity(id ReservationID, epoch AttemptEpoch) error {
	if id == "" {
		return fmt.Errorf("%w: reservation id is required", ErrInvalidReservation)
	}
	if epoch == 0 {
		return fmt.Errorf("%w: attempt epoch must be nonzero", ErrInvalidReservation)
	}
	return nil
}

func sameReservationRequest(existing Reservation, req ReservationRequest, lane AccountingLane) bool {
	return existing.LogicalRequestID == req.LogicalRequestID &&
		existing.AttemptID == req.AttemptID &&
		existing.AttemptEpoch == req.AttemptEpoch &&
		existing.Lane == lane &&
		existing.ReservedAmount == req.Amount &&
		existing.LeaseUntil.Equal(req.LeaseUntil)
}

func isExpired(reservation Reservation, now time.Time) bool {
	return !reservation.LeaseUntil.IsZero() && !reservation.LeaseUntil.After(now)
}

func (reservation Reservation) ExpiryStateAt(now time.Time) ExpiryState {
	if reservation.LeaseUntil.IsZero() {
		return ExpiryStateNoLease
	}
	if reservation.LeaseUntil.After(now) {
		return ExpiryStateLive
	}
	return ExpiryStateExpired
}

func unusedAmount(reserved Amount, actual Amount) Amount {
	return Amount{
		Tokens:     nonNegative(reserved.Tokens - actual.Tokens),
		CostMicros: nonNegative(reserved.CostMicros - actual.CostMicros),
	}
}

func excessAmount(actual Amount, reserved Amount) Amount {
	return Amount{
		Tokens:     nonNegative(actual.Tokens - reserved.Tokens),
		CostMicros: nonNegative(actual.CostMicros - reserved.CostMicros),
	}
}

func addAmount(left Amount, right Amount) Amount {
	return Amount{
		Tokens:     left.Tokens + right.Tokens,
		CostMicros: left.CostMicros + right.CostMicros,
	}
}

func nonNegative(value int64) int64 {
	if value < 0 {
		return 0
	}
	return value
}
