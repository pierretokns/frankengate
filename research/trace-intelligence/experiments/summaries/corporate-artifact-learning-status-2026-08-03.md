# Corporate trace-artifact learning status ledger — 2026-08-03

This ledger is a requirement-level status report. “Proven” means proven only
at the scope stated in the evidence column; it never means production-ready or
enterprise-general.

The current independent completion audit remains `active_incomplete`; its open
requirements are fair powered controls, independent prospective outcomes, and
comparable power/cost/latency accounting. This is an intentional result of the
audit, not a missing receipt.

| Requirement | Current evidence | Status | What is still required |
|---|---|---|---|
| Reusable validated SQL/tool artifacts | PostgreSQL capsule replay accepts valid bound SQL and rejects stale authority, wrong scope, expiry, parameter mismatch, schema drift, and unsafe interpolation. Changed-system replay shows semantic-ID mappings avoid false semantic acceptance. A frontier agent consumed four paired validated artifacts under governed PostgreSQL and passed independent recomputation. An authoritative two-seed composable subplan replay reached 10/10 semantic correctness versus 5/10 no-skill and 5/10 placebo on five source-disjoint broker tasks. | **Mechanics and bounded composability signal** | Cross-family/time/project-held-out replication, changed production-like systems, independent outcome oracles, and prospective success. |
| Unpaired validated-artifact retrieval | Initial lexical screen: 0/10 semantic reuse. Follow-up comparison: lexical, frozen dense, identifier-aware, and hybrid scope-filtered arms all had 0/10 top-three semantic transfer; pooled retrieval selected the correct database only 7/10 for lexical/dense and 5/10 for identifier/hybrid. An evaluation-only oracle executed all 165 same-scope source artifacts and found 0/10 targets with any semantically matching artifact. A controlled shared-intent companion recovered the known source artifact 20/20 for lexical, dense, and hybrid arms. | **Natural cohort: pool-coverage null; controlled cohort: retrieval mechanics recovered known intent** | Nearest-question lookup is insufficient on natural held-out tasks, but artifact reuse is recoverable when the library contains a known shared-intent artifact. Hard scope filtering remains mandatory. | Natural SME paraphrases, parameterized templates, regeneration and changed-system utility. |
| Validated-artifact pool coverage ceiling | Evaluation-only oracle executed all 33 admitted source artifacts against all ten targets (165/165 authorized): zero targets had any semantic match, and gold-structure oracle top-1/top-3 were both 0/10. | **Library-coverage null** | The source library lacks reusable answers for this cohort; retrieval cannot recover artifacts that are not present. | Parameterized/composable artifacts, frontier regeneration, SME relevance labels, explicit NILs, and changed-schema replay. |
| Composable artifact subplans | Two seeds on five source-disjoint broker tasks: composable subplan arm 10/10 semantic, no-skill 5/10, placebo 5/10; three stable wins and zero losses per control at the unique-task level. | **Promising small frontier replay** | Store validated artifacts at subplan/template granularity and let a frontier agent compose them; do not auto-promote yet. | Cross-family/time/project holdouts, fresh-generation comparison, SME relevance/NIL labels, changed-system replay, and cost/latency. |
| Corporate concept and alias discovery | 22-case public alias/NIL benchmark and 17-case same-scope collision benchmark; Luna abstained on constructed NILs and resolved many bounded collisions. | **Public capability only** | Two independent SME labels, undocumented internal aliases, true NIL/unclear cases, temporal validity, and user/project/system/time holdouts. |
| Hard-negative mining | Same-scope collision benchmark exposes dense errors; structured identity ranker removes observed collision-before-target errors. | **Useful bounded method** | Larger adjudicated hard-negative families and a fixed cost/latency budget. |
| Domain-specific embedding adaptation | Database-family-held-out MATM adapter underperformed deterministic structured scoring and reached 51.2% collision-before-target. The 601-case schema-grounded benchmark found frozen Nomic above the regularized adapter in both pooled MRR/R@1/R@10 (`.1824/.0933/.3760` vs `.1573/.0761/.3214`) and known-scope MRR/Recall@10 (`.217356/.447275` vs `.201527/.425539`). | **Negative on public proxy; enterprise recipe still open** | Require SME-labelled undocumented aliases, true NIL/wrong-system cases, entity/time/project holdouts, and downstream changed-system utility lift before promotion. |
| Identifier-aware representations | Cheap leave-one-database-out ranker reached MRR .737 / Recall@1 .647 / Recall@5 .882 with 0% observed collision-before-target. | **Promising retrieval lane** | SME semantic labels and downstream artifact utility; the positive labels remain gold-SQL proxies. |
| Embedding-vs-model insight mining | MATM action embeddings improved Recall@20 by +.123; outcome-conditioned prioritization had negative/uncertain AUC delta; Luna reranking tied lexical on nine same-corpus queries, with 104.118s total / 11.569s mean wall-clock; Luna procedure proposals passed structural grounding on 3/4 Wisp sessions. | **Cascade mechanics and cost checkpoint** | A common labeled insight target, provider billing, adversarial NILs, and replayed artifact usefulness. |
| Frontier review of recurring tool artifacts | Initial screen: 8 candidates, 16/16 valid calls, 5/8 repeat agreement. Expanded screen: 16 cross-project candidates, 48/48 valid calls, 11/16 unanimous; 25 reusable, 18 context-specific, 3 unsafe, and 2 insufficient-evidence judgments. | **Review-queue signal; promotion unproven** | Blinded SME labels, exact task outcomes, governed replay, and changed-system safety/utility gates. |
| Local-model versus frontier insight labels | On six blinded Wisp candidates under the same rubric, field agreement ranged from 0% (`usefulness`) to 33.3% (`cause`); all-six agreement was 0%, despite valid structured output and candidate-local evidence references. | **Not interchangeable** | Human labels, multi-model calibration, and prospective outcome checks before using a cheap model for high-impact memory/skill/eval decisions. |
| Trace-mined skill improvement | Disjoint car→broker and broader factorial replays show ties/nulls; mined procedures are not promotion-eligible. | **Causal utility unproven** | Powered sequential tasks with no-skill, neutral, placebo, mined, and teacher arms on changed systems. |
| Larger changed-agent outcome replay | A sealed BIRD-SQL 20-task family-disjoint candidate/control replay produced 20 ties, zero candidate wins/losses, exact-match delta 0.0, and latency ratio .989. | **Bounded no-lift result** | More task families, non-floor interventions, and independent user/outcome labels before any causal claim. |
| Canonical trace representation | ATIF/OTel round trips preserve projections but lose load-bearing reward, reset, memory, termination, and authority facts. | **Projection mechanics proven** | Canonical DAG adoption and real collector/runtime integration. |
| Cross-user/team insights | Structural mining produces evidence-linked proposals, but no independent employee skill-gap, collaboration, or satisfaction labels exist. | **Unproven** | Consent, minimum cohorts, privacy review, prospective outcomes, and unwanted-contact/negative-transfer measurement. |
| Publication/partner claim | Literature map identifies adjacent work and a narrow artifact-lifecycle research seam; partner shortlist covers CMU, MIT DSAIL, Harvard data/human-systems groups, and NVIDIA GEAR. | **Ready for reproduction package** | License-cleared or sealed replay cohort, preregistration, and partner acceptance. |

## Current architectural decision

Use a canonical loss-aware trajectory DAG and a single governed artifact store.
Route retrieval through exact identifiers and structured scope first, then
lexical and optional dense candidate recall, then the cheap identifier-aware
ranker, and reserve frontier/human review for ambiguity and abstention. Require
semantic-ID compatibility, authority/epoch checks, result/outcome validation,
and replay before release. Do not make a custom embedding, graph database, or
automatic memory/skill writer a mandatory dependency yet.

## Claim boundary

No academic paper has been disproven. The experiments identify transfer
conditions under which broad interpretations fail: embeddings do not reliably
resolve same-scope identity, hard-negative weighting alone did not help, and
trace-mined procedures did not yet improve changed-system task success. Those
are results about our protocols and public proxies, not refutations of the
original papers.

## Authoritative artifacts

- [Main findings](corporate-trace-artifact-learning-main-findings-2026-08-02.md)
- [Evidence matrix](evidence-matrix-2026-08-02.md)
- [Enterprise label/drift protocol](../protocols/enterprise-semantic-label-and-drift-2026-08-03.md)
- [Publication and partner opportunities](publication-partner-opportunities-2026-08-02.md)
- [Research epic #118](https://github.com/pierretokns/frankengate/issues/118)
