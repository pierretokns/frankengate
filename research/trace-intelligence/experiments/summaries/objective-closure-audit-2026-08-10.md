# Corporate trace-artifact learning objective closure audit — 2026-08-10

**Status:** active/incomplete; current branch is reproducible and publication-
ready, but enterprise semantic and prospective outcome gates remain open.

## Requirement evidence

| Objective lane | Current evidence | Status |
|---|---|---|
| Validated SQL/tool artifacts | Independent validation admitted only `76/193` recorded BIRD queries; typed parameter replay passed `75/75`; exact scoped priors survive time holdout while coarse key shapes are negative | Governed mechanics demonstrated; causal utility open |
| Corporate concepts and aliases | Full EnterpriseRAG source filtering improves MRR but leaves a same-source tail; train-only Defog alias links reproduce exactly but cover only `.065385` of targets and slightly lower MRR | Candidate generation only |
| Hard negatives | Full 500-question source ceiling removes wrong-source candidates but leaves same-source distractors; identifier-aware public proxies reduce collision-before-target | Compatibility/representation signal demonstrated; semantic labels open |
| Domain embedding adaptation | Fold-local Nomic adapter gives a small rank-one gain but no invalid-selection precision gain; project-held-out lexical adaptation is silver | Shadow adaptation only |
| Embedding/model cascade | Dense retrieval broadens candidates; frontier review improves ordering when targets are already covered; NIL proposal rate remains `1.0` on tested retrieval arms | Candidate/ranking/review stages demonstrated; release safety open |
| Identifier-aware representations | Exact identifiers, scope, semantic IDs, authority epochs, and resource identity repeatedly outperform name-only or generic dense controls on safety/compatibility proxies | Strong architectural rule |
| Skill/memory improvement | Reviewed guidance and typed/subplan arms show bounded positive signals; generic prose and SkillOpt replications are null or negative | No causal promotion evidence |
| Cross-user patterns and skill gaps | Similarity/retrieval queues are reproducible, but no independent task-equivalence, capability, human-outcome, or negative-transfer labels exist | Open |
| Publication/partners | Current packet defines a falsifiable lifecycle paper, partner-specific study, sealed replay API, and content-free receipts | Outreach-ready; no collaboration commitment |

## Machine-audited open gates

The current completion checks preserve these as unresolved rather than
inferring completion from infrastructure or proxy results:

- authorized/CMU publisher access and independent trajectory metrics;
- randomized causal skill utility and release-gated optimizer arms;
- semantic procedure/dream utility under changed systems;
- prospective enterprise task outcomes and human labels;
- managed Aurora semantics, extension compatibility, concurrency, and scale;
- consented minimum-cohort labels for cross-user analysis;
- collaboration utility, unwanted-contact, and negative-transfer outcomes; and
- matched SkillLearnBench/Recovery-Bench intervention outcomes.

## Decisive next study

Use the strengthened [enterprise semantic-cohort contract](../../configs/studies/enterprise-semantic-cohort-v1.json): at least 100 targets, 50 hard negatives, 25 NIL/unclear cases, two blinded annotators, principal/team/project/system/time holdouts, and five examples of every required mutation stratum. Run exact/structured, lexical, dense, fold-local adapter, reviewed semantic-ID, composed subplan, and frontier-regeneration arms against the same frozen candidate pool. Promote nothing without independent changed-system replay, terminal outcomes, deletion/rollback receipts, and cost/latency budgets.

## Source artifacts

- [Full EnterpriseRAG ceiling](enterprise-rag-source-filter-ceiling-full-2026-08-10.md)
- [Alias enrichment reproduction](nl2sql-alias-enrichment-reproduction-2026-08-10.md)
- [Semantic cohort contract addendum](enterprise-semantic-cohort-contract-conformance-2026-08-10.md)
- [Publication/partner packet](publication-partner-evidence-packet-2026-08-10.md)
- [New skill/provenance/retrieval prior-art map](latest-skill-provenance-retrieval-prior-art-2026-08-02.md)
- [SRA-Bench BM25 retrieval control](sra-bench-bm25-retrieval-control-2026-08-02.md)
- [SRA-Bench BM25/TF-IDF comparison](sra-bench-bm25-tfidf-comparison-2026-08-02.md)
- [SRA-Bench ToolQA lexical/dense comparison](sra-bench-toolqa-lexical-dense-comparison-2026-08-02.md)
- [SRA-Bench TheoremQA lexical/dense comparison](sra-bench-theoremqa-lexical-dense-comparison-2026-08-02.md)
- [SRA-Bench ToolQA incorporation control](sra-bench-toolqa-incorporation-control-2026-08-02.md)
- [SRA-Bench ToolQA candidate breadth and progressive disclosure](sra-bench-toolqa-candidate-breadth-2026-08-02.md)
- [Current objective audit](objective-completion-audit-2026-08-06.md)
