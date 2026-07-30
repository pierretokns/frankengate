# Frankengate trace-intelligence research harness

This directory is the reproducible artifact for the trace-intelligence empirical
program. It is deliberately separate from the production analytics service.

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
