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

Run the dependency-free conformance tests with:

```bash
python3 -m unittest discover \
  -s research/trace-intelligence/tests \
  -p 'test_*.py'
```

The frozen environment adds `jsonschema`, `psycopg2-binary`, and `pyarrow` for
artifact validation, governed PostgreSQL experiments, and admitted Parquet manifests.
Core adapters and most tests remain standard-library-only.

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
  full-text, and structured retrieval demonstrably fail.
