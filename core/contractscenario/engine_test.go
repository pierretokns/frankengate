package contractscenario

import (
	"context"
	"errors"
	"fmt"
	"math"
	"sync"
	"testing"
	"time"
)

func testLimits() Limits {
	return Limits{
		MaxRequests: 10, MaxObjects: 10, MaxBodyBytes: 1024, MaxEventBytes: 1024,
		MaxDiagnosticByte: 64, MaxStreamDuration: time.Minute, MaxIdleDuration: time.Second,
	}
}

func testSpec() ScenarioSpec {
	return ScenarioSpec{Name: "matrix", Cells: []CellSpec{
		{
			Name:         "openai",
			CredentialID: "credential-openai",
			InitialState: "ready",
			Expectations: []Expectation{
				{ID: "first", Method: "POST", RawTarget: "/openai/v1/responses?x=%2B&x=", Headers: []Header{{Name: "X-Test", Value: "a"}, {Name: "x-test", Value: "b"}}, Body: []byte(`{"n":9007199254740993}`), BodyMode: BodyMatchJSON},
				{ID: "second", Method: "POST", RawTarget: "/openai/v1/responses", Body: []byte("exact\n"), BodyMode: BodyMatchRaw},
			},
			Transitions: []TransitionRule{{From: "ready", Event: "request", To: "streaming"}, {From: "streaming", Event: "finish", To: "done"}},
			Faults:      []Fault{{Kind: FaultStatus, Value: "503"}},
			Limits:      Limits{MaxRequests: 2, MaxObjects: 2, MaxBodyBytes: 128, MaxEventBytes: 128, MaxDiagnosticByte: 32, MaxStreamDuration: time.Minute, MaxIdleDuration: time.Second},
		},
		{Name: "anthropic", CredentialID: "credential-anthropic", Limits: testLimits()},
	}}
}

func TestConsumeIsOrderedCellBoundAndComplete(t *testing.T) {
	engine, err := New(testSpec())
	if err != nil {
		t.Fatal(err)
	}
	id := CellID("matrix", "openai")
	request := Request{Method: "post", RawTarget: "/openai/v1/responses?x=%2B&x=", Headers: []Header{{Name: "x-test", Value: "a"}, {Name: "X-Test", Value: "b"}}, Body: []byte(`{"n":9007199254740993}`)}
	got, err := engine.Consume(id, "credential-openai", 1, request, 1)
	if err != nil || got.ID != "first" {
		t.Fatalf("consume first: %+v, %v", got, err)
	}
	if _, err := engine.Consume(id, "credential-openai", 1, request, 0); errorCode(err) != ErrorConsumed {
		t.Fatalf("replay code = %v (%v)", errorCode(err), err)
	}
	if _, err := engine.Consume(id, "credential-openai", 3, request, 0); errorCode(err) != ErrorStaleSequence {
		t.Fatalf("out-of-order code = %v (%v)", errorCode(err), err)
	}
	if err := engine.VerifyComplete(); errorCode(err) != ErrorUnused {
		t.Fatalf("incomplete code = %v (%v)", errorCode(err), err)
	}
	second := Request{Method: "POST", RawTarget: "/openai/v1/responses", Body: []byte("exact\n")}
	if _, err := engine.Consume(id, "credential-openai", 2, second, 1); err != nil {
		t.Fatal(err)
	}
	// The anthropic cell has zero expectations and must not make completion fail.
	if err := engine.VerifyComplete(); err != nil {
		t.Fatal(err)
	}
}

func TestCredentialCannotCrossCells(t *testing.T) {
	engine, err := New(testSpec())
	if err != nil {
		t.Fatal(err)
	}
	id := CellID("matrix", "openai")
	if _, err := engine.Consume(id, "credential-anthropic", 1, Request{}, 0); errorCode(err) != ErrorCrossCell {
		t.Fatalf("cross-cell code = %v (%v)", errorCode(err), err)
	}
	if _, err := engine.Consume(id, "unknown", 1, Request{}, 0); errorCode(err) != ErrorUnknownCredential {
		t.Fatalf("unknown credential code = %v (%v)", errorCode(err), err)
	}
}

func TestMismatchPreservesDuplicateHeadersRawEvidenceAndCursor(t *testing.T) {
	engine, err := New(testSpec())
	if err != nil {
		t.Fatal(err)
	}
	id := CellID("matrix", "openai")
	base := Request{Method: "POST", RawTarget: "/openai/v1/responses?x=%2B&x=", Headers: []Header{{Name: "X-Test", Value: "a"}, {Name: "x-test", Value: "b"}}, Body: []byte(`{"n":9007199254740993}`)}
	mutations := []Request{
		{Method: base.Method, RawTarget: "/openai/v1/responses?x=+&x=", Headers: base.Headers, Body: base.Body},
		{Method: base.Method, RawTarget: base.RawTarget, Headers: []Header{{Name: "X-Test", Value: "a"}, {Name: "Y", Value: "b"}}, Body: base.Body},
		{Method: base.Method, RawTarget: base.RawTarget, Headers: []Header{{Name: "x-test", Value: "b"}, {Name: "X-Test", Value: "a"}}, Body: base.Body},
		{Method: base.Method, RawTarget: base.RawTarget, Headers: base.Headers, Body: []byte(`{"n":9007199254740992}`)},
	}
	for i, mutation := range mutations {
		if _, err := engine.Consume(id, "credential-openai", 1, mutation, 0); errorCode(err) != ErrorMismatch {
			t.Fatalf("mutation %d code = %v (%v)", i, errorCode(err), err)
		}
	}
	if _, err := engine.Consume(id, "credential-openai", 1, base, 0); err != nil {
		t.Fatalf("mismatch advanced cursor: %v", err)
	}
}

func TestJSONSemanticModeRejectsDuplicateKeys(t *testing.T) {
	if jsonSemanticallyEqual([]byte(`{"a":1,"a":2}`), []byte(`{"a":2}`)) {
		t.Fatal("duplicate JSON key was normalized with last-write-wins semantics")
	}
}

func TestCompileRequiresBoundedCells(t *testing.T) {
	_, err := New(ScenarioSpec{Name: "unbounded", Cells: []CellSpec{{Name: "cell", CredentialID: "credential"}}})
	if errorCode(err) != ErrorInvalidSpec {
		t.Fatalf("unbounded cell code = %v (%v)", errorCode(err), err)
	}
}

func TestTransitionGraphAndFaultOwnership(t *testing.T) {
	engine, err := New(testSpec())
	if err != nil {
		t.Fatal(err)
	}
	id := CellID("matrix", "openai")
	if _, err := engine.Transition(id, "credential-openai", "finish"); errorCode(err) != ErrorInvalidTransition {
		t.Fatalf("invalid transition code = %v (%v)", errorCode(err), err)
	}
	first, err := engine.Transition(id, "credential-openai", "request")
	if err != nil || first.Sequence != 1 || first.From != "ready" || first.To != "streaming" {
		t.Fatalf("first transition = %+v, %v", first, err)
	}
	second, err := engine.Transition(id, "credential-openai", "finish")
	if err != nil || second.Sequence != 2 || second.To != "done" {
		t.Fatalf("second transition = %+v, %v", second, err)
	}
	if fault, ok, err := engine.NextFault(id, "credential-openai"); err != nil || !ok || fault.Kind != FaultStatus {
		t.Fatalf("fault = %+v, %v, %v", fault, ok, err)
	}
	bad := ScenarioSpec{Name: "bad", Cells: []CellSpec{{Name: "c", CredentialID: "c", Faults: []Fault{{Kind: "tcp-reset"}}, Limits: testLimits()}}}
	if _, err := New(bad); errorCode(err) != ErrorInvalidSpec {
		t.Fatalf("transport fault accepted: %v", err)
	}
}

func TestInputsAreDeepCopied(t *testing.T) {
	spec := testSpec()
	engine, err := New(spec)
	if err != nil {
		t.Fatal(err)
	}
	spec.Cells[0].Expectations[0].Headers[0].Value = "mutated"
	spec.Cells[0].Expectations[0].Body[0] = 'x'
	id := CellID("matrix", "openai")
	request := Request{Method: "POST", RawTarget: "/openai/v1/responses?x=%2B&x=", Headers: []Header{{Name: "X-Test", Value: "a"}, {Name: "x-test", Value: "b"}}, Body: []byte(`{"n":9007199254740993}`)}
	if _, err := engine.Consume(id, "credential-openai", 1, request, 0); err != nil {
		t.Fatalf("compiled state aliased caller input: %v", err)
	}
}

func TestCheckedAddRejectsOverflow(t *testing.T) {
	if _, ok := checkedAdd(math.MaxUint64, 1); ok {
		t.Fatal("overflow accepted")
	}
}

func TestParallelCellsRemainIsolated(t *testing.T) {
	const count = 128
	spec := ScenarioSpec{Name: "parallel", Cells: make([]CellSpec, count)}
	for i := range spec.Cells {
		name := fmt.Sprintf("cell-%03d", i)
		limits := testLimits()
		limits.MaxRequests = 1
		spec.Cells[i] = CellSpec{Name: name, CredentialID: "credential-" + name, Expectations: []Expectation{{ID: "one", Method: "POST", RawTarget: "/", BodyMode: BodyMatchRaw}}, Limits: limits}
	}
	engine, err := New(spec)
	if err != nil {
		t.Fatal(err)
	}
	var group sync.WaitGroup
	errors := make(chan error, count)
	for i := range spec.Cells {
		group.Add(1)
		go func(i int) {
			defer group.Done()
			name := fmt.Sprintf("cell-%03d", i)
			_, err := engine.Consume(CellID("parallel", name), "credential-"+name, 1, Request{Method: "POST", RawTarget: "/"}, 0)
			errors <- err
		}(i)
	}
	group.Wait()
	close(errors)
	for err := range errors {
		if err != nil {
			t.Fatal(err)
		}
	}
	if err := engine.VerifyComplete(); err != nil {
		t.Fatal(err)
	}
}

func TestBarriersWaitWithoutPolling(t *testing.T) {
	barriers, err := NewBarriers("headers", "first-event")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := barriers.Wait(ctx, "headers"); !errors.Is(err, context.Canceled) {
		t.Fatalf("cancelled wait = %v", err)
	}
	if err := barriers.Reach("headers"); err != nil {
		t.Fatal(err)
	}
	if err := barriers.Wait(context.Background(), "headers"); err != nil {
		t.Fatal(err)
	}
}

func errorCode(err error) ErrorCode {
	var scenarioError *ScenarioError
	if errors.As(err, &scenarioError) {
		return scenarioError.Code
	}
	return ""
}
