# FrankenGate Analytics

`frankengate-analytics` is the separately deployed Go analytics binary for
trace-native continual evaluation. It belongs in this repository because it
shares the canonical trajectory, privacy/evidence, ClickHouse, and rubric
contracts with FrankenGate. It is not linked into the gateway inference binary.

## What this beta does

1. Admits authorized canonical traces only when privacy, deletion, provenance,
   and loss receipts are present.
2. Removes raw content from the durable representation; only bounded metadata
   and digests are written to ClickHouse.
3. Preserves tool, skill, knowledge-base, retry, fallback, branch, and state
   lineage as typed events.
4. Validates task-family rubrics and scores structured candidate assessments.
5. Records hard violations and abstentions instead of converting missing state
   into a confident score.

This is a retrospective evaluator. It does not execute tools, capture private
chain-of-thought, promote live routes, or establish causal claims about an
external world.

For ingestion interoperability, use OTEL as the correlation envelope and keep
native producer adapters for semantics that OTEL does not guarantee. The
source matrix, Cloud Code/Codex/Strands differences, CASS adapter notes, and
bounded nested-field policy are documented in
`../docs/roadmap/research/trace-format-unification-and-otel-interop.md`.

## Run locally

```bash
go run ./cmd/frankengate-analytics --check
docker compose -f ../docker-compose.yml up clickhouse # if available
CLICKHOUSE_ADDR=localhost:8123 \
  go run ./cmd/frankengate-analytics
```

The service exposes `/healthz`, `/readyz`, `POST /v1/traces`,
`POST /v1/evaluations`, and `GET /v1/reports/evaluations`. Configure
`ANALYTICS_WORKER_TOKEN` in any shared or
enterprise deployment. Every request requires `X-Tenant-ID` and the body tenant
must match it.

The report endpoint is tenant-scoped and accepts an optional `trace_id` query
parameter. It reads ClickHouse `FINAL` rows so retried trace/evaluation writes
do not inflate counts.

## Required trace guarantees

The input must use `canonical-trajectory-v1` and include an active source
authorization, source revision/digest, privacy receipt, deletion lineage, and
zero silent projection loss. A missing terminal outcome is retained as an abstention/coverage case,
not as evidence for ranking fidelity. Raw prompts, tool arguments/results,
secrets, and private reasoning are never persisted.

## Rubrics

Rubrics are task-family contracts, not generic quality prompts. They define the
terminal success predicate, visible state, permitted action grammar, hard
authorization/safety constraints, weighted action-value dimensions, evidence
policy, and abstention conditions. The recommended dimensions are goal
progress, precondition correctness, information gain, risk/recoverability, and
cost. See:

- `../docs/roadmap/research/autoeval-rubric-authoring-and-calibration.md`
- `../docs/roadmap/architecture/autoeval-trace-preparation-tool.md`
- `../docs/roadmap/research/trace-autoeval-article-findings.md`

Skill calls are scored for applicability, authorization, grounding, and task
progress—not for merely invoking a skill. Retrieval/knowledge-base actions are
scored for query specificity, relevance, freshness, citation grounding, and
whether stale or unobserved evidence is treated as fact.

## Enterprise beta gates

Before accepting a corporate cohort, run privacy canaries, deletion/tenant
isolation tests, future/outcome leakage checks, known-good/no-op/random/bad
mutants, executed next-action references, and model/harness/skill/KB holdouts.
Publish per-slice coverage, abstention, calibration, action-value ranking
agreement, regret, and cost. Never publish a pooled headline without its
support matrix.
