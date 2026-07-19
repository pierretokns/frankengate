package schemas

import "testing"

func TestTraceGetSpanNilSafe(t *testing.T) {
	var nilTrace *Trace
	if span := nilTrace.GetSpan("span"); span != nil {
		t.Fatalf("nil trace GetSpan returned %v, want nil", span)
	}

	trace := &Trace{Spans: []*Span{nil, &Span{SpanID: "target"}}}
	if span := trace.GetSpan(""); span != nil {
		t.Fatalf("empty span ID = %v, want nil", span)
	}
	if span := trace.GetSpan("missing"); span != nil {
		t.Fatalf("missing span = %v, want nil", span)
	}
	if span := trace.GetSpan("target"); span == nil || span.SpanID != "target" {
		t.Fatalf("target span = %v, want target", span)
	}
}

func TestTraceAndSpanNilMutatorsNoop(t *testing.T) {
	trace := &Trace{}
	trace.AddSpan(nil)
	if len(trace.Spans) != 0 {
		t.Fatalf("nil span was appended: %v", trace.Spans)
	}

	var nilTrace *Trace
	nilTrace.AddSpan(&Span{SpanID: "ignored"})

	var nilSpan *Span
	nilSpan.SetAttribute("key", "value")
	nilSpan.AddEvent(SpanEvent{Name: "event"})
	nilSpan.End(SpanStatusOk, "")
}

func TestNilTraceAccessorsAndLifecycleAreNoop(t *testing.T) {
	var trace *Trace
	if got := trace.GetRequestID(); got != "" {
		t.Fatalf("nil trace request ID = %q, want empty", got)
	}
	if value, ok := trace.GetAttribute("missing"); ok || value != nil {
		t.Fatalf("nil trace attribute = (%v, %v), want (nil, false)", value, ok)
	}

	// These calls occur on error/finalization paths where a tracer may have
	// already been detached. They must never turn an otherwise recoverable
	// provider error into a process panic.
	trace.SetRequestID("ignored")
	trace.SetRequestHeaders(map[string]string{"x-test": "ignored"})
	trace.SetAttribute("key", "ignored")
	trace.SetRedactionReplacements(RedactionPhaseInput, map[string]string{"secret": "[REDACTED]"})
	trace.ApplyRedactionReplacements()
	trace.AppendPluginLogs([]PluginLogEntry{{}})
	trace.Reset()
}
