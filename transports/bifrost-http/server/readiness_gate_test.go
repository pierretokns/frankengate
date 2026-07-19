package server

import (
	"sync"
	"testing"
)

func TestAuthorityReadinessGateStartsClosedAndTransitionsAtomically(t *testing.T) {
	var gate authorityReadinessGate
	if gate.Ready() {
		t.Fatal("readiness gate must start closed")
	}
	gate.Open()
	if !gate.Ready() {
		t.Fatal("readiness gate did not open")
	}
	gate.Close()
	if gate.Ready() {
		t.Fatal("readiness gate did not close")
	}
}

func TestAuthorityReadinessGateConcurrentReaders(t *testing.T) {
	var gate authorityReadinessGate
	var wg sync.WaitGroup
	for i := 0; i < 32; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 1000; j++ {
				gate.Open()
				_ = gate.Ready()
				gate.Close()
			}
		}()
	}
	wg.Wait()
}
