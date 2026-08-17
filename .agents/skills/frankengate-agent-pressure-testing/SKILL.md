---
name: frankengate-agent-pressure-testing
description: Exercise FrankenGate MCP and agent-gateway limits under fan-out, cancellation, tool failure, result-size, and mixed direct/agent load. Use when validating hundreds of always-on agents, MCP tool admission, agent HPA signals, goroutine safety, or agent memory pressure.
---

# FrankenGate agent pressure testing

## Quick start

Start with deterministic tools and no live model quota. Vary:

- concurrent top-level agent requests;
- 1, 16, and 128 tool calls per model turn;
- slow, failing, panicking, oversized, and non-cooperative tools;
- direct inference mixed with agent work;
- cancellation while queued, while executing, and between LLM turns.

```bash
go test -race ./core/mcp -count=1
go test -race ./core/mcp -run 'Agent|Tool|Admission|Pressure' -count=1
```

## Invariants

- Per-request fan-out, process-wide tool slots, worker admission, tool-call
  arguments, retained results, conversation history, and total execution time
  remain bounded.
- Canceled waiters never enter a tool callback. Running callbacks either honor
  context or are isolated in a bounded worker set; their eventual return
  releases capacity.
- Results preserve model tool-call order even when execution is parallel.
- Panics become bounded tool errors and cannot strand admission slots.
- Mixed direct and agent traffic exposes separate active gauges and does not
  let agent work starve ordinary inference.

## Evidence

Capture active/waiting admission gauges, cancellation and timeout counters,
tool error classes, latency by tool, goroutines, RSS, and provider/PostgreSQL
pressure. Repeat the same wave after cancellation and verify all gauges and
capacity return to baseline. Test the configured HPA metric freshness and
missing-metric behavior before relying on scale-out.

Use `tests/artifacts/perf/agent-worker-pressure-*.md` as the result format.
Do not infer “hundreds of agents” from a unit test: run a mixed workload in a
multi-pod Kubernetes environment before making that claim.
