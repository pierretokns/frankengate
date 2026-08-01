# Corporate trace-intelligence evidence matrix

Date: 2026-08-02

This matrix is the current claim ledger for the program. “Supported” means the
mechanic or measurement has been independently exercised. It does not mean the
mechanism has demonstrated enterprise productivity or causal user benefit.
“Null” means the candidate did not beat its controls in the stated cohort; it
does not mean the cited academic method is disproven.

## Claim ledger

| Hypothesis | Current evidence | Status | Safe claim | Required before promotion |
| --- | --- | --- | --- | --- |
| Preserve a canonical trajectory rather than flattening OTel/ATIF text | Native imports, branch reconstruction, tool/result pairing, malformed-record quarantine, and loss receipts pass on public histories. ATIF/OTel projections still omit reset, reward, memory, termination, and authorization facts. | **Supported mechanic** | Use a provider-neutral trajectory DAG plus explicit loss records. | Cross-harness conformance on more native formats and sealed task outcomes. |
| Mine friction and recovery candidates from history | Wisp/share-codex common constructor found 89 and 31 bounded error→later-success episodes; the same constructor changed earlier counts materially. | **Supported detector** | Generate review candidates, not “user skill gaps” or causal recoveries. | Human labels for intent, causality, task success, and environment failure. |
| Generate suggested evals from traces | Full Wisp derivation emitted 11 eval proposals and 7 procedure-review proposals with evidence links; proposal/audit mechanics passed. | **Supported proposal path** | Treat output as an auditable review queue. | A guided harness must execute the proposal against a changed system and retain gold/negative labels. |
| Reuse validated SQL/tool artifacts safely | Governed PostgreSQL capsules enforce scope, authorization epoch, expiry, schema fingerprint, parameters, result shape, RLS, and audit receipts; invalid cases were denied. | **Supported mechanism** | Build a governed artifact library before attempting autonomous memory promotion. | Multi-tenant concurrency, deletion, failover, Aurora compatibility, and outcome lift. |
| A frontier agent can consume a validated SQL artifact under governance | Four paired Defog paraphrase tasks: no-skill, placebo, and validated-artifact arms all reached `4/4`; the artifact arm used 4 versus 6/5 SQL attempts and passed independent PostgreSQL recomputation with zero authority or verifier errors. | **Bounded consumption mechanics** | Artifact execution and submission can be safely wired into the governed loop. | Train-only artifact library, unpaired retrieval, NIL candidates, larger changed-system replay, and reuse-versus-regeneration lift. |
| Nearest-question retrieval of validated SQL transfers to held-out tasks | Ten broker/car-dealership `questions_gen` targets retrieved executable same-database artifacts from basic/advanced source tasks; all 10 executed under authority, but 0/10 matched target semantics. A follow-up compared lexical, frozen dense, identifier-aware, and hybrid arms: every scope-filtered arm remained 0/10 in top-three semantic transfer; pooled lexical/dense selected the correct database only 7/10 and pooled identifier/hybrid only 5/10. | **Negative bounded retrieval result** | “Store successful SQL and retrieve the nearest question” is insufficient; validated execution does not imply relevance, and database/project scope must be a hard boundary. | Parameterized templates, explicit structural NIL cases, SME relevance labels, regeneration control, and changed-schema replay. |
| Structured identifiers and scope resolve corporate collisions | Surface exact + known scope: MRR .4441→.6867, R@1 .1992→.4492, R@5 .8150→.9980; wrong-system-before-target 14.43%→.20%. | **Strongest quality result** | Exact identifiers, aliases, project/database/team scope must be a first retrieval lane. | Blinded SME labels for true aliases, NIL cases, undocumented terms, and family-held-out replay. |
| Generic embeddings solve identifier/alias ambiguity | `nomic-embed-text` + scope was below exact identifier retrieval on the pinned NL2SQL slice; collision adjudication was deliberately easy and model-only. | **Rejected as default** | Do not replace structured retrieval with dense search. | Hard negative and semantic-alias labels before any corporate model claim. |
| Domain adaptation automatically improves embeddings | MATM fold-local adapter: Recall@20 .5301→.5331, delta +.0029, CI crosses zero; MRR slightly decreased. The 601-case, four-family-held-out schema benchmark found frozen Nomic above the schema-adaptive pair scorer in pooled MRR/R@1/R@10 (`.1824/.0933/.3760` vs `.1573/.0761/.3214`) and known-scope MRR/R@10 (`.217356/.447275` vs `.201527/.425539`). | **Null / not promotable** | “Train an adapter” is not evidence of useful adaptation; generated schema labels and hard negatives did not beat the frozen baseline here. | Corporate hard negatives, entity/time/project holdouts, SME alias/NIL labels, and a preregistered downstream utility gate. |
| Dense retrieval is still useful in a cascade | CodeTraceBench factorial retained exact IDs and found exact+structured+dense reached R@20 .818; labels are silver and not jointly RLS-tested. | **Promising retrieval component** | Use dense search for candidate recall after exact/structured filters. | Human labels, PostgreSQL execution, selective-RLS latency, deletion, and cost measurements on the same corpus. |
| Frontier-model reranking adds value after lexical/dense candidates | Nine MATM leave-one-model-out queries: lexical and Luna both MRR/Recall@1/3/5 1.0; embedding MRR .674; Luna top-3 success .704 tied lexical. Candidate pool and labels were silver. | **Null incremental gain / bounded checkpoint** | Keep frontier ranking off the hot path; use it for ambiguous review and hard-negative adjudication. | Blinded SME labels, adversarial NIL/wrong-system cases, candidate-recall freeze, latency/cost, and downstream replay. |
| Frontier adjudication can abstain on aliases and NILs | Two independent Luna roles on 23 synthetic exact/semantic/collision/NIL/unclear cases: surface, candidate, wrong-system, and abstention accuracy all 1.0; inter-judge agreement 1.0. | **Synthetic capability gate** | Keep explicit `nil`/`unclear` labels and abstention in the contract. | Authorized enterprise cases, two independent SME judgments, calibration, user/project/time holdouts, and changed-system replay. |
| Frontier abstention transfers to a real NL2SQL cohort | On 22 Defog-derived cases (6 explicit, 8 implicit, 8 scope-swapped NIL), Luna retrieved all target cases and abstained on 8/8 constructed NILs; exact/lexical/dense retrieval had no abstention semantics. Target MRR: exact .893, lexical .806, dense .690, Luna 1.000. | **Public-corpus capability / abstention result** | Keep model abstention as a late-stage gate; never interpret retrieval of a candidate as evidence that one exists. | Enterprise/SME labels, true NIL/unclear cases, calibration, holdouts, cost/latency, and changed SQL/tool replay. |
| Same-scope table/column collisions are resolved by generic dense retrieval | On 17 focus-object proxy cases with same-normalized-name siblings in the same database, dense Recall@1 was .471 and put a sibling before the proxy target in 23.5% of cases; lexical collision-before-target was 5.9%, exact 0%, and Luna .0% with Recall@1 .941. | **Dense collision failure / frontier checkpoint** | Preserve table/column identity and reserve frontier review for ambiguous same-scope collisions; do not treat dense similarity as authority. | SME-labelled object relevance, larger schemas, temporal renames, changed-schema replay, cost/latency, and RLS-aware candidate generation. |
| Hard-negative embedding adaptation transfers across database families | Three leave-one-database-family-out folds: table-aware embedding Recall@1 .373 with 29.8% collision-before-target; structured score Recall@1 .337 with 5.6%; learned pair adapter Recall@1 .302 with 51.2%. | **Negative / not promotable** | Hard-negative training is not evidence of a useful corporate embedding; keep structured retrieval authoritative. | Larger SME labels, more families, entity/time/project holdouts, calibrated loss, and a preregistered absolute-lift plus collision-safety gate. |
| A cheap identifier-aware reranker can replace dense/frontier ranking for same-scope collisions | Leave-one-database-out logistic reranker reached MRR `.737`, Recall@1 `.647`, Recall@5 `.882`, and 0% collision-before-target; 4x hard-negative weighting produced no incremental gain. | **Promising small diagnostic** | Put a cheap structured reranker between lexical retrieval and frontier review; do not call it semantic alias discovery. | SME labels, larger families, temporal changes, cost/p95, and prospective artifact/replay utility. |
| Trace-mined skills improve downstream task success | Direct native runs were neutral/inconsistent; proxy paraphrase was 8/12 vs neutral 7/12, balanced native was 9/12 vs neutral 9/12; a complete car→broker replication was 3/4 vs no-skill 3/4, neutral 3/4, and placebo 4/4. | **Null / harness-sensitive** | No current skill artifact is promotion-eligible. | Powered multi-seed, family-held-out, changed-environment replay with cost and negative-transfer gates. |
| A Trace2Skill-style compiler can transfer a procedure | The initial 4/4 native and 2/2 sequential-prefix results were contaminated by source/replay task overlap. The corrected disjoint car→broker replication executed safely but tied no-skill and neutral at 3/4 while the placebo scored 4/4 and used 8 vs 6 SQL attempts. | **Null transfer utility; mechanics supported** | Compilation, hashing, isolation, and replay are feasible; no held-out skill lift is established. | Demonstrate incremental lift over no-skill and neutral on a larger genuinely disjoint sequential cohort, including repair/regression and efficiency. |
| SkillOpt/memory composition helps frontier agents | ALFWorld four-family 35-step factorial: no component, SkillOpt, memory, and composition all 0/4; earlier SkillOpt checkpoint also had zero wins. | **Small null with floor effect** | Do not infer that composition is harmful or universally useless. | Non-floor tasks, fair horizons, larger cohort, and a direct causal comparison. |
| Graph/memory systems add useful enterprise state | Graphiti/LangMem passed API smoke checks but no natural full case completed within the bound; exact-state retrieval and graph extraction target different objectives. | **Compatibility only** | Keep graph/memory extraction optional and downstream of governed evidence. | Temporal/contradiction benchmark, exact identifier retention, update/rollback, deletion, and later-query utility. |
| Cross-user trace mining identifies collaborators or missing skills | Structural proposal mechanics pass; public-corpus analysis intentionally emitted zero skill-gap/collaboration recommendations. | **Unproven** | Require opt-in, minimum cohorts, and reviewed taxonomies before recommendations. | Consent-stable identities, human capability labels, prospective outcomes, and privacy/abstention evaluation. |
| Cheap models can replace embedding/retrieval analysis | No fair head-to-head enterprise insight study has yet passed; tiny local models often failed structured output or tool protocol. | **Untested / capability-gated** | Compare model passes only after retrieval and schema projections are fixed. | Frontier-quality structured extraction baseline, cost/latency budget, and blinded insight-quality labels. |
| TurboVec/vector acceleration is needed now | CodeTraceBench dense index mechanics passed; 2-bit matched exact dense Recall@20 in a small cohort, 4-bit lost 1.52 points. | **Mechanics only** | Quantization/indexing is an optimization option, not an architectural requirement. | Scale, filtered retrieval, rebuild/failover, RLS interaction, and cost against exact pgvector. |
| Science One-style evidence chains improve research reliability | Claim-level receipts, isolated branches, raw evaluator retention, and independent audit rules were mapped into the protocol. | **Process adaptation** | Use evidence chains to prevent overclaiming and make experiments reproducible. | A/B test whether the process improves reviewer agreement, error detection, or decision quality. |

## What this means for the architecture

The evidence supports a small core rather than a stack of independent memory,
graph, vector, and search products:

1. One governed evidence/proposal authority in PostgreSQL.
2. A canonical trajectory DAG with explicit OTel/ATIF loss receipts.
3. Exact identifiers, aliases, and structured scope filters.
4. Optional pgvector/dense candidate recall behind those filters.
5. Versioned SQL/tool capsules with tests, provenance, expiry, scope, and replay.
6. A frontier/SME adjudication queue and a no-skill/placebo/neutral experiment
   harness.

Graph databases, custom embeddings, TurboVec, automatic memory writes, and
cross-user recommendations remain experimental add-ons. None is justified as a
mandatory production dependency by the current evidence.

## Completion gates still open

- 20–40+ sequential tasks across multiple families, users/projects, and changed
  schemas; report paired lift, cost, latency, abstention, and negative transfer.
- Blinded alias/NIL/wrong-system labeling with at least two independent frontier
  judgments plus SME adjudication.
- Corporate hard-negative and entity/time/project holdouts for any embedding
  adaptation claim.
- Human labels and prospective outcomes for friction, skill gaps, collaboration,
  and eval usefulness.
- Same-corpus quality + RLS + deletion + concurrency + p95/p99 benchmark on the
  selected PostgreSQL/Aurora deployment surface.

Until those gates close, no skill, memory, embedding adapter, or cross-user
recommendation should be auto-promoted.
