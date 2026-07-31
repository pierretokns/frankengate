# BIRD-SQL recorded-trace replay (2026-07-31)

The pinned `experiential-labs/wmh-bird-sql-traces` training traces were replayed
against the upstream harness's pinned BIRD mini-dev v2 SQLite materialization.
The runner is `research/trace-intelligence/bird_sql_trace_replay.py`; the
aggregate receipt is `experiments/results/bird-sql-trace-replay-2026-07-31.json`.

## Receipt

- 1,993 traces contained metadata and joined to a task/database.
- 1,978 gold queries executed under the bounded evaluator; 15 exceeded the
  10,000-row/8 MiB result bound.
- 1,977 recorded candidate answers were parseable as one read-only `SELECT` or
  `WITH` statement; one was not.
- 1,976 candidates executed; one candidate exceeded the result bound.
- 811 candidate results matched the first pinned gold result exactly and 833
  matched after ignoring row order. The remaining mismatches are not evidence
  of model failure: BIRD's released grader may accept alternative SQL and this
  verifier intentionally compares against one gold result with strict column,
  order, and multiplicity semantics.
- All candidate and gold execution was read-only, bounded, and performed from
  fresh immutable database materializations. No prompts, SQL, rows, or trace
  identifiers were emitted in the receipt.

## Interpretation boundary

This closes an executed retrospective replay check for BIRD-SQL, not a causal
skill-improvement experiment. It validates that recorded actions can be joined
to a resettable environment and evaluated against outcomes. The OTel export still
has no parentage or real latency, and SQLite replay does not establish
PostgreSQL/Aurora transfer. A fair skill experiment must now mine procedures
from a family-disjoint evidence split and evaluate no-skill, placebo, expert, and
method arms with a sealed independent evaluator.
