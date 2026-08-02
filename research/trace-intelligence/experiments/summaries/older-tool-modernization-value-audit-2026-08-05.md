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

The pinned modernization receipt was independently revalidated on 2026-08-10:
canonical JSON hashing reproduced its recorded `result_sha256`, the verifier's
recorded receipt hash matched the file, and every published verifier check was
true. This validates receipt integrity; it is not a new corpus execution.

| Port | Measured result | Value for Frankengate |
|---|---|---|
| Termolator/TermSuite-style termhood | Ran under the current `uv` environment on 49 Wisp documents and emitted the configured 3,000 candidates with normalized variants. Termhood recall was `0.358` within a represented schema and `0.015` on the database-held-out transfer diagnostic. | A reproducible, interpretable candidate generator and search-enrichment baseline. It detects vocabulary repeated in an observed corpus; it is not a portable corporate-alias detector. |
| AcronymExpansion-style extraction | A deterministic contextual extractor passed all `8/8` synthetic cases, including undefined and conflicting expansions by abstaining. | A safe candidate-mining primitive with explicit ambiguity/NIL behavior. It is useful for review queues and query expansion after approval. |
| Fork/provenance layer | Both branches preserve upstream attribution and record the source commit, implementation boundary, and `uv` reproducibility status. | Shareable, auditable research artifacts without making obsolete Java/Python stacks gateway dependencies. |

## Follow-up validation on a retrieval task

The port was later used as a **search-only** feature on the WMH-BIRD trace
cohort. On 71 held-out table-retrieval cases, adding train-only termhood
associations changed MRR from `.775660` to `.788514` and Recall@5 from
`.887324` to `.929577`; Recall@1 stayed at `.676056`. This is the clearest
positive downstream result for the modernization, but it is a deeper-recall
effect on a schema/table proxy—not proof of enterprise alias quality. The
replay-negative ranker reached `.812693` MRR, while replay filtering added no
incremental lift because every exposed training negative in that split already
failed the counterfactual. Receipts: [WMH-BIRD termhood retrieval](wmh-bird-exposure-counterfactual-2026-08-09.md)
and [replay-negative reranker](wmh-bird-replay-negative-reranker-2026-08-09.md).

The acronym port's cross-cohort stability probe found 40 valid acronym hashes
across four public trace cohorts, all confined to one cohort, with no shared
exact definition pair. This strengthens the review-only decision: the
extractor can surface local candidates, but raw parenthetical definitions do
not support a global dictionary. See [acronym stability](acronym-cross-cohort-stability-2026-08-09.md).

On a larger public Claude Code history export spanning 432 sessions and 65
project directories, the same ports found 2,249 unique top-term hashes: 777
appeared in at least two projects, while none appeared in all projects. The
acronym extractor found 170 valid acronym hashes, of which 36 crossed a project
boundary; no exact definition pair appeared in every project. This is the
strongest evidence so far that the ports can supply a useful scoped candidate
queue, while still failing to justify a global ontology or alias table. See
[legacy candidate stability on Claude history](claude-history-legacy-candidate-stability-2026-08-09.md).

The follow-up [term-context collision diagnostic](claude-history-term-context-collisions-2026-08-09.md)
found that 543/778 shared top-term hashes had at least one project pair with
less than `.05` lexical-context Jaccard. This turns the old ports into a useful
input to hard-negative mining: recurrence proposes a candidate, while context
separation prevents frequency alone from creating a global alias. It remains a
lexical review signal, not a semantic collision label.

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
