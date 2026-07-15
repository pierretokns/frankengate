package authorityepoch

import (
	"errors"
	"fmt"
	"sync"
)

var (
	ErrInvalidPrincipal  = errors.New("invalid principal")
	ErrInvalidReference  = errors.New("invalid authority reference")
	ErrUnknownPrincipal  = errors.New("unknown principal")
	ErrInactivePrincipal = errors.New("principal is inactive")
	ErrStaleEpoch        = errors.New("authorization epoch is stale")
)

type ArtifactKind string

const (
	ArtifactUnary             ArtifactKind = "unary"
	ArtifactSSE               ArtifactKind = "sse"
	ArtifactWebSocket         ArtifactKind = "websocket"
	ArtifactQueued            ArtifactKind = "queued"
	ArtifactKey               ArtifactKind = "key"
	ArtifactCache             ArtifactKind = "cache"
	ArtifactMCPGrant          ArtifactKind = "mcp_grant"
	ArtifactMCPLiveConnection ArtifactKind = "mcp_live_connection"
)

var supportedArtifactKinds = map[ArtifactKind]struct{}{
	ArtifactUnary:             {},
	ArtifactSSE:               {},
	ArtifactWebSocket:         {},
	ArtifactQueued:            {},
	ArtifactKey:               {},
	ArtifactCache:             {},
	ArtifactMCPGrant:          {},
	ArtifactMCPLiveConnection: {},
}

type Reason string

const (
	ReasonGroupRemoved Reason = "group_removed"
	ReasonDeactivated  Reason = "deactivated"
)

const LogicalSLORevisions uint64 = 0

type Principal struct {
	Tenant  string
	Issuer  string
	Subject string
}

type Reference struct {
	Principal Principal
	Epoch     uint64
	Kind      ArtifactKind
	ID        string
}

type EpochEvent struct {
	Principal Principal
	OldEpoch  uint64
	NewEpoch  uint64
	Reason    Reason
	Revision  uint64
}

type Cancellation struct {
	Reference        Reference
	Reason           Reason
	Revision         uint64
	DeadlineRevision uint64
}

type Registry struct {
	mu            sync.RWMutex
	principals    map[Principal]principalState
	subscriptions map[Reference]map[uint64]chan Cancellation
	nextSubID     uint64
	revision      uint64
}

type principalState struct {
	epoch  uint64
	active bool
}

func NewRegistry() *Registry {
	return &Registry{
		principals:    make(map[Principal]principalState),
		subscriptions: make(map[Reference]map[uint64]chan Cancellation),
	}
}

func (r *Registry) Activate(principal Principal, epoch uint64) error {
	if err := validatePrincipal(principal); err != nil {
		return err
	}
	if epoch == 0 {
		return fmt.Errorf("%w: epoch must be positive", ErrInvalidReference)
	}

	r.mu.Lock()
	defer r.mu.Unlock()
	if state, ok := r.principals[principal]; ok && epoch <= state.epoch {
		return ErrStaleEpoch
	}
	r.principals[principal] = principalState{epoch: epoch, active: true}
	return nil
}

func (r *Registry) Deactivate(principal Principal, reason Reason) (EpochEvent, error) {
	if err := validatePrincipal(principal); err != nil {
		return EpochEvent{}, err
	}
	if reason == "" {
		return EpochEvent{}, fmt.Errorf("%w: reason is required", ErrInvalidReference)
	}

	r.mu.Lock()
	defer r.mu.Unlock()
	state, ok := r.principals[principal]
	if !ok {
		return EpochEvent{}, ErrUnknownPrincipal
	}
	oldEpoch := state.epoch
	state.epoch++
	state.active = false
	r.principals[principal] = state
	r.revision++
	event := EpochEvent{
		Principal: principal,
		OldEpoch:  oldEpoch,
		NewEpoch:  state.epoch,
		Reason:    reason,
		Revision:  r.revision,
	}
	r.cancelLocked(principal, oldEpoch, reason, event.Revision)
	return event, nil
}

func (r *Registry) AdvanceEpoch(principal Principal, reason Reason) (EpochEvent, error) {
	if err := validatePrincipal(principal); err != nil {
		return EpochEvent{}, err
	}
	if reason == "" {
		return EpochEvent{}, fmt.Errorf("%w: reason is required", ErrInvalidReference)
	}

	r.mu.Lock()
	defer r.mu.Unlock()
	state, ok := r.principals[principal]
	if !ok {
		return EpochEvent{}, ErrUnknownPrincipal
	}
	if !state.active {
		return EpochEvent{}, ErrInactivePrincipal
	}
	oldEpoch := state.epoch
	state.epoch++
	r.principals[principal] = state
	r.revision++
	event := EpochEvent{
		Principal: principal,
		OldEpoch:  oldEpoch,
		NewEpoch:  state.epoch,
		Reason:    reason,
		Revision:  r.revision,
	}
	r.cancelLocked(principal, oldEpoch, reason, event.Revision)
	return event, nil
}

func (r *Registry) Mint(principal Principal, kind ArtifactKind, id string) (Reference, error) {
	if id == "" || kind == "" {
		return Reference{}, fmt.Errorf("%w: kind and id are required", ErrInvalidReference)
	}
	if !isSupportedArtifactKind(kind) {
		return Reference{}, fmt.Errorf("%w: unsupported artifact kind %q", ErrInvalidReference, kind)
	}
	if err := validatePrincipal(principal); err != nil {
		return Reference{}, err
	}

	r.mu.RLock()
	defer r.mu.RUnlock()
	state, ok := r.principals[principal]
	if !ok {
		return Reference{}, ErrUnknownPrincipal
	}
	if !state.active {
		return Reference{}, ErrInactivePrincipal
	}
	return Reference{
		Principal: principal,
		Epoch:     state.epoch,
		Kind:      kind,
		ID:        id,
	}, nil
}

func (r *Registry) Validate(ref Reference) error {
	if ref.ID == "" || ref.Kind == "" || ref.Epoch == 0 {
		return fmt.Errorf("%w: kind, id and epoch are required", ErrInvalidReference)
	}
	if !isSupportedArtifactKind(ref.Kind) {
		return fmt.Errorf("%w: unsupported artifact kind %q", ErrInvalidReference, ref.Kind)
	}
	if err := validatePrincipal(ref.Principal); err != nil {
		return err
	}

	r.mu.RLock()
	defer r.mu.RUnlock()
	state, ok := r.principals[ref.Principal]
	if !ok {
		return ErrUnknownPrincipal
	}
	if !state.active {
		return ErrInactivePrincipal
	}
	if ref.Epoch != state.epoch {
		return ErrStaleEpoch
	}
	return nil
}

func (r *Registry) Subscribe(ref Reference) (<-chan Cancellation, func(), error) {
	if err := r.Validate(ref); err != nil {
		return nil, nil, err
	}

	r.mu.Lock()
	defer r.mu.Unlock()
	if err := r.validateLocked(ref); err != nil {
		return nil, nil, err
	}
	r.nextSubID++
	id := r.nextSubID
	ch := make(chan Cancellation, 1)
	if r.subscriptions[ref] == nil {
		r.subscriptions[ref] = make(map[uint64]chan Cancellation)
	}
	r.subscriptions[ref][id] = ch

	unsubscribe := func() {
		r.mu.Lock()
		defer r.mu.Unlock()
		subs := r.subscriptions[ref]
		if subs == nil {
			return
		}
		delete(subs, id)
		if len(subs) == 0 {
			delete(r.subscriptions, ref)
		}
	}
	return ch, unsubscribe, nil
}

func validatePrincipal(principal Principal) error {
	if principal.Tenant == "" || principal.Issuer == "" || principal.Subject == "" {
		return ErrInvalidPrincipal
	}
	return nil
}

func isSupportedArtifactKind(kind ArtifactKind) bool {
	_, ok := supportedArtifactKinds[kind]
	return ok
}

func (r *Registry) validateLocked(ref Reference) error {
	if ref.ID == "" || ref.Kind == "" || ref.Epoch == 0 {
		return fmt.Errorf("%w: kind, id and epoch are required", ErrInvalidReference)
	}
	if !isSupportedArtifactKind(ref.Kind) {
		return fmt.Errorf("%w: unsupported artifact kind %q", ErrInvalidReference, ref.Kind)
	}
	if err := validatePrincipal(ref.Principal); err != nil {
		return err
	}
	state, ok := r.principals[ref.Principal]
	if !ok {
		return ErrUnknownPrincipal
	}
	if !state.active {
		return ErrInactivePrincipal
	}
	if ref.Epoch != state.epoch {
		return ErrStaleEpoch
	}
	return nil
}

func (r *Registry) cancelLocked(principal Principal, epoch uint64, reason Reason, revision uint64) {
	for ref, subs := range r.subscriptions {
		if ref.Principal != principal || ref.Epoch != epoch {
			continue
		}
		cancellation := Cancellation{
			Reference:        ref,
			Reason:           reason,
			Revision:         revision,
			DeadlineRevision: revision + LogicalSLORevisions,
		}
		for id, ch := range subs {
			ch <- cancellation
			delete(subs, id)
			close(ch)
		}
		delete(r.subscriptions, ref)
	}
}
