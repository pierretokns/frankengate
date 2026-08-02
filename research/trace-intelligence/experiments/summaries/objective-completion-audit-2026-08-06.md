# Corporate trace-artifact learning objective audit

**Audit date:** 2026-08-09
**Branch:** `codex/trace-intelligence-academic-program`  
**Status:** active/incomplete. “Supported” means exercised under a recorded
fixture and verifier; it does not mean enterprise readiness or causal benefit.

| Objective | Strongest current evidence | Status | Required next proof |
|---|---|---|---|
| Reusable validated SQL/tool artifacts | On recorded BIRD traces, only `76/193` executable tool queries matched independent gold results; natural lexical reuse matched `1/76`, while controlled typed-template replay matched `75/75` mutated targets. A family-disjoint frontier replay using 16 actual validated trace artifacts scored `4/20` versus `3/20` for both controls, with one paired win, zero losses, and 19 ties. In 36,549 local Codex command occurrences, same-scope repeats after prior success succeeded `97.09%` versus `94.68%` overall, while cross-scope reuse fell to `87.02%`. Governed capsules reject stale authority, wrong scope, expiry, schema drift, unsafe interpolation, and parameter errors. Exposure-counterfactual replay produced 1,232/1,236 execution errors or result mismatches, with only four result-preserving substitutions; an equivalence-aware held-out retrieval probe found no aggregate lift and alternate-only Recall@10 `.028169`. Replay remains a validation gate rather than a semantic label. The joined retrieval→replay decision keeps PostgreSQL policy/semantic compatibility ahead of dense retrieval. | Scope-bound operational artifact priors are supported; semantic utility and safe cross-scope reuse remain unproven | Repeated natural intents, compatible templates, changed-system semantic outcomes, real tool contracts, deletion/failover, more seeds/models, and user utility. |
| Whole-query retrieval | Natural library coverage is `0/10`; nearest wording is not a safe reuse mechanism. | Negative boundary established | Larger real artifact libraries and independent intent labels. |
| Composable subplans | Same-family broker replay was `10/10` versus `5/10` controls. Two family-disjoint BIRD replays were `8/40` versus `6/40` for both controls, with one stable win and zero stable losses. | Repeatable but low-headroom positive signal | More families/seeds, irrelevant-library NILs, schema mutation, and changed-system outcomes. |
| Corporate concept/alias discovery | Modernized termhood produced 3,000 candidates; within-schema recall `.358`, held-out transfer `.015`. Acronym probe passed `8/8` synthetic cases with ambiguity abstention. Alias enrichment lowered MRR (`.860→.815`) on a small holdout. | Candidate mining only | Reviewed internal aliases, temporal replacements, NILs, same-scope wrong-system labels, and downstream utility. |
| Hard-negative mining | Scope-aware identifier retrieval reduced collision-before-target from `14.43%` to `.20%`; identifier-aware reranker reached MRR `.737` and collision rate `0.0` on a held-out public proxy. | Useful bounded method | Larger expert-labeled hard-negative families and changed-system replay. |
| Domain-specific embeddings | MATM fold-local adapter delta was only `+.0029` Recall@20 with negative/neutral MRR change; schema-adaptive pair scorer lost to frozen Nomic. A leave-one-project-out Trace Commons adapter tied its already-ceiling baseline (`13/13`, MRR `1.0`). | No adapter promotion; public proxy too easy to measure transfer | Expert triplets, paraphrase/entity/project/time holdouts, hard negatives, and absolute downstream-lift gates. |
| Embedding-vs-model insight mining | Action embeddings improved candidate Recall@20 by `+.123` on MATM, while dense/lexical/identifier/hybrid BIRD retrieval all gave `0/76` top-1 executable matches. A paired public BIRD trajectory probe had prompt-only Luna abstain `16/16`; trajectory-aware Luna reached `7/8` recall but only `7/13` precision, with six false positives. On the identical nine-query MATM shortlist, Luna tied lexical while adding `104.118s` total wall time. | Use embeddings/models for candidate recall, ranking, and validator suggestions only; no automatic acceptance | Common human/SME insight labels, fixed cost budgets, adversarial NILs, repeated intents, and changed-system artifact replay. |
| Identifier-aware representations | Exact identifiers, database scope, semantic IDs, and authority are consistently safer than generic dense similarity. | Strong design rule | Enterprise semantic alias labels and temporal/tenant tests. |
| Structured SSL-style trace representations | A 20-record isolated-tool probe preserved exact identifiers `20/20` but emitted zero scenes. A corrected 19-record multi-tool probe preserved exact tool/action order `19/19`, emitted `2.63` scenes and `.63` transitions per trace, and fully grounded evidence on `.684` of records. | Input structure unlocks scene/action extraction, but normalization is review-only and not yet a retrieval or skill result. | Enterprise multi-step traces with retries, typed effects, authority/time labels, human adjudication, and downstream replay utility. |
| Real coding-session normalization | Ten bounded episodes from one MIT-licensed cctrace session preserved exact tool/action order `10/10`, emitted `1.9` scenes and `.9` transitions, and fully grounded `.800` of episodes. | Coding-trace ingestion and review proposals are feasible; one session cannot establish skill, alias, or cross-user utility. | Multiple authorized sessions/principals, independent terminal outcomes, replayable artifacts, and capability labels. |
| Normalized coding-trace structural quality | An independent audit found exact action order, scene coverage, and transition references `1.000`, with conservative action-type fidelity `.983607`. | The projection is structurally complete enough for review and candidate features; semantic phase/effect correctness remains unproven. | Human adjudication, replay/terminal labels, and downstream retrieval or skill utility. |
| Parameter-aware artifact capsules | On the same 10 episodes, input-key fidelity was `1.000`, but repeated top-level tool order was `0.0`, per-action resource identity `.300`, and safe-template actions only `.081967`; no replay was run. | The schema must keep immutable identity separate from resource and template fields; model proposals remain unvalidated. | Original/changed-system replay, side-effect/authority labels, template correctness, and artifact utility. |
| Deterministic artifact capsule compiler | A content-external compiler preserved tool order, input keys, action order, invocation uniqueness, and source provenance at `1.000` on 10 episodes. | Deterministic capsule identity is supported; semantic template enrichment remains optional and untrusted. | Original/changed-system execution, authority/deletion checks, result validators, and user utility. |
| Skill improvement | One-shot trace-mined procedure was `8/40`, equal to no-skill and slower. The validated-artifact library arm reached `4/20` versus `3/20` no-skill and `3/20` placebo, but only one paired win and no losses. A separate four-task family-disjoint Luna factorial tested a diagnosis-derived fault checklist: all three arms were `0/4` exact, and independent verification passed. In the six-task SkillLearnBench enterprise-search family, null/generated/reviewed reached `43/53`, `46/53`, and `49/53` q1 IDs; a later reviewed+generated composite reached `53/53`, with all arms q3-exact `6/6`. Two frontier seeds of one renamed task were stable for reviewed guidance but not composition. These are verified checkpoints, not a universal disproof of sequential skill learning. | Keep prose procedure, fault checklist, and generated composition quarantined; retain reviewed guidance and validated artifacts only as scope-bound experimental candidates | Task-disjoint families, randomized null/placebo/generated/reviewed/composite arms, changed-system replay, cost/latency gates, and independent labels/outcomes. |
| Cross-user insights | Trace Commons prompt retrieval reached `13/13` and durable-identifier retrieval `12/13` same-project top-1 on a repeated-workstream proxy; event structure was `1/13`. The corrected local Codex archive importer exposes 622 sessions and 47,122 prompt episodes; lexical friction markers had only `.79%` precision against a structured process-exit proxy. DataClaw frontier review agreed on only `5/8` repeated candidate labels. No stable enterprise labels or independent outcomes exist. | Workstream/friction-signal proxies only; cross-user insight unproven | Consent-stable identities, principal/time-disjoint task labels, human capability labels, same-surface negatives, and negative-transfer gates. The required protocol is documented in [cross-user insight and skill-gap protocol](cross-user-insight-skill-gap-protocol-2026-08-09.md). |
| Publication/partners | Evidence packet maps CMU LTI, MIT DSAIL, Harvard human-outcome/data-systems groups, MIT CLEAR/TRAC, and NVIDIA GEAR to specific reproduction questions. | Outreach-ready, cohort absent | Authorized/sealed cohort, preregistration, and independent reproduction. |
| Older modernized tools | TermSuite/Termolator and AcronymExpansion ports are reproducible under `uv`; upstream legacy stacks are setup-blocked. | Offline review-only value | Enterprise labels before any ontology or embedding promotion. |

The exact-versus-execution-equivalent artifact probe is documented in
[wmh-bird-equivalence-aware-retrieval-2026-08-09.md](wmh-bird-equivalence-aware-retrieval-2026-08-09.md).

The cross-harness normalization audit is documented in
[claude-command-artifact-normalization-2026-08-09.md](claude-command-artifact-normalization-2026-08-09.md).
The four-cohort transfer audit is documented in
[claude-cross-cohort-command-transfer-2026-08-09.md](claude-cross-cohort-command-transfer-2026-08-09.md).
The cross-domain identifier transfer probe is documented in
[nl2sql-identifier-cross-domain-transfer-2026-08-09.md](nl2sql-identifier-cross-domain-transfer-2026-08-09.md).
The cross-cohort termhood stability probe is documented in
[termhood-cross-cohort-stability-2026-08-09.md](termhood-cross-cohort-stability-2026-08-09.md).
The cross-cohort acronym stability probe is documented in
[acronym-cross-cohort-stability-2026-08-09.md](acronym-cross-cohort-stability-2026-08-09.md).
The cross-corpus SQL artifact signature probe is documented in
[cross-corpus-sql-artifact-signatures-2026-08-09.md](cross-corpus-sql-artifact-signatures-2026-08-09.md).
The strict DataClaw cross-user artifact transfer probe is documented in
[dataclaw-cross-user-artifact-transfer-2026-08-09.md](dataclaw-cross-user-artifact-transfer-2026-08-09.md).

## Overall conclusion

No academic method has been disproven. The current evidence supports a minimal
cascade of structured identity → exact/lexical retrieval → dense candidate
recall → frontier/human ambiguity review → independent replay → release or
abstention. The strongest positive is validated subplan composition; the
strongest negative is one-shot prose/procedure transfer. The missing decisive
evidence remains a consented changed-system cohort with independent semantic
labels and terminal outcomes.

Sources: [current evidence matrix](current-evidence-matrix-2026-08-06.md),
[trace-derived artifact reuse](bird-trace-artifact-reuse-2026-08-07.md),
[cross-method calibration](cross-method-calibration-2026-08-06.md), [replay
readiness status](enterprise-replay-readiness-status-2026-08-06.md), and
[publication/partner packet](publication-partner-evidence-packet-2026-08-06.md).
The current archive import is documented in
[codex-archive-history-import-2026-08-08.md](codex-archive-history-import-2026-08-08.md).
The latest intervention is documented in
[wmh-bird-fault-category-intervention-2026-08-09.md](wmh-bird-fault-category-intervention-2026-08-09.md).
The retrieval/replay composition decision is documented in
[retrieval-to-replay-composition-decision-2026-08-09.md](retrieval-to-replay-composition-decision-2026-08-09.md).
The cross-user evidence boundary is documented in
[cross-user-insight-skill-gap-protocol-2026-08-09.md](cross-user-insight-skill-gap-protocol-2026-08-09.md).
The SkillLearnBench seed-stability synthesis is documented in
[skilllearnbench-changed-data-multiseed-2026-08-09.md](skilllearnbench-changed-data-multiseed-2026-08-09.md).
