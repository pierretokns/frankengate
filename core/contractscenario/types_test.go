package contractscenario

import (
	"encoding/json"
	"testing"
)

func TestDeterministicCellsAndExactMatching(t *testing.T) {
	a, err := New("s", []CellSpec{{Name:"chat", Expectations: []Expectation{{Method:"POST",Path:"/openai",Headers:map[string]string{"Authorization":"Bearer x"},Body:json.RawMessage(`{"b":2,"a":1}`)}}}}, AuthPolicy{})
	if err != nil { t.Fatal(err) }; b, _ := New("s", []CellSpec{{Name:"chat"}}, AuthPolicy{})
	id := CellID("s","chat"); if id != CellID("s","chat") { t.Fatal("unstable cell id") }; if _,ok:=b.Cell(id); !ok { t.Fatal("cell id is not reproducible") }
	if err:=a.Match(id,Expectation{Method:"post",Path:"/openai",Headers:map[string]string{"authorization":"Bearer x"},Body:json.RawMessage(`{"a":1,"b":2}`)}); err!=nil { t.Fatal(err) }
	if err:=a.Match(id,Expectation{Method:"POST",Path:"/openai",Headers:map[string]string{"Authorization":"Bearer x"},Body:json.RawMessage(`{"a":1,"b":3}`)}); err==nil { t.Fatal("mismatched body accepted") }
}

func TestAuthTransitionsAndFaults(t *testing.T) {
	e,err:=New("s",[]CellSpec{{Name:"c"}},AuthPolicy{Required:true,Credentials:map[string]string{"tok":"agent"}}); if err!=nil{t.Fatal(err)}; id:=CellID("s","c")
	if p,err:=e.Authenticate("tok");err!=nil||p!="agent"{t.Fatalf("auth: %v %q",err,p)}; if _,err:=e.Authenticate("bad");err==nil{t.Fatal("bad credential accepted")}
	if tr,err:=e.Transition(id,"ready","request");err!=nil||tr.Sequence!=1||tr.From!="initial"{t.Fatalf("transition: %+v %v",tr,err)}; if tr,err:=e.Transition(id,"done","response");err!=nil||tr.Sequence!=2{t.Fatalf("transition: %+v %v",tr,err)}
	if err:=e.InstallFaults(id,[]Fault{{Kind:FaultStatus,Value:"503"},{Kind:FaultDrop}});err!=nil{t.Fatal(err)}; if f,ok:=e.NextFault(id);!ok||f.Kind!=FaultStatus{t.Fatalf("fault: %+v %v",f,ok)}; if f,ok:=e.NextFault(id);!ok||f.Kind!=FaultDrop{t.Fatalf("fault: %+v %v",f,ok)}; if _,ok:=e.NextFault(id);ok{t.Fatal("fault program did not exhaust")}
}

func TestBudgetAndBarrierAreDeterministic(t *testing.T) {
	e, err := New("s", []CellSpec{{Name: "c"}}, AuthPolicy{}); if err != nil { t.Fatal(err) }
	id := CellID("s", "c"); var u Usage
	if err := e.Consume(id, Budget{Requests: 1, BodyBytes: 3}, &u, 3, 0); err != nil { t.Fatal(err) }
	if err := e.Consume(id, Budget{Requests: 1, BodyBytes: 3}, &u, 0, 0); err == nil { t.Fatal("request budget not enforced") }
	b := NewBarrier(); if b.Reached("headers") { t.Fatal("barrier reached before signal") }; if err := b.Reach("headers"); err != nil { t.Fatal(err) }; if !b.Reached("headers") { t.Fatal("barrier signal lost") }
}

func TestCancellationAndRetryAccounting(t *testing.T) {
	var c Cancellation; if ok, _ := c.State(); ok { t.Fatal("cancelled before signal") }; c.Cancel("client-close"); c.Cancel("late-error")
	if ok, reason := c.State(); !ok || reason != "client-close" { t.Fatalf("latch: %v %q", ok, reason) }
	r := NewRetryCounter(2); if err := r.Next(); err != nil { t.Fatal(err) }; if err := r.Next(); err != nil { t.Fatal(err) }; if err := r.Next(); err == nil { t.Fatal("retry limit not enforced") }; if r.Attempts() != 2 { t.Fatalf("attempt count: %d", r.Attempts()) }
}

func TestCanonicalTargetPreservesRepeatedAndEmptyValues(t *testing.T) {
	g, err := CanonicalTarget("/invoke?z=last&a=two&a=&a=one"); if err != nil { t.Fatal(err) }
	if g != "/invoke?a=&a=one&a=two&z=last" { t.Fatalf("canonical target: %s", g) }
	if g, err := CanonicalTarget("/"); err != nil || g != "/" { t.Fatalf("root: %q %v", g, err) }
}
