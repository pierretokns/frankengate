# Embedding versus model cascade decision (2026-08-09)

This memo combines the independent MATM cascade receipts with the newer
WMH-BIRD identifier/reranker results. It is an architecture decision, not a
claim that any public proxy represents enterprise semantics.

## Evidence

| Stage | Evidence | Decision |
|---|---|---|
| Exact/structured retrieval | Identifier-aware public rankers outperform dense retrieval and remove observed same-scope collisions. The WMH-BIRD learned ranker reached Recall@1 `.704` and Recall@5 `.958`, versus lexical `.676/.887`. | First stage: scope, authority, exact identifiers, table/tool compatibility. |
| Term/alias candidate recall | WMH-BIRD termhood raised Recall@5 `.887 → .930` but left Recall@1 unchanged. Earlier within-schema termhood raised Recall@5 while lowering MRR and Recall@1. | Search-only recall lane; never canonical alias or ontology truth. |
| Dense embeddings | MATM action embeddings improved candidate Recall@20 by `+.123` over lexical (CI `[+.053,+.206]`), but the fold-local adapter was neutral (`+.0029` Recall@20, CI crossing zero). | Optional broad recall after structured filtering; no custom-model promotion from unlabelled traces. |
| Fold-local domain adaptation | Peter DataClaw combined MRR rose `.769341→.854452`; on a separate 404-session Claude-history proxy, user-message MRR rose `.885892→.915765` and all-message MRR `.899585→.921237`. | Keep cheap scoped lexical adaptation/reranking in shadow/candidate lanes; this is not neural embedding evidence or artifact utility. |
| Finance-specialized model and serving identity | Pinned FinanceBench: BalyasnyAI multilingual-e5 reached Recall@20 `1.000` / MRR `.8087`; the same projection through Ollama Nomic reached `.4533/.1661`. | Model choice and serving path are part of the retrieval contract; test domain models in a governed shadow lane before any corporate adaptation claim. |
| Frontier/model review | On the identical nine-query MATM shortlist, Luna tied lexical at MRR/Recall@1 and cost 104.118 seconds total. On a richer public reranking probe, frontier review improved ordering only when the target was already covered. | Use selectively for ambiguity, intent extraction, and synthesis—not routine retrieval or authority. |
| Replay validation | WMH-BIRD exposure substitutions yielded 1,232/1,236 execution errors or result mismatches. Replay-negative training tied naive exposed-negative training because the training split had no ambiguous substitutions. | Replay is the acceptance/data-quality gate; it is not yet a demonstrated representation-learning objective. |

The matched [44-case dense/frontier cohort](wmh-bird-sql-dense-frontier-cohort-2026-08-09.md)
is the strongest current cascade receipt. Local Nomic reached strict
MRR/Recall@1 `.940152/.909091`, while frontier reached `.954545/.909091`.
Their Recall@1 was tied, but dense retrieval selected about `5.545` tables with
`3.591` invalid selections on average, versus frontier's two tables and only
`.205` invalid selections. The measured frontier contribution is therefore
shortlist precision/noise reduction, not additional target discovery. This
reinforces the late-stage frontier role and the need for replay/authority gates.

The [fold-local adapter study](wmh-bird-sql-embedding-adapter-cohort-2026-08-09.md)
trained a small pairwise adapter on the even task split and evaluated the odd
split. It improved Nomic MRR `.940152 → .947917` and Recall@1
`.909091 → .931818`, but reduced Recall@5 and left incompatible shortlist
selection unchanged. Adaptation is therefore useful only as a labelled shadow
reranker with family-stratified monitoring; it is not a reason to train a
universal embedding from raw traces.

The FinanceBench receipts add an operational constraint: E5 reached Recall@20
`1.0` with `9.61s` corpus encoding, versus Qwen3-Embedding's `.9933` with
`111.15s`; governed E5 query latency was p50 `2.02ms` / p95 `2.96ms`. Model
snapshot, prefix, dimension, and serving path must therefore be part of index
identity and promotion criteria.

## Smallest useful cascade

```text
canonical trace + scope/authority
  -> exact identifiers and compatibility filters
  -> lexical / termhood / cheap learned reranker
  -> optional dense candidate expansion
  -> selective frontier or human review
  -> independent execution/replay and changed-system validation
  -> versioned artifact/eval/skill proposal
```

The order matters. Dense vectors and frontier models cannot repair a missing
candidate or an incompatible system choice. Conversely, exact retrieval cannot
discover an undocumented paraphrase, so a bounded recall lane remains useful.

## What this rules out for now

- A universal custom embedding model trained directly on raw traces.
- Frontier-model scoring on every trace or every dashboard query.
- Automatic alias, memory, skill, or ontology writes from term extraction.
- Treating exposed-but-unused tables/documents as semantic negatives without
  refusal, authority, temporal, and human-intent labels.

## Decisive next experiment

Use a consented enterprise cohort with repeated intents and at least four
negative classes: same-surface/different-system, temporal replacement,
result-preserving alternative, and genuinely irrelevant exposed candidate.
Compare the four stages under a fixed latency/token budget and evaluate:

1. semantic label agreement and NIL abstention;
2. wrong-system-before-target and collision rate;
3. changed-schema/tool replay success;
4. correction burden, task completion, and recommendation acceptance; and
5. whether adding domain-adaptive embeddings changes downstream artifact or
   skill outcomes after the structured baseline is already strong.

Until that cohort exists, the evidence supports a governed cascade, not a
semantic memory or custom-embedding product claim.

## Receipts

- [MATM embedding/model cascade](matm-embedding-model-cascade-audit-2026-08-02.md)
- [MATM frontier cost replay](matm-embedding-model-cascade-cost-2026-08-04.md)
- [WMH-BIRD exposure counterfactual](wmh-bird-exposure-counterfactual-2026-08-09.md)
- [WMH-BIRD replay-negative reranker](wmh-bird-replay-negative-reranker-2026-08-09.md)
