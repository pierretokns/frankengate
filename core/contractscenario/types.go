// Package contractscenario provides a deterministic, in-memory scenario engine
// for sealed protocol conformance services. It is a test oracle, not evidence of
// AWS or Bedrock Mantle service parity.
package contractscenario

import (
	"encoding/json"
	"fmt"
	"time"
)

const SchemaV1 = "bedrock-mantle-contract-scenario/v1"

// ErrorCode is stable enough for conformance harnesses to classify failures
// without parsing human-readable diagnostics.
type ErrorCode string

const (
	ErrorUnknownCell       ErrorCode = "unknown_cell"
	ErrorCrossCell         ErrorCode = "cross_cell_identity"
	ErrorUnknownCredential ErrorCode = "unknown_credential"
	ErrorConsumed          ErrorCode = "expectation_consumed"
	ErrorStaleSequence     ErrorCode = "stale_sequence"
	ErrorMismatch          ErrorCode = "request_mismatch"
	ErrorInvalidTransition ErrorCode = "invalid_transition"
	ErrorBudgetExceeded    ErrorCode = "budget_exceeded"
	ErrorCounterOverflow   ErrorCode = "counter_overflow"
	ErrorUnused            ErrorCode = "unused_expectation"
	ErrorInvalidSpec       ErrorCode = "invalid_spec"
)

type ScenarioError struct {
	Code   ErrorCode
	CellID string
	Detail string
}

func (e *ScenarioError) Error() string {
	if e.CellID == "" {
		return fmt.Sprintf("%s: %s", e.Code, e.Detail)
	}
	return fmt.Sprintf("%s for cell %s: %s", e.Code, e.CellID, e.Detail)
}

type Header struct {
	Name  string
	Value string
}

type BodyMatchMode string

const (
	BodyMatchRaw  BodyMatchMode = "raw"
	BodyMatchJSON BodyMatchMode = "json"
)

// Request retains both the raw target and duplicate header fields. This avoids
// weakening signing and HTTP-shape assertions by first normalizing into a map.
type Request struct {
	Method    string
	RawTarget string
	Headers   []Header
	Body      []byte
}

type Expectation struct {
	ID        string
	Sequence  uint64
	Method    string
	RawTarget string
	Headers   []Header
	Body      json.RawMessage
	BodyMode  BodyMatchMode
}

type TransitionRule struct {
	From  string
	Event string
	To    string
}

type FaultKind string

const (
	FaultStatus    FaultKind = "status"
	FaultDelay     FaultKind = "delay"
	FaultMalformed FaultKind = "malformed"
)

// Fault expresses protocol-service intent. TCP, TLS, DNS, and packet faults
// belong to the external transport-fault profile.
type Fault struct {
	Kind     FaultKind
	Value    string
	Duration time.Duration
}

type Limits struct {
	MaxRequests       uint64
	MaxObjects        uint64
	MaxBodyBytes      uint64
	MaxEventBytes     uint64
	MaxDiagnosticByte uint64
	MaxStreamDuration time.Duration
	MaxIdleDuration   time.Duration
}

type CellSpec struct {
	Name         string
	CredentialID string
	InitialState string
	Expectations []Expectation
	Transitions  []TransitionRule
	Faults       []Fault
	Limits       Limits
}

type ScenarioSpec struct {
	Name  string
	Cells []CellSpec
}

type Usage struct {
	Requests  uint64
	Objects   uint64
	BodyBytes uint64
}

type Transition struct {
	Sequence uint64
	CellID   string
	From     string
	To       string
	Event    string
}

type CellSnapshot struct {
	ID                 string
	Name               string
	State              string
	NextExpectation    uint64
	ExpectationCount   uint64
	RemainingFaults    uint64
	Usage              Usage
	TransitionSequence uint64
}
