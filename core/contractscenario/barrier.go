package contractscenario

import (
	"context"
	"fmt"
	"sync"
)

// Barriers coordinate deterministic transport milestones without sleeps.
type Barriers struct {
	mu      sync.Mutex
	reached map[string]chan struct{}
	closed  map[string]bool
}

func NewBarriers(names ...string) (*Barriers, error) {
	b := &Barriers{reached: make(map[string]chan struct{}, len(names)), closed: make(map[string]bool, len(names))}
	for _, name := range names {
		if name == "" {
			return nil, fmt.Errorf("barrier name is required")
		}
		if _, exists := b.reached[name]; exists {
			return nil, fmt.Errorf("duplicate barrier %q", name)
		}
		b.reached[name] = make(chan struct{})
	}
	return b, nil
}

func (b *Barriers) Reach(name string) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	ch, exists := b.reached[name]
	if !exists {
		return fmt.Errorf("unknown barrier %q", name)
	}
	if !b.closed[name] {
		close(ch)
		b.closed[name] = true
	}
	return nil
}

func (b *Barriers) Wait(ctx context.Context, name string) error {
	b.mu.Lock()
	ch, exists := b.reached[name]
	b.mu.Unlock()
	if !exists {
		return fmt.Errorf("unknown barrier %q", name)
	}
	select {
	case <-ch:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
