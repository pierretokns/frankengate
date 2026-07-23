package contractscenario

import (
	"bytes"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
	"sync"
)

const (
	maxScenarioCells       = 1024
	maxCellExpectations    = 10_000
	maxCellTransitionRules = 10_000
	maxCellFaults          = 10_000
)

type compiledTransition struct {
	to string
}

type cell struct {
	id             string
	name           string
	credentialHash [sha256.Size]byte
	state          string
	expectations   []Expectation
	next           uint64
	transitions    map[string]compiledTransition
	transitionSeq  uint64
	faults         []Fault
	faultPos       uint64
	limits         Limits
	usage          Usage
}

type Engine struct {
	mu          sync.Mutex
	scenario    string
	cells       map[string]*cell
	credentials map[[sha256.Size]byte]string
	transitions []Transition
}

func New(spec ScenarioSpec) (*Engine, error) {
	if strings.TrimSpace(spec.Name) == "" {
		return nil, invalidSpec("scenario name is required")
	}
	if len(spec.Cells) == 0 || len(spec.Cells) > maxScenarioCells {
		return nil, invalidSpec(fmt.Sprintf("scenario must contain 1..%d cells", maxScenarioCells))
	}
	e := &Engine{
		scenario:    spec.Name,
		cells:       make(map[string]*cell, len(spec.Cells)),
		credentials: make(map[[sha256.Size]byte]string, len(spec.Cells)),
	}
	for _, input := range spec.Cells {
		if err := e.addCell(input); err != nil {
			return nil, err
		}
	}
	return e, nil
}

func invalidSpec(detail string) error {
	return &ScenarioError{Code: ErrorInvalidSpec, Detail: detail}
}

func (e *Engine) addCell(input CellSpec) error {
	if strings.TrimSpace(input.Name) == "" || input.CredentialID == "" {
		return invalidSpec("cell name and synthetic credential are required")
	}
	if len(input.Expectations) > maxCellExpectations || len(input.Transitions) > maxCellTransitionRules || len(input.Faults) > maxCellFaults {
		return invalidSpec(fmt.Sprintf("cell %q exceeds compiled collection limits", input.Name))
	}
	if !bounded(input.Limits) {
		return invalidSpec(fmt.Sprintf("cell %q must set every execution limit", input.Name))
	}
	id := CellID(e.scenario, input.Name)
	if _, exists := e.cells[id]; exists {
		return invalidSpec(fmt.Sprintf("duplicate cell %q", input.Name))
	}
	credentialHash := sha256.Sum256([]byte(input.CredentialID))
	if _, exists := e.credentials[credentialHash]; exists {
		return invalidSpec("synthetic credentials must be unique per cell")
	}
	state := input.InitialState
	if state == "" {
		state = "initial"
	}
	expectations := make([]Expectation, len(input.Expectations))
	for i := range input.Expectations {
		expectations[i] = cloneExpectation(input.Expectations[i])
	}
	for i := range expectations {
		if expectations[i].ID == "" {
			return invalidSpec(fmt.Sprintf("cell %q expectation %d has no ID", input.Name, i+1))
		}
		wantSequence := uint64(i + 1)
		if expectations[i].Sequence == 0 {
			expectations[i].Sequence = wantSequence
		}
		if expectations[i].Sequence != wantSequence {
			return invalidSpec(fmt.Sprintf("cell %q expectation sequence must be contiguous", input.Name))
		}
		if expectations[i].BodyMode == "" {
			expectations[i].BodyMode = BodyMatchRaw
		}
		if expectations[i].BodyMode != BodyMatchRaw && expectations[i].BodyMode != BodyMatchJSON {
			return invalidSpec(fmt.Sprintf("cell %q expectation %q has unknown body mode", input.Name, expectations[i].ID))
		}
	}
	transitions := make(map[string]compiledTransition, len(input.Transitions))
	for _, rule := range input.Transitions {
		if rule.From == "" || rule.Event == "" || rule.To == "" {
			return invalidSpec(fmt.Sprintf("cell %q has incomplete transition", input.Name))
		}
		key := transitionKey(rule.From, rule.Event)
		if _, exists := transitions[key]; exists {
			return invalidSpec(fmt.Sprintf("cell %q has ambiguous transition %s/%s", input.Name, rule.From, rule.Event))
		}
		transitions[key] = compiledTransition{to: rule.To}
	}
	for _, fault := range input.Faults {
		if !validFault(fault) {
			return invalidSpec(fmt.Sprintf("cell %q has invalid fault %q", input.Name, fault.Kind))
		}
	}
	e.cells[id] = &cell{
		id:             id,
		name:           input.Name,
		credentialHash: credentialHash,
		state:          state,
		expectations:   expectations,
		transitions:    transitions,
		faults:         append([]Fault(nil), input.Faults...),
		limits:         input.Limits,
	}
	e.credentials[credentialHash] = id
	return nil
}

func bounded(limits Limits) bool {
	return limits.MaxRequests > 0 && limits.MaxObjects > 0 && limits.MaxBodyBytes > 0 &&
		limits.MaxEventBytes > 0 && limits.MaxDiagnosticByte > 0 &&
		limits.MaxStreamDuration > 0 && limits.MaxIdleDuration > 0
}

func validFault(fault Fault) bool {
	switch fault.Kind {
	case FaultStatus, FaultMalformed:
		return fault.Duration == 0
	case FaultDelay:
		return fault.Duration > 0
	default:
		return false
	}
}

func CellID(scenario, name string) string {
	sum := sha256.Sum256([]byte(scenario + "\x00" + name))
	return "cell_" + hex.EncodeToString(sum[:16])
}

// Authenticate returns the cell bound to the synthetic credential. Hashes are
// compared in constant time to avoid turning the conformance service into a
// credential-enumeration oracle.
func (e *Engine) Authenticate(credential string) (string, error) {
	hash := sha256.Sum256([]byte(credential))
	e.mu.Lock()
	defer e.mu.Unlock()
	for candidate, id := range e.credentials {
		if subtle.ConstantTimeCompare(hash[:], candidate[:]) == 1 {
			return id, nil
		}
	}
	return "", &ScenarioError{Code: ErrorUnknownCredential, Detail: "synthetic authentication failed"}
}

// Consume matches and atomically consumes exactly the next expectation.
func (e *Engine) Consume(cellID, credential string, sequence uint64, request Request, objects uint64) (Expectation, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	c, err := e.authorizedCell(cellID, credential)
	if err != nil {
		return Expectation{}, err
	}
	if sequence <= c.next {
		return Expectation{}, &ScenarioError{Code: ErrorConsumed, CellID: cellID, Detail: fmt.Sprintf("sequence %d was already consumed", sequence)}
	}
	wantSequence := c.next + 1
	if sequence != wantSequence {
		return Expectation{}, &ScenarioError{Code: ErrorStaleSequence, CellID: cellID, Detail: fmt.Sprintf("expected sequence %d, got %d", wantSequence, sequence)}
	}
	if c.next >= uint64(len(c.expectations)) {
		return Expectation{}, &ScenarioError{Code: ErrorConsumed, CellID: cellID, Detail: "all expectations were consumed"}
	}
	requests, ok := checkedAdd(c.usage.Requests, 1)
	if !ok {
		return Expectation{}, &ScenarioError{Code: ErrorCounterOverflow, CellID: cellID, Detail: "request counter overflow"}
	}
	objectCount, ok := checkedAdd(c.usage.Objects, objects)
	if !ok {
		return Expectation{}, &ScenarioError{Code: ErrorCounterOverflow, CellID: cellID, Detail: "object counter overflow"}
	}
	bodyBytes, ok := checkedAdd(c.usage.BodyBytes, uint64(len(request.Body)))
	if !ok {
		return Expectation{}, &ScenarioError{Code: ErrorCounterOverflow, CellID: cellID, Detail: "body byte counter overflow"}
	}
	nextUsage := Usage{Requests: requests, Objects: objectCount, BodyBytes: bodyBytes}
	if detail := overLimit(c.limits, nextUsage); detail != "" {
		return Expectation{}, &ScenarioError{Code: ErrorBudgetExceeded, CellID: cellID, Detail: detail}
	}
	want := c.expectations[c.next]
	if detail := mismatch(want, request); detail != "" {
		return Expectation{}, &ScenarioError{Code: ErrorMismatch, CellID: cellID, Detail: boundDiagnostic(detail, c.limits.MaxDiagnosticByte)}
	}
	c.next++
	c.usage = nextUsage
	return cloneExpectation(want), nil
}

func (e *Engine) authorizedCell(cellID, credential string) (*cell, error) {
	c, exists := e.cells[cellID]
	if !exists {
		return nil, &ScenarioError{Code: ErrorUnknownCell, CellID: cellID, Detail: "cell does not exist"}
	}
	hash := sha256.Sum256([]byte(credential))
	if subtle.ConstantTimeCompare(hash[:], c.credentialHash[:]) != 1 {
		if _, known := e.credentials[hash]; known {
			return nil, &ScenarioError{Code: ErrorCrossCell, CellID: cellID, Detail: "credential belongs to another cell"}
		}
		return nil, &ScenarioError{Code: ErrorUnknownCredential, CellID: cellID, Detail: "synthetic authentication failed"}
	}
	return c, nil
}

func overLimit(limits Limits, usage Usage) string {
	if limits.MaxRequests > 0 && usage.Requests > limits.MaxRequests {
		return "request limit exceeded"
	}
	if limits.MaxObjects > 0 && usage.Objects > limits.MaxObjects {
		return "object limit exceeded"
	}
	if limits.MaxBodyBytes > 0 && usage.BodyBytes > limits.MaxBodyBytes {
		return "body byte limit exceeded"
	}
	return ""
}

func checkedAdd(left, right uint64) (uint64, bool) {
	result := left + right
	return result, result >= left
}

func mismatch(want Expectation, got Request) string {
	if !strings.EqualFold(want.Method, got.Method) {
		return fmt.Sprintf("method: want %q got %q", want.Method, got.Method)
	}
	if want.RawTarget != got.RawTarget {
		return fmt.Sprintf("raw target: want %q got %q", want.RawTarget, got.RawTarget)
	}
	if !headersEqual(want.Headers, got.Headers) {
		return "headers differ, including duplicate values or order"
	}
	switch want.BodyMode {
	case BodyMatchRaw:
		if !bytes.Equal(want.Body, got.Body) {
			return "raw body differs"
		}
	case BodyMatchJSON:
		if !jsonSemanticallyEqual(want.Body, got.Body) {
			return "JSON body differs"
		}
	}
	return ""
}

func headersEqual(want, got []Header) bool {
	if len(want) != len(got) {
		return false
	}
	for i := range want {
		if !strings.EqualFold(want[i].Name, got[i].Name) || want[i].Value != got[i].Value {
			return false
		}
	}
	return true
}

func jsonSemanticallyEqual(a, b []byte) bool {
	left, err := decodeStrictJSON(a)
	if err != nil {
		return false
	}
	right, err := decodeStrictJSON(b)
	if err != nil {
		return false
	}
	leftJSON, _ := json.Marshal(left)
	rightJSON, _ := json.Marshal(right)
	return bytes.Equal(leftJSON, rightJSON)
}

func decodeStrictJSON(input []byte) (any, error) {
	decoder := json.NewDecoder(bytes.NewReader(input))
	decoder.UseNumber()
	value, err := decodeJSONValue(decoder)
	if err != nil {
		return nil, err
	}
	if _, err := decoder.Token(); err != io.EOF {
		if err == nil {
			return nil, fmt.Errorf("trailing JSON value")
		}
		return nil, err
	}
	return value, nil
}

func decodeJSONValue(decoder *json.Decoder) (any, error) {
	token, err := decoder.Token()
	if err != nil {
		return nil, err
	}
	delim, isDelimiter := token.(json.Delim)
	if !isDelimiter {
		return token, nil
	}
	switch delim {
	case '{':
		object := make(map[string]any)
		for decoder.More() {
			keyToken, err := decoder.Token()
			if err != nil {
				return nil, err
			}
			key, ok := keyToken.(string)
			if !ok {
				return nil, fmt.Errorf("JSON object key is not a string")
			}
			if _, exists := object[key]; exists {
				return nil, fmt.Errorf("duplicate JSON key %q", key)
			}
			value, err := decodeJSONValue(decoder)
			if err != nil {
				return nil, err
			}
			object[key] = value
		}
		end, err := decoder.Token()
		if err != nil || end != json.Delim('}') {
			return nil, fmt.Errorf("unterminated JSON object")
		}
		return object, nil
	case '[':
		array := make([]any, 0)
		for decoder.More() {
			value, err := decodeJSONValue(decoder)
			if err != nil {
				return nil, err
			}
			array = append(array, value)
		}
		end, err := decoder.Token()
		if err != nil || end != json.Delim(']') {
			return nil, fmt.Errorf("unterminated JSON array")
		}
		return array, nil
	default:
		return nil, fmt.Errorf("unexpected JSON delimiter %q", delim)
	}
}

func boundDiagnostic(detail string, limit uint64) string {
	if limit == 0 || uint64(len(detail)) <= limit {
		return detail
	}
	return detail[:limit]
}

func cloneExpectation(input Expectation) Expectation {
	output := input
	output.Headers = append([]Header(nil), input.Headers...)
	output.Body = append(json.RawMessage(nil), input.Body...)
	return output
}

func transitionKey(from, event string) string {
	return from + "\x00" + event
}

func (e *Engine) Transition(cellID, credential, event string) (Transition, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	c, err := e.authorizedCell(cellID, credential)
	if err != nil {
		return Transition{}, err
	}
	rule, exists := c.transitions[transitionKey(c.state, event)]
	if !exists {
		return Transition{}, &ScenarioError{Code: ErrorInvalidTransition, CellID: cellID, Detail: fmt.Sprintf("event %q is invalid from state %q", event, c.state)}
	}
	c.transitionSeq++
	transition := Transition{Sequence: c.transitionSeq, CellID: cellID, From: c.state, To: rule.to, Event: event}
	c.state = rule.to
	e.transitions = append(e.transitions, transition)
	return transition, nil
}

func (e *Engine) NextFault(cellID, credential string) (Fault, bool, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	c, err := e.authorizedCell(cellID, credential)
	if err != nil {
		return Fault{}, false, err
	}
	if c.faultPos >= uint64(len(c.faults)) {
		return Fault{}, false, nil
	}
	fault := c.faults[c.faultPos]
	c.faultPos++
	return fault, true, nil
}

func (e *Engine) Snapshot(cellID string) (CellSnapshot, bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	c, exists := e.cells[cellID]
	if !exists {
		return CellSnapshot{}, false
	}
	return CellSnapshot{
		ID:                 c.id,
		Name:               c.name,
		State:              c.state,
		NextExpectation:    c.next + 1,
		ExpectationCount:   uint64(len(c.expectations)),
		RemainingFaults:    uint64(len(c.faults)) - c.faultPos,
		Usage:              c.usage,
		TransitionSequence: c.transitionSeq,
	}, true
}

func (e *Engine) Transitions() []Transition {
	e.mu.Lock()
	defer e.mu.Unlock()
	return append([]Transition(nil), e.transitions...)
}

func (e *Engine) VerifyComplete() error {
	e.mu.Lock()
	defer e.mu.Unlock()
	ids := make([]string, 0, len(e.cells))
	for id := range e.cells {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		c := e.cells[id]
		if c.next != uint64(len(c.expectations)) {
			return &ScenarioError{Code: ErrorUnused, CellID: id, Detail: fmt.Sprintf("%d expectation(s) remain", uint64(len(c.expectations))-c.next)}
		}
	}
	return nil
}
