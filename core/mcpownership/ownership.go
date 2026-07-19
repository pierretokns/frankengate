package mcpownership

import (
	"errors"
	"fmt"
	"slices"
	"sync"
	"time"
)

var (
	ErrAlreadyOwned = errors.New("connection is owned by another live pod")
	ErrInvalidClaim = errors.New("ownership claim is invalid")
	ErrLeaseExpired = errors.New("ownership lease has expired")
	ErrStaleFence   = errors.New("ownership fence is stale")
	ErrNotFound     = errors.New("connection ownership record not found")
)

type ConnectionKey struct {
	ClientID   string
	Principal  string
	SessionKey string
}

type ReconnectAction string

const (
	ReconnectNone   ReconnectAction = "none"
	ReconnectFresh  ReconnectAction = "fresh"
	ReconnectResume ReconnectAction = "resume"
)

type OperationStatus string

const (
	OperationPending   OperationStatus = "pending"
	OperationAmbiguous OperationStatus = "ambiguous"
	OperationSucceeded OperationStatus = "succeeded"
	OperationFailed    OperationStatus = "failed"
)

type Claim struct {
	Key        ConnectionKey
	OwnerPod   string
	Fence      uint64
	LeaseUntil time.Time
	Reconnect  ReconnectDecision
}

type ReconnectDecision struct {
	Action              ReconnectAction
	ServerSessionID     string
	AmbiguousOperations []string
}

type CallReceipt struct {
	OperationID       string
	OwnerPod          string
	Fence             uint64
	Status            OperationStatus
	Attempt           int
	Duplicate         bool
	AmbiguousPrevious bool
}

type OAuthRoute struct {
	Key      ConnectionKey
	OwnerPod string
	Fence    uint64
}

// Store is the fencing contract used by the MCP execution path.
//
// Registry is the deliberately explicit process-local implementation. Hosts
// running more than one gateway replica must inject a durable implementation
// (for example, one backed by the existing Postgres/config-store machinery)
// that preserves these atomic claim, fence, and idempotency semantics. The
// MCP package depends on this interface rather than a particular database or
// cache, so a durable adapter can be added without changing request handling.
// Implementations must return an error on unavailable state; callers treat
// those errors as authorization failures and do not touch the upstream MCP
// connection.
type Store interface {
	Claim(now time.Time, key ConnectionKey, ownerPod string, ttl time.Duration) (Claim, error)
	Renew(now time.Time, key ConnectionKey, ownerPod string, fence uint64, ttl time.Duration) (Claim, error)
	AttachServerSession(now time.Time, key ConnectionKey, ownerPod string, fence uint64, serverSessionID string, resumable bool) error
	StartCall(now time.Time, key ConnectionKey, ownerPod string, fence uint64, operationID string) (CallReceipt, error)
	CompleteCall(now time.Time, key ConnectionKey, ownerPod string, fence uint64, operationID string, success bool) (CallReceipt, error)
	BeginOAuth(now time.Time, key ConnectionKey, ownerPod string, fence uint64, state string, ttl time.Duration) error
	RouteOAuthCallback(now time.Time, state string) (OAuthRoute, error)
	Operations(key ConnectionKey) []OperationSnapshot
}

type OperationSnapshot struct {
	ID        string
	Status    OperationStatus
	Attempt   int
	Ambiguous bool
}

type record struct {
	key              ConnectionKey
	ownerPod         string
	fence            uint64
	leaseUntil       time.Time
	serverSessionID  string
	sessionResumable bool
	operations       map[string]*operation
}

type operation struct {
	id        string
	status    OperationStatus
	attempts  []attempt
	ambiguous bool
}

type attempt struct {
	pod     string
	fence   uint64
	started time.Time
}

type oauthFlow struct {
	key       ConnectionKey
	state     string
	expiresAt time.Time
}

type Registry struct {
	mu      sync.Mutex
	records map[ConnectionKey]*record
	oauth   map[string]oauthFlow
}

func NewRegistry() *Registry {
	return &Registry{
		records: make(map[ConnectionKey]*record),
		oauth:   make(map[string]oauthFlow),
	}
}

// NewProcessLocalStore makes the non-durable default explicit at call sites.
// It is suitable for a single process or tests only; multi-replica hosts must
// inject a shared Store implementation.
func NewProcessLocalStore() Store { return NewRegistry() }

func (r *Registry) Claim(now time.Time, key ConnectionKey, ownerPod string, ttl time.Duration) (Claim, error) {
	if err := validateClaim(key, ownerPod, ttl); err != nil {
		return Claim{}, err
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	rec := r.records[key]
	if rec == nil {
		rec = &record{
			key:        key,
			operations: make(map[string]*operation),
		}
		r.records[key] = rec
	}

	if rec.ownerPod == "" {
		rec.ownerPod = ownerPod
		rec.fence++
		rec.leaseUntil = now.Add(ttl)
		return claimFromRecord(rec, ReconnectDecision{Action: ReconnectFresh}), nil
	}

	if rec.ownerPod == ownerPod && now.Before(rec.leaseUntil) {
		rec.leaseUntil = now.Add(ttl)
		return claimFromRecord(rec, ReconnectDecision{Action: ReconnectNone}), nil
	}

	if now.Before(rec.leaseUntil) {
		return Claim{}, fmt.Errorf("%w: owner=%s fence=%d lease_until=%s", ErrAlreadyOwned, rec.ownerPod, rec.fence, rec.leaseUntil.Format(time.RFC3339Nano))
	}

	ambiguous := markPendingAmbiguous(rec)
	rec.ownerPod = ownerPod
	rec.fence++
	rec.leaseUntil = now.Add(ttl)

	decision := ReconnectDecision{
		Action:              ReconnectFresh,
		AmbiguousOperations: ambiguous,
	}
	if rec.serverSessionID != "" && rec.sessionResumable {
		decision.Action = ReconnectResume
		decision.ServerSessionID = rec.serverSessionID
	}

	return claimFromRecord(rec, decision), nil
}

func (r *Registry) Renew(now time.Time, key ConnectionKey, ownerPod string, fence uint64, ttl time.Duration) (Claim, error) {
	if err := validateClaim(key, ownerPod, ttl); err != nil {
		return Claim{}, err
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	rec, err := r.requireOwner(now, key, ownerPod, fence)
	if err != nil {
		return Claim{}, err
	}
	rec.leaseUntil = now.Add(ttl)
	return claimFromRecord(rec, ReconnectDecision{Action: ReconnectNone}), nil
}

func (r *Registry) AttachServerSession(now time.Time, key ConnectionKey, ownerPod string, fence uint64, serverSessionID string, resumable bool) error {
	if serverSessionID == "" {
		return fmt.Errorf("%w: server session id is required", ErrInvalidClaim)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	rec, err := r.requireOwner(now, key, ownerPod, fence)
	if err != nil {
		return err
	}
	rec.serverSessionID = serverSessionID
	rec.sessionResumable = resumable
	return nil
}

func (r *Registry) StartCall(now time.Time, key ConnectionKey, ownerPod string, fence uint64, operationID string) (CallReceipt, error) {
	if operationID == "" {
		return CallReceipt{}, fmt.Errorf("%w: operation id is required", ErrInvalidClaim)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	rec, err := r.requireOwner(now, key, ownerPod, fence)
	if err != nil {
		return CallReceipt{}, err
	}

	op := rec.operations[operationID]
	if op == nil {
		op = &operation{id: operationID, status: OperationPending}
		rec.operations[operationID] = op
		op.attempts = append(op.attempts, attempt{pod: ownerPod, fence: fence, started: now})
		return receiptFromOperation(op, ownerPod, fence, false, false), nil
	}

	switch op.status {
	case OperationSucceeded, OperationFailed:
		return receiptFromOperation(op, ownerPod, fence, true, op.ambiguous), nil
	case OperationPending:
		last := op.attempts[len(op.attempts)-1]
		if last.fence == fence && last.pod == ownerPod {
			return receiptFromOperation(op, ownerPod, fence, true, op.ambiguous), nil
		}
		return CallReceipt{}, ErrStaleFence
	case OperationAmbiguous:
		op.status = OperationPending
		op.attempts = append(op.attempts, attempt{pod: ownerPod, fence: fence, started: now})
		return receiptFromOperation(op, ownerPod, fence, false, true), nil
	default:
		return CallReceipt{}, fmt.Errorf("%w: unknown operation status %q", ErrInvalidClaim, op.status)
	}
}

func (r *Registry) CompleteCall(now time.Time, key ConnectionKey, ownerPod string, fence uint64, operationID string, success bool) (CallReceipt, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec, err := r.requireOwner(now, key, ownerPod, fence)
	if err != nil {
		return CallReceipt{}, err
	}

	op := rec.operations[operationID]
	if op == nil {
		return CallReceipt{}, ErrNotFound
	}
	if op.status != OperationPending {
		return receiptFromOperation(op, ownerPod, fence, true, op.ambiguous), nil
	}
	last := op.attempts[len(op.attempts)-1]
	if last.pod != ownerPod || last.fence != fence {
		return CallReceipt{}, ErrStaleFence
	}
	if success {
		op.status = OperationSucceeded
	} else {
		op.status = OperationFailed
	}
	return receiptFromOperation(op, ownerPod, fence, false, op.ambiguous), nil
}

func (r *Registry) BeginOAuth(now time.Time, key ConnectionKey, ownerPod string, fence uint64, state string, ttl time.Duration) error {
	if state == "" || ttl <= 0 {
		return fmt.Errorf("%w: oauth state and ttl are required", ErrInvalidClaim)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	if _, err := r.requireOwner(now, key, ownerPod, fence); err != nil {
		return err
	}
	r.oauth[state] = oauthFlow{key: key, state: state, expiresAt: now.Add(ttl)}
	return nil
}

func (r *Registry) RouteOAuthCallback(now time.Time, state string) (OAuthRoute, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	flow, ok := r.oauth[state]
	if !ok {
		return OAuthRoute{}, ErrNotFound
	}
	if !now.Before(flow.expiresAt) {
		delete(r.oauth, state)
		return OAuthRoute{}, ErrLeaseExpired
	}

	rec := r.records[flow.key]
	if rec == nil || rec.ownerPod == "" {
		return OAuthRoute{}, ErrNotFound
	}
	if !now.Before(rec.leaseUntil) {
		return OAuthRoute{}, ErrLeaseExpired
	}
	return OAuthRoute{Key: flow.key, OwnerPod: rec.ownerPod, Fence: rec.fence}, nil
}

func (r *Registry) Operations(key ConnectionKey) []OperationSnapshot {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec := r.records[key]
	if rec == nil {
		return nil
	}

	out := make([]OperationSnapshot, 0, len(rec.operations))
	for _, op := range rec.operations {
		out = append(out, OperationSnapshot{
			ID:        op.id,
			Status:    op.status,
			Attempt:   len(op.attempts),
			Ambiguous: op.ambiguous,
		})
	}
	slices.SortFunc(out, func(a, b OperationSnapshot) int {
		if a.ID < b.ID {
			return -1
		}
		if a.ID > b.ID {
			return 1
		}
		return 0
	})
	return out
}

func validateClaim(key ConnectionKey, ownerPod string, ttl time.Duration) error {
	if key.ClientID == "" || key.Principal == "" || key.SessionKey == "" || ownerPod == "" || ttl <= 0 {
		return fmt.Errorf("%w: key, owner pod and positive ttl are required", ErrInvalidClaim)
	}
	return nil
}

func (r *Registry) requireOwner(now time.Time, key ConnectionKey, ownerPod string, fence uint64) (*record, error) {
	rec := r.records[key]
	if rec == nil {
		return nil, ErrNotFound
	}
	if rec.ownerPod != ownerPod || rec.fence != fence {
		return nil, ErrStaleFence
	}
	if !now.Before(rec.leaseUntil) {
		return nil, ErrLeaseExpired
	}
	return rec, nil
}

func claimFromRecord(rec *record, decision ReconnectDecision) Claim {
	return Claim{
		Key:        rec.key,
		OwnerPod:   rec.ownerPod,
		Fence:      rec.fence,
		LeaseUntil: rec.leaseUntil,
		Reconnect:  decision,
	}
}

func markPendingAmbiguous(rec *record) []string {
	var ambiguous []string
	for _, op := range rec.operations {
		if op.status == OperationPending {
			op.status = OperationAmbiguous
			op.ambiguous = true
			ambiguous = append(ambiguous, op.id)
		}
	}
	slices.Sort(ambiguous)
	return ambiguous
}

func receiptFromOperation(op *operation, ownerPod string, fence uint64, duplicate, ambiguousPrevious bool) CallReceipt {
	return CallReceipt{
		OperationID:       op.id,
		OwnerPod:          ownerPod,
		Fence:             fence,
		Status:            op.status,
		Attempt:           len(op.attempts),
		Duplicate:         duplicate,
		AmbiguousPrevious: ambiguousPrevious,
	}
}
