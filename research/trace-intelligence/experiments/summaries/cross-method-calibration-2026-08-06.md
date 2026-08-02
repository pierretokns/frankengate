# Cross-method calibration checkpoint (2026-08-06)

This update keeps unlike tasks and labels separate while incorporating the
expanded 40-task skill factorial and the earlier composable-subplan replay.

| Mechanism | Cohort/result | What it supports | What it does not support |
|---|---|---|---|
| Whole-query artifact retrieval | `0/10` natural library-coverage NILs | Text-nearest whole-query reuse is unsafe when no compatible artifact exists. | That artifact reuse is impossible. |
| Parameterized artifact gate | `52/52` known mutations; `10/10` template-absence NILs rejected | Compatibility-gated template reuse with explicit refusal. | Mined enterprise artifact quality or causal user benefit. |
| Semantic-ID subplan adaptation | `3/5` accepted and correct; `0` unsafe accepts; name-only had `2` unsafe accepts | Typed semantic IDs and post-composition verification. | Automatic migration mapping or enterprise prevalence. |
| Frontier composable subplans | `10/10` on two seeded runs over five broker tasks; controls `5/10` | Validated examples can be decomposed and composed when whole-query retrieval has no exact answer. | Powered, cross-family, changed-system, or natural skill-transfer utility. |
| One-shot trace-mined procedure | `8/40`, equal to no-skill `8/40`; trace-vs-no-skill `1–1` paired | The tested procedure is not promotable; the null is independently verified. | A universal rejection of sequential skill learning. |
| Identifier-aware retrieval | MRR `.737`, Recall@1 `.647`, collision-before-target `0.0` on held-out proxy | Cheap structured reranking before dense/frontier stages. | Semantic alias truth. |
| Domain embedding adapter | MATM Recall@20 delta `+.0029`, MRR delta `-.0015`; schema adapter below frozen Nomic | Raw repeated-work traces alone do not justify an adapter. | Properly supervised schema/alias embedding research. |
| Frontier reranking cascade | Equal lexical quality on nine MATM queries; mean `11.569s` per frontier call | Use frontier selectively in the gray zone. | Frontier usefulness for real insight labels or downstream artifacts. |

## Calibration conclusion

The positive result is **structured, validated subplan composition**, not a
generic memory or embedding layer. The strongest safe cascade remains:

```text
scope/semantic IDs -> exact/lexical -> dense candidate recall
  -> frontier/human ambiguity review -> independent replay -> release/abstain
```

The 40-task factorial improves power for one-shot skill transfer but remains a
single public SQL proxy cohort. Its no-lift result should not be pooled with the
five-task composable-subplan success. The next positive test must use a clean,
larger multi-step or repair-oriented consumer and preserve no-skill, placebo,
fresh-generation, and composed-subplan controls.

Receipts:

- [`40-task factorial`](bird-sql-skill-factorial-40-2026-08-06.md)
- [`composable subplan replay`](composable-artifact-frontier-replay-2026-08-04.md)
- [`parameterized retrieval`](parameterized-artifact-retrieval-2026-08-06.md)
- [`identifier reranker`](nl2sql-identifier-reranker-2026-08-03.md)
- [`MATM cascade cost`](matm-embedding-model-cascade-cost-2026-08-04.md)

