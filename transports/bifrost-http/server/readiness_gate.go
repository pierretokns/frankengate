package server

import "sync/atomic"

// authorityReadinessGate is a one-bit startup fence shared by the health
// handler and the bootstrap sequence. Keeping this separate from the live
// freshness lease makes the contract explicit: a pod is never ready until a
// complete fenced authority snapshot/catch-up has succeeded.
type authorityReadinessGate struct{ open atomic.Bool }

func (g *authorityReadinessGate) Open() {
	if g != nil {
		g.open.Store(true)
	}
}

func (g *authorityReadinessGate) Close() {
	if g != nil {
		g.open.Store(false)
	}
}

func (g *authorityReadinessGate) Ready() bool {
	return g != nil && g.open.Load()
}
