// Package contractscenario provides a deterministic, in-memory contract
// scenario engine for protocol test doubles. It deliberately has no network,
// clock, or provider dependencies; callers own the transport around it.
package contractscenario

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"net/url"
	"sort"
)

const SchemaV1 = "bedrock-mantle-contract-scenario/v1"

// CanonicalTarget returns a stable SigV4-style path and sorted query string.
// It preserves repeated and empty values and percent-encodes each component.
func CanonicalTarget(raw string) (string, error) {
	u, err := url.ParseRequestURI(raw); if err != nil { return "", fmt.Errorf("invalid target: %w", err) }
	path := u.EscapedPath(); if path == "" { path = "/" }
	vals, err := url.ParseQuery(u.RawQuery); if err != nil { return "", fmt.Errorf("invalid query: %w", err) }
	type pair struct{ k, v string }; pairs := make([]pair, 0)
	for k, vs := range vals { if len(vs)==0 { pairs=append(pairs,pair{k,""}) }; for _, v := range vs { pairs=append(pairs,pair{k,v}) } }
	sort.Slice(pairs, func(i,j int) bool { if pairs[i].k==pairs[j].k { return pairs[i].v<pairs[j].v }; return pairs[i].k<pairs[j].k })
	if len(pairs)==0 { return path, nil }; out := path+"?"; for i,p := range pairs { if i>0 { out += "&" }; out += sigv4Escape(p.k)+"="+sigv4Escape(p.v) }; return out,nil
}
func sigv4Escape(s string) string { return strings.ReplaceAll(url.QueryEscape(s), "+", "%20") }

func CanonicalHeaders(headers map[string]string) (string, string, error) {
	if len(headers) == 0 { return "", "", fmt.Errorf("headers are required") }
	type item struct { name, value string }
	items := make([]item, 0, len(headers))
	for k, v := range headers { n := strings.ToLower(strings.TrimSpace(k)); if n == "" { return "", "", fmt.Errorf("empty header name") }; items = append(items, item{n, strings.Join(strings.Fields(v), " ")}) }
	sort.Slice(items, func(i, j int) bool { return items[i].name < items[j].name })
	var b strings.Builder; names := make([]string, len(items)); for i, h := range items { b.WriteString(h.name); b.WriteByte(':'); b.WriteString(h.value); b.WriteByte('\n'); names[i] = h.name }
	return b.String(), strings.Join(names, ";"), nil
}

func CanonicalRequest(method, target string, headers map[string]string, body []byte) (string, error) {
	ct, signed, err := CanonicalHeaders(headers); if err != nil { return "", err }; canon, err := CanonicalTarget(target); if err != nil { return "", err }; sum := sha256.Sum256(body)
	return strings.ToUpper(method)+"\n"+canon+"\n"+ct+"\n"+signed+"\n"+hex.EncodeToString(sum[:]), nil
}

func SigV4Signature(secret, date, region, service, canonical string) string {
	kDate := hmacSHA256([]byte("AWS4"+secret), []byte(date)); kRegion := hmacSHA256(kDate, []byte(region)); kService := hmacSHA256(kRegion, []byte(service)); kSigning := hmacSHA256(kService, []byte("aws4_request")); sum := hmacSHA256(kSigning, []byte(canonical)); return hex.EncodeToString(sum)
}
func hmacSHA256(key, data []byte) []byte { h := hmac.New(sha256.New, key); _, _ = h.Write(data); return h.Sum(nil) }

type CellSpec struct { Name, InitialState string; Expectations []Expectation }
type Cell struct { Name, ID, State string; Expectations []Expectation }

// Expectation is an exact request assertion. Header names are compared
// case-insensitively, while values and JSON body values are exact.
type Expectation struct { Method, Path string; Headers map[string]string; Body json.RawMessage }

type AuthPolicy struct { Required bool; Credentials map[string]string }
type Transition struct { Sequence uint64; CellID, From, To, Event string }

type FaultKind string
const (
	FaultDelay FaultKind = "delay"
	FaultStatus FaultKind = "status"
	FaultDrop FaultKind = "drop"
	FaultMalformed FaultKind = "malformed"
)
type Fault struct { Kind FaultKind; Value string }

type Engine struct { mu sync.Mutex; scenario string; cells map[string]*Cell; auth AuthPolicy; transitions []Transition; faults map[string][]Fault; faultPos map[string]int }

// Budget is a deterministic per-cell execution bound. A zero field means
// unlimited; callers should set every bound required by their scenario.
type Budget struct { Requests, Objects, BodyBytes uint64 }
type Usage struct { Requests, Objects, BodyBytes uint64 }
type Barrier struct { mu sync.Mutex; reached map[string]bool }
type Cancellation struct { mu sync.Mutex; cancelled bool; reason string }
type RetryCounter struct { mu sync.Mutex; attempts, limit uint64 }

func NewBarrier() *Barrier { return &Barrier{reached: make(map[string]bool)} }
func (b *Barrier) Reach(name string) error { if strings.TrimSpace(name)=="" { return fmt.Errorf("barrier name is required") }; b.mu.Lock(); b.reached[name]=true; b.mu.Unlock(); return nil }
func (b *Barrier) Reached(name string) bool { b.mu.Lock(); defer b.mu.Unlock(); return b.reached[name] }
func (c *Cancellation) Cancel(reason string) { c.mu.Lock(); if !c.cancelled { c.cancelled=true; c.reason=reason }; c.mu.Unlock() }
func (c *Cancellation) State() (bool, string) { c.mu.Lock(); defer c.mu.Unlock(); return c.cancelled, c.reason }
func NewRetryCounter(limit uint64) *RetryCounter { return &RetryCounter{limit: limit} }
func (r *RetryCounter) Next() error { r.mu.Lock(); defer r.mu.Unlock(); if r.limit > 0 && r.attempts >= r.limit { return fmt.Errorf("retry budget exceeded") }; r.attempts++; return nil }
func (r *RetryCounter) Attempts() uint64 { r.mu.Lock(); defer r.mu.Unlock(); return r.attempts }

func (e *Engine) Consume(id string, budget Budget, usage *Usage, bodyBytes, objects uint64) error {
	if usage == nil { return fmt.Errorf("usage is required") }
	e.mu.Lock(); defer e.mu.Unlock()
	if _, ok := e.cells[id]; !ok { return fmt.Errorf("unknown cell %q", id) }
	next := Usage{Requests: usage.Requests+1, Objects: usage.Objects+objects, BodyBytes: usage.BodyBytes+bodyBytes}
	if budget.Requests > 0 && next.Requests > budget.Requests { return fmt.Errorf("request budget exceeded") }
	if budget.Objects > 0 && next.Objects > budget.Objects { return fmt.Errorf("object budget exceeded") }
	if budget.BodyBytes > 0 && next.BodyBytes > budget.BodyBytes { return fmt.Errorf("body byte budget exceeded") }
	*usage = next
	return nil
}

func New(scenario string, specs []CellSpec, auth AuthPolicy) (*Engine, error) {
	if strings.TrimSpace(scenario) == "" { return nil, fmt.Errorf("scenario name is required") }
	e := &Engine{scenario: scenario, cells: make(map[string]*Cell), auth: auth, faults: make(map[string][]Fault), faultPos: make(map[string]int)}
	for _, spec := range specs {
		if strings.TrimSpace(spec.Name) == "" { return nil, fmt.Errorf("cell name is required") }
		id := CellID(scenario, spec.Name)
		if _, ok := e.cells[id]; ok { return nil, fmt.Errorf("duplicate cell %q", spec.Name) }
		state := spec.InitialState; if state == "" { state = "initial" }
		exps := append([]Expectation(nil), spec.Expectations...)
		e.cells[id] = &Cell{Name: spec.Name, ID: id, State: state, Expectations: exps}
	}
	return e, nil
}

func CellID(scenario, cell string) string { h := sha256.Sum256([]byte(scenario+"\x00"+cell)); return "cell_" + hex.EncodeToString(h[:16]) }
func (e *Engine) Cell(id string) (Cell, bool) { e.mu.Lock(); defer e.mu.Unlock(); c, ok := e.cells[id]; if !ok { return Cell{}, false }; return *c, true }
func (e *Engine) Match(id string, got Expectation) error { e.mu.Lock(); defer e.mu.Unlock(); c, ok := e.cells[id]; if !ok { return fmt.Errorf("unknown cell %q", id) }; for _, want := range c.Expectations { if expectationEqual(want, got) { return nil } }; return fmt.Errorf("request did not match any expectation for cell %s", c.Name) }

func expectationEqual(a, b Expectation) bool {
	if !strings.EqualFold(a.Method,b.Method) || a.Path != b.Path || len(a.Headers) != len(b.Headers) || !jsonEqual(a.Body,b.Body) { return false }
	for k,v := range a.Headers { found := false; for kb,vb := range b.Headers { if strings.EqualFold(k,kb) && v == vb { found=true; break } }; if !found { return false } }
	return true
}
func jsonEqual(a,b []byte) bool { if len(a)==0 || len(b)==0 { return string(a)==string(b) }; var x,y any; if json.Unmarshal(a,&x)!=nil || json.Unmarshal(b,&y)!=nil { return string(a)==string(b) }; return deepEqual(x,y) }
func deepEqual(a,b any) bool { aj,_:=json.Marshal(a); bj,_:=json.Marshal(b); return string(aj)==string(bj) }

func (e *Engine) Authenticate(token string) (string, error) { e.mu.Lock(); defer e.mu.Unlock(); if !e.auth.Required && len(e.auth.Credentials)==0 { return "", nil }; principal, ok := e.auth.Credentials[token]; if !ok { return "", fmt.Errorf("synthetic authentication failed") }; return principal,nil }

func (e *Engine) Transition(id, to, event string) (Transition,error) { e.mu.Lock(); defer e.mu.Unlock(); c,ok:=e.cells[id]; if !ok{return Transition{},fmt.Errorf("unknown cell %q",id)}; if strings.TrimSpace(to)==""||strings.TrimSpace(event)=="" { return Transition{},fmt.Errorf("transition state and event are required") }; e.transitions=append(e.transitions,Transition{Sequence:uint64(len(e.transitions)+1),CellID:id,From:c.State,To:to,Event:event}); c.State=to; return e.transitions[len(e.transitions)-1],nil }
func (e *Engine) Transitions() []Transition { e.mu.Lock(); defer e.mu.Unlock(); return append([]Transition(nil),e.transitions...) }
func (e *Engine) InstallFaults(id string, faults []Fault) error { e.mu.Lock(); defer e.mu.Unlock(); if _,ok:=e.cells[id]; !ok{return fmt.Errorf("unknown cell %q",id)}; e.faults[id]=append([]Fault(nil),faults...); e.faultPos[id]=0; return nil }
func (e *Engine) NextFault(id string) (Fault,bool) { e.mu.Lock(); defer e.mu.Unlock(); fs:=e.faults[id]; p:=e.faultPos[id]; if p>=len(fs){return Fault{},false}; e.faultPos[id]=p+1; return fs[p],true }
