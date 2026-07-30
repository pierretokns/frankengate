# Governed bitemporal memory conformance

**Date:** 2026-07-30
**Result:** 15/15 deterministic assertions passed
**Result artifact:** [`bitemporal-memory-conformance-2026-07-30.json`](../results/bitemporal-memory-conformance-2026-07-30.json)
**Result SHA-256:** `e5380cd58fcc90a5270b7ea1e30df79e2e55e3e24361cc950c6ed8a13982be59`

## Question

Can the useful mechanics from Anthropic Dreams, Graphiti, LangMem, and
MemPalace be expressed as one governed relational state machine without making
a graph database or mutable harness file authoritative?

## Method

The arm uses six deterministic synthetic evidence rows. It models:

- evidence carrying tenant, owner, audience, classification, purpose,
  authorization epoch, and policy revision;
- proposal-only extracted candidates with one or more exact evidence IDs;
- human review followed by copy-on-write promotion;
- fact identity as `(fact_key, context)`, rather than text similarity;
- valid time for when a fact applies and system time for when Frankengate knew
  it;
- immutable releases, rollback-as-a-new-release, deletion closure, and
  influence lineage.

The executable oracle is
[`bitemporal_memory_conformance.py`](../../bitemporal_memory_conformance.py).
The arm pins the public Anthropic Dreams beta
`dreaming-2026-04-21`, Graphiti `v0.29.3` at `021d3a5`, LangMem at
`56d8593`, and MemPalace `v3.6.0` at `8ab251c`.

## Results

All 15 assertions passed:

- a later correction closed only the matching contextual fact;
- the old value remained visible at earlier valid time;
- the earlier release retained its original system-time view;
- a fact for a different environment was not treated as a contradiction;
- partial or failed dream output could not promote;
- derived classification was the maximum of its sources;
- derived purposes were the intersection of source purposes;
- an empty purpose intersection and a cross-tenant composition failed closed;
- rollback produced a new release and restored the parent view;
- source deletion invalidated the dependent candidate, release, and export;
- an influenced trace was ineligible as independent validation; and
- a stale authorization epoch returned no rows.

The run created six evidence rows, four candidates, and five releases: three
promotions, one rollback, and one deletion-withdrawal release. One exported
release was invalidated through deletion closure.

## Interpretation

This is positive evidence that the required lifecycle can be represented in
ordinary relational structures. It weakens the case for adopting Graphiti's
graph database as a production dependency: temporal facts, provenance,
contradiction edges, dependency closure, and release membership do not require
a graph server at this scale.

It does **not** establish:

- PostgreSQL transaction, RLS, concurrency, or query-performance behavior;
- equivalence to Anthropic's, Graphiti's, LangMem's, or MemPalace's
  implementations;
- extraction, entailment, consolidation, or retrieval quality;
- memory benefit on held-out tasks or natural enterprise traces; or
- the validity of team- or enterprise-level promotion policy.

The next empirical gate is therefore a Postgres implementation with native RLS,
concurrent promotion/deletion tests, and natural-trace candidate extraction.
Only after that passes should a model or harness projection be evaluated.
