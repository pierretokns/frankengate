# Older-tool modernization value audit

This audit answers a narrower question than efficacy: what did the published
modernizations buy us, and what did they fail to establish?

## Scope

Only two projects were published as Frankengate forks:

- the Termolator/TermSuite-style termhood port;
- the AcronymExpansion-style contextual acronym port.

AgentRx, AgentEvals, SkillGen, RHO, GLiNER, and related projects were pinned or
reimplemented for mechanics checks; they were not silently relabeled as
upstream forks.

## Value that was actually measured

| Port | Measured result | Value for Frankengate |
|---|---|---|
| Termolator/TermSuite-style termhood | Ran under the current `uv` environment on 49 Wisp documents and emitted the configured 3,000 candidates with normalized variants. Termhood recall was `0.358` within a represented schema and `0.015` on the database-held-out transfer diagnostic. | A reproducible, interpretable candidate generator and search-enrichment baseline. It detects vocabulary repeated in an observed corpus; it is not a portable corporate-alias detector. |
| AcronymExpansion-style extraction | A deterministic contextual extractor passed all `8/8` synthetic cases, including undefined and conflicting expansions by abstaining. | A safe candidate-mining primitive with explicit ambiguity/NIL behavior. It is useful for review queues and query expansion after approval. |
| Fork/provenance layer | Both branches preserve upstream attribution and record the source commit, implementation boundary, and `uv` reproducibility status. | Shareable, auditable research artifacts without making obsolete Java/Python stacks gateway dependencies. |

## Value that was *not* established

These runs did not establish byte-for-byte upstream equivalence, enterprise
term or alias precision, cross-company transfer, improved NL2SQL execution,
better user outcomes, or skill improvement. The public cohort contains neither
real corporate reformulation labels nor wrong-system/temporal hard negatives.

The 3,000-candidate count is a configured cap, not a quality score. The `8/8`
acronym result is a synthetic capability probe, not an enterprise benchmark.

## Integration decision

Keep both ports offline and behind review. They may produce candidate terms,
variant groups, and acronym expansions for a search projection. They must not:

1. auto-write ontology or alias edges;
2. replace structured identifiers or schema evidence;
3. change the embedding model; or
4. run on the inference hot path.

Promotion requires a license-cleared internal corpus with reviewed aliases,
NIL/ambiguity labels, same-scope wrong-system negatives, temporal replacements,
retrieval impact, reviewer cost, and downstream task outcomes. Until that gate
is met, their value is bounded to reproducibility, candidate generation, and
experimental baselines.

## Receipts

- [modern port receipt](../results/modern-term-acronym-port-wisp-2026-08-04.json)
- [modern port verification](../results/modern-term-acronym-port-wisp-2026-08-04-verification.json)
- [held-out NL2SQL diagnostic](nl2sql-modern-vocabulary-benchmark-2026-08-04.md)
- [fork manifest](../../ports/fork-manifest.json)
- [upstream porting policy](../../ports/UPSTREAM_PORTING.md)
