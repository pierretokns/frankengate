# Frankengate trace-intelligence research harness

This directory is the reproducible artifact for the trace-intelligence empirical
program. It is deliberately separate from the production analytics service.

Raw public, gated, and enterprise traces never belong in this repository. Dataset
manifests pin upstream revisions and rights; adapters read explicit external paths;
committed results are aggregate-only. A public trace is not permission to infer a
person's competence, productivity, or collaboration needs.

## Reproduce the committed artifact

The dependency lock covers the tested Python 3.9–3.13 range. PyArrow 21 does
not publish a Python 3.14 wheel, so the upper bound is deliberate:

```bash
cd research/trace-intelligence
uv sync --python 3.9 --frozen
uv run make verify
```

`make verify` runs every unit/conformance test, validates dataset manifests and
canonical governed fixtures, parses every aggregate result, checks that no raw corpus
file is committed, and compiles the Python harness. It performs no network request,
model call, database mutation, or dataset download.

The governed Wisp target is intentionally separate because it mutates a disposable
research schema and requires explicit private inputs:

```bash
make governed-wisp \
  GOVERNED_POSTGRES_DSN='postgresql://…' \
  WISP_CORPUS_ROOT='/private/research-cache/wisp/transcripts'
```

The Hugging Face NL2SQL structural audit is also external-input-only. It verifies
pinned BIRD-SQL and CRMArena task/trace hashes and emits aggregate replay
classification without retaining prompts, SQL, tool arguments, observations,
answers, or identifiers:

```sh
python3 hf_nl2sql_trace_audit.py \
  --bird-root /private/path/bird \
  --bird-manifest configs/datasets/wmh-bird-sql-traces.json \
  --crmarena-root /private/path/crmarena \
  --crmarena-manifest configs/datasets/wmh-crmarena-traces.json \
  --output experiments/results/hf-nl2sql-trace-audit-2026-07-30.json
```

The audited WMH files contain real tool arguments and environment observations,
but not parent-linked/wall-clock OTel or full assistant messages. BIRD is
reconstructable from an external mini-dev archive; CRMArena is reconstructable
from its official SQLite dump and is non-commercial research only. See
[`experiments/summaries/hf-nl2sql-trace-audit-2026-07-30.md`](experiments/summaries/hf-nl2sql-trace-audit-2026-07-30.md).
The domain decision, prior State of AI synthesis, modular skill taxonomy, and
smallest causal sequence are recorded in
[`experiments/summaries/nl2sql-enterprise-skill-domain-assessment-2026-07-30.md`](experiments/summaries/nl2sql-enterprise-skill-domain-assessment-2026-07-30.md).

The causal SQL layer uses a separate, content-free 96-task Defog manifest and
four disposable PostgreSQL databases. The hardened runner requires a governance
subject and an exact current authorization epoch bound to database, scope,
user, team, and virtual key. It parses and allowlists a single read-only query,
authorizes sensitive columns across projections, predicates, joins, grouping,
ordering, windows, functions, and correlated subqueries, fixes the governed
search path, enforces PostgreSQL and result limits, and reports authority,
policy, execution, leakage, benchmark correctness, and strict answer shape
separately:

```sh
DEFOG_SOURCE_ROOT=/private/path/defog-sql-eval \
DEFOG_REPLAY_DSN_TEMPLATE='host=127.0.0.1 port=55432 user=... dbname=fg_defog_{database}' \
DEFOG_RAW_AUDIT_DIR=/private/path/defog-raw-audit \
uv run make defog-sql-conformance
```

The conformance run matched all 95 PostgreSQL-executable tasks: 93 under the
default policy and two only with explicit field-level entitlements. One source
task is invalid PostgreSQL and remains quarantined. All security controls passed
on all four database families. This proves the replay/verifier boundary, not
model quality or causal skill benefit. See
[`experiments/summaries/defog-governed-sql-replay-conformance-2026-07-30.md`](experiments/summaries/defog-governed-sql-replay-conformance-2026-07-30.md).

The content-free four-fold factorial contract can be regenerated without
network or benchmark content:

```sh
uv run make defog-sql-design
```

The first cache-disabled 12-episode mechanics smoke completed with 12/12 valid
authority receipts and zero unauthorized observations. Every arm solved the
same 2/4 tasks, so the expert seed showed no lift. Terminal-protocol failure was
25% for no-skill, 50% for placebo, and 25% for the expert seed, exceeding the
preregistered 10% gate. The 23-task effect screen and hidden family therefore
remain sealed until an arm-independent protocol repair passes a new P0. See
[`experiments/summaries/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md`](experiments/summaries/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md).

An independent, content-free native-tool pilot then ran six paired synthetic
fixtures across the all-tools control, remaining-budget annotations, and
terminal-only tool availability. All variants completed 6/6 expected terminal
actions, establishing that per-request terminal-only switching is compatible
with the pinned MLX/Qwen runtime. Because the controls also passed, this is not
evidence of causal improvement and does not reopen P1. Reproduction and exact
receipts are in
[`experiments/summaries/native-tool-protocol-compliance-pilot-2026-07-30.md`](experiments/summaries/native-tool-protocol-compliance-pilot-2026-07-30.md)
and
[`experiments/summaries/mlx-lm-tool-runtime-audit-2026-07-30.md`](experiments/summaries/mlx-lm-tool-runtime-audit-2026-07-30.md).

The subsequent capability audit found that the current single process keeps
source task IDs, all stage memberships, gold SQL, the candidate executor, and
evaluation code in one address space. P1 and hidden evaluation therefore also
remain blocked on executable solver/broker/resolver/evaluator isolation,
append-once attempt evidence, and separately sealed stage manifests. The exact
minimum architecture and 27 release-gate tests are specified in
[`nl2sql-capability-isolation-design-2026-07-30.md`](../../docs/roadmap/research/nl2sql-capability-isolation-design-2026-07-30.md).

The expanded capability-isolation implementation checkpoint now passes 61/61
component tests. In addition to strict DTO, broker, attempt, evaluator, and
stage-sealing contracts, it includes separate supervisor/evaluator resolver
methods, a fresh-process solver harness with inherited Unix peers, and a
fail-closed OCI profile contract. The frozen profile passed 21 real Linux/runc
enforcement and protocol gates after the runtime test exposed and corrected a
missing safe `fstatfs` syscall and an unsafe host-global `RLIMIT_NPROC`
assumption. A bounded real PostgreSQL 16 audit also
passed distinct candidate/evaluator roles and application names, write denial,
three candidate plus three evaluator-only gold executions, database snapshot
stability, and cleanup. A composition test proves that an empty model preview
can still yield the correct verdict from the full sealed result while candidate
execution remains exactly one. P1 is **not** reopened: the abstract resolver
still needs OS peer credentials, the solver needs a minimal image and
episode-specific identity/two-run isolation, database execution needs
independently signed server/broker receipts, and crash recovery, signed
evaluation/OTel receipts, and the complete 27-gate same-profile run remain.
See
[`experiments/summaries/nl2sql-capability-isolation-component-checkpoint-2026-07-30.md`](experiments/summaries/nl2sql-capability-isolation-component-checkpoint-2026-07-30.md).
The real PostgreSQL slice is recorded separately in
[`experiments/summaries/nl2sql-postgres-role-audit-2026-07-30.md`](experiments/summaries/nl2sql-postgres-role-audit-2026-07-30.md).
The actual Linux profile, discovered failures, and raw-evidence contract are in
[`experiments/summaries/nl2sql-linux-oci-conformance-runbook-2026-07-30.md`](experiments/summaries/nl2sql-linux-oci-conformance-runbook-2026-07-30.md).

Spider2 is admitted only as a later external-validity layer. The source audit
found 135 local Lite tasks across 30 database families, but only 16/24 published
gold SQL files pass the upstream self-check. Of 68 DBT tasks, 59 are strictly
self-consistent and 62 work with deterministic filename aliases; the proposed
cohort is 60. The upstream agent also executes ordinary tool actions twice.
See
[`spider2-local-replay-audit-2026.md`](../../docs/roadmap/research/spider2-local-replay-audit-2026.md).

The real OpenTelemetry E0 arm is also separate because it downloads a pinned
Collector release, binds a disposable loopback receiver, and builds the pinned
Go SDK sender:

```bash
make otel-roundtrip
```

It verifies the release archive and extracted binary, keeps the content-minimized
SDK manifest and Collector storage out of Git, runs lossless and deliberate-drop
pipelines, and writes aggregate JSON only. See
[`experiments/summaries/otel-collector-roundtrip-e0-2026-07-30.md`](experiments/summaries/otel-collector-roundtrip-e0-2026-07-30.md).

See `CITATION.cff`, `LICENSES.md`, each `configs/datasets/*.json` manifest, and each
`experiments/summaries/*.md` interpretation before reusing a result.

The expanded real-history discovery receipt is rebuilt offline from pinned,
content-free manifests:

```bash
make history-discovery
```

It records 359 Hugging Face discovery hits, the indexed and tree-enumerated
native Claude/Codex supply, the first verified near-complete public Claude
home-state tree, portable bundle/partial-home/native archive classifications,
and the observed adjacency of Codex auth files. It commits no prompt, path,
identifier, tool argument/result, secret candidate, or raw trace.

The first executable pilot answers two narrow questions:

1. Can a native SWE-agent conversation be converted into a source-neutral event
   sequence without silently dropping source events?
2. Do label-blind, deterministic friction signals enrich externally failed attempts
   within matched tasks?

It does **not** establish that a trace is diagnostically informative, identify a
decisive failure step, infer a person's skill, or justify a production feature.

## Run the matched pilot

The input is JSON Lines with the public
[`nebius/SWE-agent-trajectories`](https://huggingface.co/datasets/nebius/SWE-agent-trajectories)
schema. Raw traces stay outside Git.

```bash
python3 research/trace-intelligence/tracebench.py pilot \
  --input /tmp/frankengate-nebius-matched-pilot.jsonl \
  --output /tmp/frankengate-nebius-pilot-result.json
```

The command:

- canonicalizes every source turn;
- marks inferred tool calls/results as `reconstructed`, never `observed`;
- emits an information-loss audit;
- computes deterministic Signals-inspired friction features without reading the
  outcome;
- compares a preregistered friction score and a length heuristic at a fixed review
  budget; and
- writes a content-addressed result manifest.

Run the frozen conformance suite with:

```bash
uv run python -m unittest discover \
  -s tests \
  -p 'test_*.py'
```

The frozen environment adds `jsonschema`, `psycopg2-binary`, `pyarrow`, and
`sqlglot` for artifact validation, governed PostgreSQL experiments, admitted
Parquet manifests, and fail-closed SQL parsing. Core adapters and most tests
remain standard-library-only.

The paper-grade design, gates, and later E0–E7 experiments are specified in
[`docs/roadmap/research/trace-intelligence-public-dataset-empirical-program.md`](../../docs/roadmap/research/trace-intelligence-public-dataset-empirical-program.md).

## Governed PostgreSQL lab

The `sql/` directory adds a disposable trace schema to the existing local PostgreSQL
16 + pgvector fixture. It validates RLS-before-FTS/vector retrieval using a
`NOSUPERUSER NOBYPASSRLS` application role. `postgres_loader.py` loads the frozen
Nebius pilot through that restricted role and preserves reconstructed tool proposals
and results as typed events.

The eight-dimensional vectors in this lab encode deterministic signal features. They
exercise PostgreSQL authorization and retrieval composition only; they are not an
embedding-quality experiment.

## Real trace and versioned-memory conformance

`trace_commons_memory_conformance.py` runs over a pinned 4,555,068-byte,
two-session Trace Commons cohort. The raw JSONL stays in an external disposable
cache. The adapter verifies source hashes, native parent edges, and exact
tool-call/result joins; reconstructs only successful writes and edits; and treats a
later read that differs from the last evidenced state as an interval-censored
version gap.

The real run preserved 1,602 records and 1,266/1,266 parent edges. All eight
context-artifact calls joined to results. One memory write exactly matched a read
in the later session, two edits replayed deterministically, and a second artifact
correctly produced one version-gap receipt. These are import and provenance
results—not evidence that the memory was correct or useful.

Re-run with the two manifest-pinned files under an external root:

```sh
TRACE_COMMONS_ROOT=/private/path/trace-commons-cache \
PYTHON=python3 \
make trace-memory
```

The committed aggregate is
[`experiments/summaries/trace-commons-memory-conformance-2026-07-30.md`](experiments/summaries/trace-commons-memory-conformance-2026-07-30.md).

## Full-cohort memory composition

`trace_commons_memory_composition.py` expands the native audit to every one of
the 28 pinned Claude Code histories (57,104,737 verified bytes and 17,991
records). It reproduces the frozen broad context inventory—14 histories, 67
joined operations, 19 reads, 37 writes/edits, and 11 shell/search operations—
then compares deterministic verbatim, context-collapsing latest-only,
contextual-bitemporal, and proposal-only dream mechanics.

The natural cohort yielded only three reconstructable later-read cutoffs, one
changed post-observation case, and one exact cross-session
write-to-later-read transition. The 50 state observations represented 48 unique
contextual revisions. Verbatim and bitemporal storage retained all 48;
latest-only retained 20 and overwrote 28. Online scoring returned one exact
state and two stale states; the two version gaps became known only from the
later read results and therefore could not legitimately cause pre-read
abstention. The contextual arm passed all six same-basename/different-project
placebos, while deliberately context-collapsing latest-only failed by retrieving
foreign-project evidence in three. All 48 evidence-linked dream proposals
remained inactive, but failed-job atomicity was not run and is not claimed.
All preregistered quality-comparison power gates failed. No model-quality,
human-review, causal-usefulness, or enterprise-transfer claim is allowed from
this run.

The source receipt is
[`configs/datasets/trace-commons-memory-full-cohort.json`](configs/datasets/trace-commons-memory-full-cohort.json),
and the implementation-sensitive protocol is
[`configs/experiments/trace-commons-memory-composition-2026.json`](configs/experiments/trace-commons-memory-composition-2026.json).
Raw histories remain outside Git.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 trace_commons_memory_composition.py \
  --manifest configs/datasets/trace-commons-memory-full-cohort.json \
  --experiment-config configs/experiments/trace-commons-memory-composition-2026.json \
  --source-root /private/path/trace-commons-cache \
  --output experiments/results/trace-commons-memory-composition-2026-07-30.json \
  --summary experiments/summaries/trace-commons-memory-composition-2026-07-30.md
```

The aggregate result is
[`experiments/summaries/trace-commons-memory-composition-2026-07-30.md`](experiments/summaries/trace-commons-memory-composition-2026-07-30.md).

The separate PostgreSQL H5 slice binds that content-free aggregate to a
context-preserving procedure and rejects basename-only latest memory. All
26 forced-RLS, role-separation, hidden-test, release, exposure, influence,
withdrawal, and rollback assertions passed on PostgreSQL 16.12 with pgvector
0.8.1; the transaction and residue check left zero study rows. This is a
bounded database-mechanics result, not an Aurora operations or memory-benefit
result. See
[`experiments/summaries/trace-commons-memory-h5-postgres-2026-07-30.md`](experiments/summaries/trace-commons-memory-h5-postgres-2026-07-30.md).

## E2 same-work retrieval factorial

`e2_authorized_retrieval_factorial.py` evaluates a frozen trace-to-trace
same-work pilot over the existing raw CodeTraceBench blocked-test allowlist. It
compares a fixed `2 x 2 x 2` structured/lexical/dense design while retaining an
exact-identifier channel in every arm. The optional dense lane is pinned to
`Qwen/Qwen3-Embedding-0.6B` revision
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`. It encodes documents without a
prompt and queries separately with the frozen instruction `Given an agent
trajectory, retrieve other trajectories attempting the same task`; the result
records the instruction, template, device, and snapshot hashes.

The task identity is a silver positive and hard negatives are metadata-derived.
Neither is a substitute for blinded human task-family adjudication. The quality
factorial runs offline; it references the existing forced-RLS PostgreSQL result as
an independent runtime proof and explicitly does not claim a joint quality/RLS,
deletion, selective-scope latency, or Aurora result. Raw text and vectors remain
outside Git.

Run with external, hash-verified inputs:

```sh
CODETRACEBENCH_FULL=/private/path/bench_manifest.full.parquet \
CODETRACEBENCH_ARCHIVE_ROOT=/private/path/codetracebench-raw \
QWEN3_EMBEDDING_SNAPSHOT=/private/path/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
QWEN3_EMBEDDING_DEVICE=auto \
PYTHON=python3 \
make e2-retrieval
```

`e2_postgres_joint_retrieval.py` then loads those same documents and pinned
1,024-dimensional vectors into the forced-RLS research table in one rollback-only
transaction. All five denied authority scenarios return zero candidates for
base, FTS, trigram, and vector queries. Withdrawal and deletion are filtered
before ranking and the independent post-rollback count is zero.

On this small local cohort, exact pgvector reached `0.6667` Recall@20 at
`3.017 ms` sequential p50. Three-way FTS/trigram/vector RRF reached only
`0.6717` Recall@20, reduced nDCG and MRR, and cost `256.843 ms` p50. The tested
hybrid is therefore rejected; the experiment supports exact pgvector as the
smallest native lane while structured plus dense remains the best offline
quality arm. This is not an Aurora, concurrency, or scale result.

Re-run it only against a disposable schema with SQL migrations 001–004 applied:

```sh
GOVERNED_POSTGRES_DSN=postgresql://... \
CODETRACEBENCH_FULL=/private/path/bench_manifest.full.parquet \
CODETRACEBENCH_ARCHIVE_ROOT=/private/path/codetracebench-raw \
QWEN3_EMBEDDING_SNAPSHOT=/private/path/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
PYTHON=python3 \
make e2-postgres-joint
```

## Claim boundary

The committed experiments currently establish representation, authorization,
structural-selection, and proposal mechanics. They do not yet satisfy the program's
full E0–E7 acceptance gates. In particular:

- a bounded failure-to-later-success episode is a review candidate, not causal repair;
- a stored-trace assertion is a retrospective audit, not a rerun;
- an independent benchmark pass is not longitudinal user learning;
- no public corpus supplies a gold enterprise skill-gap label;
- cross-user suggestions require consent, minimum cohorts, privacy defenses, and
  prospective outcomes; and
- custom embeddings remain gated on a frozen hard slice where exact, PostgreSQL
  full-text, and structured retrieval demonstrably fail; and
- the SQL replay/verifier boundary passes on all 95 executable Defog tasks and
  the no-skill/placebo/expert-seed mechanics factorial has run, but it failed
  its terminal-protocol gate; the independent synthetic pilot proves runtime
  compatibility but not remediation; solver/evaluator capability isolation,
  a fresh P0, trace-mined arms, and the causal quality screen have not run.
