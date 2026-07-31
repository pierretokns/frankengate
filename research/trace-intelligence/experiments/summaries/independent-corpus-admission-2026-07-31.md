# Independent corpus admission (2026-07-31)

The pinned `experiential-labs/wmh-bird-sql-traces` and
`experiential-labs/wmh-crmarena-traces` snapshots were downloaded to a temporary
cache and audited with `hf_nl2sql_trace_audit.py`. The aggregate receipt is
`experiments/results/independent-corpus-admission-2026-07-31.json`.

## What passed

- BIRD-SQL: 1,993 distinct training traces over 222 tasks and 11 database
  families; all captured training tasks have traces; tool arguments and tool
  results are present; gold-linked deterministic replay is available from the
  pinned external environment; rewards are present for all traces.
- CRMArena: 80 distinct training traces over 45 tasks and 9 task types; all
  captured training tasks have traces; tool arguments and tool results are
  present; gold-linked deterministic replay is available from the pinned
  external environment; rewards are present for all traces.
- File hashes, manifest revisions, malformed-row counts, duplicate span IDs,
  train/test task overlap, and captured-task coverage were checked.

## What failed or remains a loss boundary

- Every OTel span is a root (`nonempty_parent_span_ids = 0`); there is no real
  span graph, parentage, wall-clock timestamp, or latency evidence.
- The published snapshots contain train traces only; test rows are task oracles,
  not observed test trajectories.
- Full assistant narrative/reasoning is not preserved, and the HF snapshot does
  not contain the replay database; replay depends on a separately pinned
  external environment.
- BIRD is SQLite-based and does not establish PostgreSQL/Aurora behavior.
- CRMArena is one CRM organization and CC-BY-NC-4.0; it is a non-commercial
  research control, not an enterprise production-training corpus.

## Admission decision

Admit both corpora for trace mining and deterministic, gold-linked retrospective
replay under their stated claim boundaries. Do **not** admit them as complete
OTel trajectories, natural user behavior, causal skill-improvement evidence,
person-level skill measurements, or Aurora-transfer evidence. The next gate is
family-disjoint replay with sealed outcomes and independent evaluators; no skill,
memory, or backend method should be declared effective from this audit alone.
