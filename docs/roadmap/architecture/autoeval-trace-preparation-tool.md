# Autoeval Trace Preparation Tool

Status: proposed build design

The Autoeval trace-preparation tool converts an authorized, sanitized incumbent
trajectory into bounded, versioned evaluation cases for retrospective action-value
scoring. It is a compiler and evidence gate, not an observability database, model
runner, or world simulator.

The initial implementation should be a dependency-light file/CLI worker in
`research/trace-intelligence/`, with the same contracts later consumed by the
isolated `analytics-go` binary. It must remain outside the inference availability
path.

## Input and output

Input is a source manifest, never a search-result snippet. A source adapter reads
the complete authorized source record, verifies its source digest and revision, and
emits a canonical trajectory. Initial adapters should cover:

- FrankenGate canonical traces/evidence envelopes;
- CASS session exports, using source paths and explicit line/message boundaries;
- ATIF/OTLP projections, always retaining their projection loss receipt; and
- checked-in research fixtures for deterministic conformance tests.

CASS is a discovery/index surface, not automatically an eval source. Search hits can
omit tool output and are not sufficient to establish a complete trajectory. The
adapter must abstain when it cannot retrieve the source event, tool result, terminal
outcome, privacy receipt, or deletion/authorization lineage required by the case.

Output is an immutable case pack containing:

1. a dataset manifest with dataset/revision/adapter/source digests;
2. one or more canonical trajectories with event IDs and loss receipts;
3. a privacy and evidence-envelope receipt for every durable content reference;
4. deterministic checkpoint records;
5. raw-prefix and neutral-prefix case views where eligible;
6. separate oracle/outcome references that are never included in the candidate
   prompt; and
7. a manifest digest plus exclusion/abstention report.

The tool must not write raw prompts, tool payloads, secrets, private chain of
thought, or unrestricted judge explanations into the case pack. Approved redacted
or vault-controlled content is referenced by digest and policy, not copied into
control-plane rows.

## Pipeline

```text
source manifest
  -> source adapter + digest verification
  -> privacy/evidence admission
  -> canonical trajectory DAG
  -> completeness, mutation, and outcome gates
  -> deterministic checkpoint selector
  -> raw-prefix view + neutral-prefix view
  -> case validation and leakage scan
  -> immutable case pack + lineage manifest
  -> candidate runner / evaluator worker
```

### 1. Admission and normalization

The adapter must preserve branches, retries, fallback attempts, subagent edges,
tool proposal/authorization/execution/result lifecycles, exact tool arguments, and
observed state deltas. It must not flatten a DAG into a plausible chat transcript.
Every event carries an observation status: `observed`, `reconstructed`, `inferred`,
or `missing`. Reconstruction is allowed for format conversion, never for inventing
a tool result, state change, or success outcome.

Reuse `canonical-trajectory-v1`, `AgentEvidenceEnvelope`, and the existing privacy
receipt contract. Do not create a second trace authority or put large event arrays
in `BifrostContext`.

### 2. Eligibility and abstention

An eligible case requires, at minimum:

- an authorized source and active deletion lineage;
- a privacy transform receipt appropriate for evaluation;
- a task boundary and stable task-family label or an explicit unknown label;
- complete bounded tool schemas, proposals, arguments, and observations through the
  selected checkpoint;
- a terminal outcome or an explicitly labelled outcome-missing case;
- no unresolved secret, prompt-injection, authorization, or mutation hazard; and
- no future event leakage into the candidate-visible prefix.

Outcome-missing traces may be retained for coverage, judge-agreement, and
contamination tests, but must not contribute to ranking-fidelity claims. Cases with
irreversible side effects or unverifiable external state become audit-only unless
an independent state-delta receipt exists.

### 3. Checkpoint selection

Select at most five positions per trace using a stable hash and the canonical event
sequence. Always include the first eligible decision and the last eligible decision;
place interior checkpoints at deterministic evenly spaced positions. Store the
selected event IDs, canonical sequence numbers, selection algorithm revision, and
the denominator used. Do not sample checkpoints after seeing candidate scores or
outcomes.

### 4. Neutral reconstruction

For each checkpoint, build two explicit views:

- `raw_prefix`: the incumbent-visible prefix, retained as a diagnostic baseline;
- `neutral_prefix`: task instruction and controller protocol, factual prior tool
  operations with exact arguments, bounded real observations, tool definitions,
  and later user messages, while removing incumbent assistant prose and explicit
  reasoning.

The neutralizer is deterministic and must not summarize with a model. It must emit
an operation-by-operation transform receipt listing retained, removed, normalized,
and missing fields. The candidate sees no future terminal outcome, later incumbent
plan, hidden evaluator label, or private reasoning. The candidate proposes a next
protocol action only; the runner has no real-tool capability.

### 5. Case contract

Each case should include bounded fields equivalent to:

```json
{
  "schema_version": "autoeval-case-v1",
  "case_id": "sha256:...",
  "source_trace_id": "sha256:...",
  "dataset_revision": "...",
  "task_family": "...",
  "checkpoint": {
    "event_id": "...",
    "sequence": 12,
    "position": "interior",
    "selector_revision": "..."
  },
  "view": "neutral_prefix",
  "visible_event_ids": ["..."],
  "candidate_input_digest": "sha256:...",
  "available_tools_digest": "sha256:...",
  "outcome_reference": "sha256:...",
  "observation_status": "complete",
  "missingness": [],
  "contamination": [],
  "privacy_receipt_id": "...",
  "loss_receipt_id": "...",
  "eligibility": "eligible"
}
```

The rendered candidate input is an artifact, not authority. Its digest, transform
revision, and destination policy are recorded; raw text is stored only in an
approved redacted/vault tier. `outcome_reference` resolves outside the prompt and
is available only to the scorer after the candidate action has been recorded.

### 6. Validation and export

The CLI should expose these bounded operations:

```text
tracecase inspect   --manifest cohort.json
tracecase prepare   --manifest cohort.json --output case-pack/
tracecase validate  --pack case-pack/
tracecase split     --pack case-pack --strategy task-family-temporal
tracecase export   --pack case-pack --format atif|otlp|runner-json
tracecase report    --pack case-pack
```

`validate` must fail closed for missing receipts, duplicate IDs, unresolved parent
edges, unbounded content, raw/CoT fields, future leakage, outcome leakage,
cross-tenant joins, non-deterministic checkpoint selection, and silent projection
loss. ATIF/OTLP exports are lossy adapters and must carry their existing loss
receipts; they are not canonical storage.

## Evaluation boundaries

The preparation tool does not decide whether a candidate is better. It produces
cases. The runner records candidate actions without executing tools. The evaluator
then scores action value against a pinned task-family rubric and independent
outcomes. The analytics worker records experiment/run/evaluation/artifact lineage
in PostgreSQL and stores large artifacts through the approved object path.

The evaluator ladder remains:

1. exact/schema/format checks;
2. deterministic tool-trajectory and invariant checks;
3. reference-backed state/outcome checks;
4. frontier-model judge, only when necessary, with prompt-injection isolation,
   calibration cases, cost budget, and abstention.

No judge score alone promotes a route, prompt, skill, memory, or policy. Promotion
requires held-out/temporal/task-family splits, known mutants, random audits,
uncertainty, independent outcomes where applicable, and human approval.

## Build slices

1. **Contract slice:** `autoeval-case-v1`, source manifest, receipts, golden fixtures,
   strict validation, deterministic hashes.
2. **Adapter slice:** canonical FrankenGate and CASS source adapters; ATIF/OTLP
   import/export with loss receipts.
3. **Compiler slice:** eligibility gates, five-position selector, raw/neutral
   transformer, leakage and mutation scans.
4. **Runner slice:** no-tool candidate protocol, model manifest, action capture,
   evaluator input/output separation, and replay-safe artifacts.
5. **Continual slice:** analytics job, dataset membership, run lineage, sampling,
   random-audit manifest, deletion propagation, and report generation.

## Required tests

- canonical DAG branches, retries, fallback, subagent, denied-tool, missing-result,
  cancellation, and state-delta fixtures;
- byte-for-byte repeatability for normalization, selection, neutralization, and pack
  digests;
- secret/PII canaries in nested JSON, tool arguments/results, encoded text, and
  stream chunks;
- no private reasoning or future outcome reaches candidate input;
- raw-prefix and neutral-prefix differ only according to the transform receipt;
- candidate runner cannot invoke a real tool or mutate a real environment;
- task-family, temporal, tenant/user, deletion, authorization, and provenance
  holdouts;
- known-good/bad action mutants and no-op/random negative controls;
- ATIF/OTLP round-trip loss accounting; and
- analytics failure isolation from inference plus idempotent case/run ingestion.

## Non-goals for the first version

- no world simulator;
- no automatic live-route promotion;
- no fine-tuning or model training;
- no private chain-of-thought capture;
- no direct reads from raw observability tables by evaluators; and
- no second trace/eval authority alongside Aurora/PostgreSQL.
