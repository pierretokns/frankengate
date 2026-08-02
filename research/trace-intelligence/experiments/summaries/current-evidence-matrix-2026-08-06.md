# Current corporate trace-artifact evidence matrix (updated 2026-08-07)

This matrix is a decision aid, not a claim that public proxy results transfer
to an enterprise. Each row links to the receipt-backed experiment and states
the strongest conclusion that the current data supports.

| Question | Measured result | Decision | Still missing |
|---|---|---|---|
| Can validated SQL/tool artifacts be reused safely? | On 222 recorded BIRD trace tasks, only `76/193` executable trace queries matched independent gold results. Natural leave-one-out lexical reuse matched `1/76`; a controlled typed-template replay matched `75/75` mutated targets. | Treat tool success as unvalidated until independently checked; keep parameterized artifacts with scope, schema version, authority, and explicit refusal. | Natural repeated intents, real tool contracts, changed-system outcomes, latency/cost, and independent user labels. |
| Does validated subplan composition transfer across families? | Two BIRD replays: library `8/40` exact versus `6/40` for both no-skill and placebo; one stable library win and zero stable losses. | Keep subplans as a separate experimental artifact granularity; the aggregate signal is stable but low-headroom and underpowered. | More families/seeds, irrelevant-library NILs, changed-schema replay, and enterprise outcomes. |
| Does whole-query semantic retrieval solve artifact reuse? | Natural whole-query retrieval had `0/10` library-coverage NILs; nearest wording is not a safe reuse signal. | Do not reuse by text similarity alone; retrieve inside a compatible template family or regenerate. | Larger artifact libraries and real production intents. |
| Do the modernized TermSuite/Termolator ideas discover corporate concepts? | `3,000` candidates; termhood recall `0.358` within represented schema and `0.015` cross-schema transfer. A termhood alias boost raised Recall@5 but lowered MRR (`.815` vs `.860`) on a 13-case held-out proxy. | Candidate generation/search enrichment only; no automatic ontology or embedding updates. | Reviewed aliases, NILs, temporal renames, wrong-system pairs, and enterprise outcomes. |
| Do modernized acronym extraction ideas help? | `8/8` synthetic cases passed, including ambiguity/NIL abstention. | Keep as a conservative review-queue miner. | Natural corporate abbreviations and precision/recall against adjudicated labels. |
| Are exact identifiers and scope important hard negatives? | Unfiltered same-surface collisions preceded the target in `14.43%` of links; known scope reduced this to `0.20%`. | Preserve identifiers and scope as first-class fields and filters. | Multi-tenant, temporal, and authorization-scoped production traces. |
| Can a cheap identifier-aware ranker improve retrieval? | Leave-one-database-out ranker: MRR `.737`, Recall@1 `.647`, collision-before-target `0.0`; dense baseline MRR `.586`, Recall@1 `.471`, collision `0.235`. | Use structured/lexical reranking before dense or frontier calls. | SME semantic labels, larger families, and changed-system replay. |
| Does a small custom embedding adapter automatically help? | MATM fold-local adapter changed Recall@20 by only `+0.0029` (CI crosses zero) and reduced MRR by `.0015`; schema-adaptive pair scorer lost to frozen Nomic in both scope modes. | No promotion of an embedding adapter from raw/repeated-work traces alone. | Schema-grounded positives, expert labels, hard negatives, and user/project/time holdouts. |
| Are embeddings useful anywhere? | MATM action embeddings improved candidate Recall@20 by `+0.123` over lexical on a hidden-work proxy; outcome-conditioned prioritization had uncertain/negative AUC delta. | Use embeddings for broad candidate recall, not authorization or final truth. | Cost-controlled cascade and downstream artifact utility. |
| Can model/frontier adjudication replace retrieval? | Luna was strongest on a tiny gold-proxy reranking cohort but materially more expensive/latent; model-vs-lexical evidence remains small and task-specific. | Reserve frontier models for ambiguous candidate review, intent extraction, and synthesis. | Fixed-budget trials with independent labels and replay outcomes. |
| Do mined skills improve agents? | Expanded BIRD-SQL replay: trace-mined procedure `8/40`, equal to no-skill `8/40`, versus formatting placebo `5/40`; paired trace-vs-no-skill was `1–1` with 38 ties, while trace latency was `11.102s` vs `10.306s` for no-skill. | No skill was promoted; require no-skill, placebo, reviewed, generated, and composed controls. | Sequential task chains, outcome-trained consumers, and changed-system evaluation. |
| Can public clarification traces answer friction questions? | BIRD-Interact has `600` labeled ambiguity/follow-up tasks; 20 public samples expose trajectory/reward schema but are not a benchmark. | Use it to stratify clarification experiments, not to claim user-friction or skill gains. | Public gold/test bundle or an authorized natural-user cohort. |
| Can we infer cross-user skill gaps or collaboration? | No current public cohort has stable multi-principal identity plus outcomes sufficient for this claim. | Keep recommendations opt-in and review-only. | Reciprocal consent, blinded labels, negative-transfer and unwanted-contact measures. |

## Architecture implied by the evidence

```text
structured scope / identifiers / authority
        -> exact + lexical + cheap reranker (precision and safety)
        -> embedding retrieval (recall only, filtered by compatibility)
        -> frontier or human review (ambiguity, alias, intent, synthesis)
        -> independent execution/replay verifier
        -> versioned artifact or skill, with rollback and refusal
```

The matrix supports a governed evidence-to-artifact lifecycle. It does not
support a generic “memory layer improves agents” claim, an automatic corporate
ontology, or a custom embedding model trained from unlabelled logs alone.
The decisive open experiment remains a consented changed-system cohort with
independent semantic labels and terminal outcomes.

## Source summaries

- [`parameterized artifact retrieval`](parameterized-artifact-retrieval-2026-08-06.md)
- [`trace-derived artifact reuse`](bird-trace-artifact-reuse-2026-08-07.md)
- [`older-tool modernization audit`](older-tool-modernization-value-audit-2026-08-05.md)
- [`termhood alias retrieval`](nl2sql-termhood-alias-retrieval-2026-08-04.md)
- [`identifier hard-negative benchmark`](nl2sql-identifier-hard-negative-2026-08-02.md)
- [`identifier-aware reranker`](nl2sql-identifier-reranker-2026-08-03.md)
- [`MATM domain adapter`](matm-domain-embedding-adapter-2026-08-02.md)
- [`embedding/model cascade`](matm-embedding-model-cascade-audit-2026-08-02.md)
- [`schema-adaptive retrieval`](nl2sql-schema-adaptive-retrieval-2026-08-01.md)
- [`40-task skill factorial`](bird-sql-skill-factorial-40-2026-08-06.md)
- [`cross-method calibration`](cross-method-calibration-2026-08-06.md)
- [`enterprise replay readiness`](enterprise-replay-readiness-status-2026-08-06.md)
- [`next experiments and promotion gates`](corporate-trace-artifact-learning-next-experiments-2026-08-06.md)
