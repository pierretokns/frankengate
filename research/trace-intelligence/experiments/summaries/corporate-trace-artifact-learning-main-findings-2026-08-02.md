# Corporate trace-artifact learning: main findings

**Status:** current evidence synthesis  
**Scope:** reusable SQL/tool artifacts, corporate identifiers and aliases,
hard negatives, domain embedding adaptation, model-vs-embedding analysis,
trace-derived procedures, and publication fit

## Bottom line

The work has not disproven the academic papers. It has tested whether their
mechanisms transfer to a governed, identifier-heavy corporate setting and has
rejected several broad product interpretations of those mechanisms.

The strongest evidence is for a small, structured system:

```text
canonical loss-aware trajectory
  -> current authority and deletion gate
  -> exact identifiers / scope / lexical retrieval
  -> optional dense candidate recall
  -> evidence-linked eval, memory, or artifact proposal
  -> human or independent-verifier review
  -> isolated replay or prospective outcome
```

No automatic skill, memory, embedding adapter, or cross-user recommendation is
promotion-eligible yet.

## Supported mechanisms and useful corporate results

| Finding | Evidence | What it establishes |
| --- | --- | --- |
| Canonical trajectories outperform lossy projections as evidence | Native imports preserve branches, tool/result pairing, malformed records, and explicit OTel/ATIF loss receipts | Use one trajectory DAG and versioned projections; do not make OTel or ATIF a second authority |
| Deterministic mining can produce review queues | Wisp analysis reconstructed 92 structural recovery candidates, 103 eval proposals, and 7 procedure-review candidates; automatic writes were zero | Signals and reconstruction are useful proposal selectors, not skill or intent labels |
| Reusable artifacts can be governed safely | PostgreSQL capsule lab accepted a bound query and denied stale epoch, wrong scope, expiry, parameter mismatch, schema drift, and unsafe SQL interpolation | Build validation-carrying SQL/tool capsules before autonomous memory promotion |
| Artifact reuse across system changes needs semantic compatibility, not names alone | A five-case changed-system replay accepted 3/5 cases with semantic IDs and zero false semantic accepts; name-only compatibility accepted 5/5 but falsely accepted 2 semantic changes; strict fingerprints accepted only 1/5 | Store stable concept IDs and explicit, reviewable rename/parameter mappings; keep exact fingerprints as the default safety gate |
| Structured corporate identity is the highest-value retrieval intervention measured | Exact identifier + known scope: MRR `.4441 -> .6867`, R@1 `.1992 -> .4492`, R@5 `.8150 -> .9980`; wrong-system-before-target `14.43% -> .20%` | Exact identifiers, aliases, database/project/team scope must be the first retrieval lane |
| Dense retrieval is useful after structured filtering | CodeTraceBench exact+structured+dense reached R@20 `.818`; a separate MATM cascade found action-only embedding Recall@20 lift `+.123` over lexical | Treat vectors as candidate recall, not authority or replacement for identifiers |
| Retrieval and frontier judgment are not yet a measured combined cascade | On 76 validated BIRD artifacts, lexical/identifier/dense/hybrid all matched `0/76` at rank 1 because the pool had no repeated normalized templates; on a separate 16-case trajectory probe, Luna found `7` true positives but `6` false positives | Combine retrieval, selective model review, and independent replay architecturally, but require a same-cohort fixed-candidate factorial before claiming cascade utility or cost benefit |
| Frontier models can create bounded, evidence-grounded proposals | Luna produced valid, structurally grounded proposals for 3/4 meaningful content-minimized sessions; independent receipt verification passed | Model passes are viable after deterministic projection, but proposal quality and utility still require outcome labels |
| Frontier review of recurring tool artifacts is useful but unstable | Expanded DataClaw screen: 16 recurring cross-project candidates, 48/48 valid Luna calls, 11/16 unanimous candidates; labels were 25 reusable, 18 context-specific, 3 unsafe, and 2 insufficient-evidence | Frontier review is a silver review-queue layer; recurrence does not prove portability or safety, and roughly one-third of candidates still need adjudication | Blinded SME labels, independent correctness/outcome checks, authority/parameter gates, and changed-system replay |
| Frontier reranking adds value after lexical/dense candidate generation | On nine MATM leave-one-model-out queries, lexical and Luna both had MRR/Recall@1/3/5 `1.0`; embedding MRR `.674`; Luna's top-3 success `.704` tied lexical | Do not put a frontier model on every retrieval request; reserve it for ambiguous, high-value, human-reviewed cases |
| Same-scope schema collisions expose dense retrieval errors | On 17 deterministic gold-SQL focus proxies with same-normalized-name siblings in one database, Nomic Recall@1 `.471` and sibling-before-target `.235`; lexical `.353`/`.059`; Luna `.941`/`.0` | Preserve table/column identity; use frontier review selectively for ambiguous same-scope candidates |
| Small hard-negative embedding adaptation transfers across database families | Three leave-one-database-family-out folds: table-aware Recall@1 `.373`/collision `.298`; structured `.337`/`.056`; learned pair adapter `.302`/`.512` | Do not promote an adapter from proxy labels; require larger SME-labelled, entity/time/project-held-out data and a collision-safety gate |
| Schema-grounded hard negatives automatically improve a domain embedding | The 601-case, four-family-held-out benchmark found frozen Nomic above the schema-adaptive pair scorer in pooled MRR/R@1/R@10 (`.1824/.0933/.3760` vs `.1573/.0761/.3214`) and known-scope MRR/Recall@10 (`.217356/.447275` vs `.201527/.425539`) | This stronger public-proxy null still does not disprove custom corporate embeddings; it says generated schema labels and a small adapter are insufficient by themselves |
| Cheap identifier-aware reranking is a better current compromise | Leave-one-database-out logistic features reached MRR `.737`, Recall@1 `.647`, Recall@5 `.882`, and 0% collision-before-target; hard-negative weighting had no incremental gain | Add a cheap structured reranking lane before frontier review; this is a proxy-label diagnostic, not semantic alias truth |
| Alias adjudication can represent abstention | Two independent Luna roles scored 23 synthetic exact/semantic/collision/NIL/unclear cases with 1.0 surface, candidate, wrong-system, abstention, and inter-judge agreement | Preserve `nil` and `unclear` as first-class outcomes; this is only a capability gate until enterprise/SME labels exist |
| Frontier abstention works on a real public NL2SQL cohort | On 22 Defog-derived cases, Luna abstained on 8/8 constructed scope-swapped NILs and retrieved all 14 target-bearing cases; exact/lexical/dense retrieval could not abstain | Add an explicit late-stage abstention decision; this is still public/gold-SQL evidence, not enterprise semantic truth |
| Same-scope collisions are a distinct retrieval failure mode | On 17 Defog-derived collision cases, dense retrieval put a same-scope sibling before the focus proxy 23.5% of the time, lexical 5.9%, exact 0%; Luna reduced the proxy miss rate to 1/17 | Preserve full table/column identity and reserve frontier adjudication for ambiguous same-scope candidates; cross-database scope alone is insufficient |
| Domain embedding quality is inseparable from serving identity | On pinned FinanceBench, E5 reached Recall@20 `1.0` / MRR `.8087` in `9.61s` corpus encoding, while Qwen3 reached `.9933/.7164` in `111.15s`; loopback Nomic reached `.4533/.1661`; governed E5 queries were p50 `2.02ms` / p95 `2.96ms` | Bind model snapshot, prefix, dimension, endpoint, and rebuild lineage to the index; keep domain models in a governed shadow lane |
| Skill proposals need a run-level contract | Existing outcome/release gates prove scope, consent, independent verification, deletion, and rollback mechanics; the new skill-in-use protocol separates activation, binding, consumption, verifier observation, replay, and release | Evaluate extraction, binding, consumption, and outcome independently; do not promote a valid proposal without held-out downstream utility |

| Local and frontier models agree on trace-insight labels | Six blinded Wisp recovery candidates under the same contract had 0% all-field agreement; field agreement ranged from 0% for usefulness to 33.3% for cause | Cheap models may triage or draft proposals, but high-impact memory, skill, and eval labels require independent model/human agreement |

## Nulls and corrections

| Hypothesis | Correct result | Interpretation |
| --- | --- | --- |
| A Trace2Skill-style compiler transfers a procedure across databases | On a genuinely disjoint car-to-broker replay: no-skill `3/4`, neutral `3/4`, compiled procedure `3/4`, formatting placebo `4/4`; compiled vs controls McNemar `p=1.0` | Compilation, hashing, isolation, and replay are feasible; transfer utility is currently null |
| The earlier native Trace2Skill positive was held-out evidence | The seed-430000 source and replay shared all four broker task IDs; the earlier `4/4` is contaminated development smoke | It must not be cited as transfer evidence |
| The earlier sequential-prefix `2/2` was held out | Source and replay shared broker task IDs `2` and `11` | It must not be cited as transfer evidence |
| A small domain embedding adapter is enough | MATM Recall@20 `.5301 -> .5331`; confidence interval crosses zero and MRR slightly decreased | No adapter promotion; corporate hard-negative labels and stronger splits are required |
| Generic embeddings solve corporate aliases | Dense-only retrieval underperformed exact/scope retrieval on the identifier benchmark | Dense search is complementary, not the primary solution |
| SkillOpt/memory composition already improves agents | Multiple ALFWorld cohorts were floor-effect or null; the real-candidate Codex replay was `0/2` across no-skill, placebo, and candidate | The methods are not disproven; this fixture does not show a positive transfer effect |
| A larger changed-agent replay shows trace-mined utility | Sealed BIRD-SQL family-disjoint replay over 20 future tasks produced 20 ties, zero candidate wins/losses, exact delta `0.0`, and latency ratio `.989` | This is a bounded no-lift result, not a universal null or a causal disproof of skill-learning research |
| A frontier agent can consume a validated SQL artifact under governance | On four paired Defog paraphrases, no-skill, placebo, and validated-artifact arms all reached `4/4`; the artifact arm used 4 versus 6/5 SQL attempts and passed independent PostgreSQL semantic recomputation with zero authority/verifier errors | Consumption mechanics are proven; utility and retrieval benefit remain untested |
| Nearest-question artifact retrieval transfers to held-out tasks | Ten train-only broker/car retrieval targets executed under authority, but lexical nearest-artifact reuse matched target semantics `0/10` | Successful execution and lexical similarity are not sufficient for artifact relevance; parameterized/structured retrieval remains required |
| Multiple retrieval families recover held-out artifact relevance | Scope-filtered lexical, frozen dense, identifier-aware, and hybrid arms all produced `0/10` top-three semantic transfer on the same ten targets; removing scope caused pooled lexical/dense to choose the correct database only `7/10` and pooled identifier/hybrid `5/10` | The null is not specific to lexical search; keep database/project scope hard and require parameterized templates, NIL labels, regeneration controls, and changed-system replay |
| Parameterized templates create a safe reuse boundary | On 52 deterministic Defog parameter mutations, lexical and template-first retrieval recovered `52/52`; a strict normalized-template gate abstained on `10/10` template-absence NIL proxies, while lexical retrieval falsely accepted `10/10` | Store validated SQL/tool artifacts as typed parameterized templates; use semantic retrieval only inside the compatible-template set and abstain when it is empty. This is structural proxy evidence, not enterprise semantic quality |
| The source artifact pool itself contains reusable matches for these targets | An evaluation-only oracle executed all 165 same-scope validated artifacts and found 0/10 targets with any semantically matching artifact; oracle-structured top-1/top-3 were both 0/10 | The retrieval null is partly a pool-coverage ceiling. Re-ranking this source pool cannot recover transfer; add known-shared-intent templates or a regeneration control before judging embeddings |
| Retrieval recovers known shared intent when the library contains it | Controlled prompt-only paraphrases of 20 validated source tasks recovered the known artifact top-one `20/20` for lexical, frozen dense, and hybrid arms; identifier-aware recovered `8/20`; all 60/60 top-three executions were authorized and semantically correct | Artifact reuse is mechanically viable; the natural held-out null was not a universal embedding or artifact failure | Replace synthetic paraphrases with SME-labeled enterprise requests and compare reuse against frontier regeneration on changed systems |
| Composable subplans can fill a whole-query coverage gap | Two direct Luna seeds on five source-disjoint broker tasks: subplan library `10/10` semantic, no-skill `5/10`, formatting placebo `5/10`; stable task-level comparison 3 wins/0 losses/2 ties per control | Validated examples can improve fresh query generation when no complete artifact matches; this is promising but small and same-family | Replicate across families and time, add explicit regeneration and NIL controls, and replay against changed schemas before promotion |
| The artifact library has semantic coverage for these future tasks | An evaluation-only oracle checked all 33 admitted source artifacts against all ten targets: 165/165 governed executions were authorized, but no target had any semantically equivalent source artifact; even target-gold structural top-1/top-3 ranking matched 0/10 | The current failure is primarily missing library coverage, not merely poor retrieval; add composable/parameterized artifacts or regeneration rather than more nearest-neighbor tuning |
| Validated subplans can help a frontier agent compose a new answer | Two authoritative seeded replays on five source-disjoint broker tasks: composable subplan library `10/10` semantic correctness versus `5/10` no-skill and `5/10` formatting placebo; independent verification passed, with zero unauthorized observations and fewer SQL/tool calls. The original default receipt was quarantined after concurrent overwrite. | Promising composability signal after the whole-query coverage null; not a powered causal, cross-family, or enterprise result. Test parameterized artifacts, regeneration, changed schemas, and negative transfer next |
| A generalist span extractor can populate a corporate glossary without calibration | GLiNER on 49 Wisp files emitted 567 spans; an initial context-free probe hit `2/8`, while a corrected contextual probe hit `7/8`; output remained dominated by project/tool tags | Candidate mining is feasible; automatic glossary/ontology promotion is not. Add TermoUD/Termolator consensus, blinded enterprise labels, NIL/ambiguity handling, and search-impact tests |
| Classical termhood and query expansion solve corporate vocabulary | Termolator reached its configured 3,000-candidate cap on 49 Wisp documents; a six-document transparent expansion fixture improved MRR `.847222→.958333`, while corpus feedback did not improve | These are runnable candidate/search projections, not evidence of enterprise term quality; real reviewed aliases, reformulations, and wrong-system labels remain required |
| Generic termhood transfers across NL2SQL schemas | Database-held-out Defog diagnostic: cross-schema direct-surface recall `.489` versus termhood `.015`; a within-schema control reached `.388` versus `.358` | Termhood can recover vocabulary when the schema is represented in the mining corpus, but transfers poorly to an unseen schema. It is a search-enrichment projection, not a substitute for schema-local identifiers, aliases, or reviewed ontology links |
| Termhood-approved aliases improve object retrieval | On a 13-case within-schema holdout, lexical + termhood alias raised Recall@5 `.846→.923` and removed the observed same-scope collision, but lowered MRR `.860→.815` and Recall@1 `.846→.769` | Keep this as candidate-recall/search enrichment only; exact/identifier-aware ranking and reviewed hard negatives are still required |
| Train-only alias enrichment improves enterprise object retrieval | Defog proxy holdout: aliases covered 2/260 targets at support-one and 17/260 at support-two; MRR was `.734885` baseline/support-one and `.727542` support-two, with no Recall@1 lift | Sparse public exact aliases have insufficient coverage and can hurt ranking; this does not reject reviewed enterprise vocabulary mining | Natural reformulation chains, reviewed aliases, temporal replacements, larger hard negatives, and changed-system retrieval |
| Real-user traces establish cross-user task equivalence | Two MIT DataClaw exports provide real-user provenance; an 8-pair Luna pilot, after harness-boilerplate normalization, produced 1 related, 1 unclear, and 6 different pair labels with 8/8 repeat agreement | Candidate adjudication is feasible, but labels are silver and no cross-user transfer, skill-gap, or collaboration claim is established |
| Broad friction detectors identify real-user friction | An 8-row DataClaw Luna calibration produced 16/16 valid labels and 7/8 repeat agreement; neutral controls were productive, but keyword strata included productive/unclear cases | Use re-prompt/correction signals to prioritize review, not as automatic friction, satisfaction, or skill labels |
| Trace-dataset integrity is itself a promotion gate | The pinned MRiabov DataClaw card claims 775 scrubbed sessions, but the released JSONL had only 9 valid rows; deleting redaction markers made 104 parse, while 14.2M markers corrupted values | Reject malformed exports at ingestion; do not silently repair or use them for embeddings, alias mining, skill discovery, or cross-user evaluation |
| Parseable coding traces support candidate mining, but tool vocabulary is weak evidence | A 436-session/46-project OpenAI-format DataClaw export had 48,779 tool calls; prompt lexical top-1 same-project proxy rate was `.637` versus `.308` for tool-signature overlap; 342 normalized command shapes recurred across projects | Use prompts plus normalized command shapes for diverse review candidates and hard negatives; never treat tool-name recurrence as same-work or artifact correctness |
| Temporal recurrence can overstate artifact reuse | In a per-project 70/30 chronological split, 83.8% of later sessions had at least one same-project shape, but only 16.5% of shape events were same-project repeats and 27.9% were repeats from any project | Measure event-level support and parameter diversity; use cross-project recurrence as hard negatives, not as automatic artifact promotion |
| Normalized command shapes hide substantial parameter diversity | 12,237 command events collapsed to 4,297 shapes but 9,387 exact command digests; 1,092 shapes had multiple variants and 312 had at least five | Mine parameterized proposals with typed bindings and replay contracts; a recurring prefix is not a reusable artifact |
| Exact recurrence is much rarer than shape recurrence | In the chronological holdout, exact same-project event reuse was `.064` versus `.159` for shapes; any-project reuse was `.084` versus `.303`; session-level exact reuse was `.629` versus `.838` | Use shape recall, exact recurrence as a prior, and deterministic scope/epoch/schema plus replay as the release gate |
| Same filename/path surfaces are useful hard-negative candidates | In the parseable 436-session DataClaw export, 2,462 basename surfaces produced 4,025 full-path digests; 281 surfaces crossed projects, 245 of those also had multiple path digests, and collision-bearing surface events were 13.3% of path events | Preserve exact identifiers and scope; use same-surface/different-path/project pairs for reviewed NIL, alias, and wrong-system labels. A basename collision is not a semantic alias or artifact-correctness label |
| Identifier-aware retrieval adds signal in a temporal project proxy | On 141 chronological held-out sessions, prompt-only project MRR was `.551`; prompt + identifiers `.598`; prompt + shapes `.590`; prompt + shapes + identifiers `.657` with Recall@1 `.567` versus `.461` prompt-only | Keep exact identifier surfaces as a separate retrieval lane beside lexical, shape, and optional dense candidates. This is project recurrence, not same-work, alias quality, or artifact correctness |
| Exact paths trade recall for precision and are not authority alone | In the same chronological split, basename event reuse was `.303` within project versus exact-path `.167`; only `.553` of same-project basename hits were exact, and 60 full-path digests crossed projects in training | Use exact path identity as a high-precision exposure feature and basename as a scoped candidate/hard-negative feature; require authority, reviewed semantics, and replay for reuse |
| Friction mining requires typed tool-result events | The 436-session OpenAI projection yielded 19 adjacent repeats, 121 rephrase pairs, and 1,131 marker-bearing user messages, but zero explicit `tool` role messages | Use rephrase/retry structure for review sampling only; preserve `tool_call → tool_result → correction` edges before attempting failure recovery or skill labels |
| Durable memory and skill files are real trace artifacts | 243 sessions referenced `CLAUDE.md`/`.claude`, 34 referenced skills, 13 referenced `memory.md`, and 3 referenced `AGENTS.md`/`.codex`; 373 read-like and 343 write-like artifact calls were observed | Import memory/skill files as provenance-linked lifecycle events, but require citations, scope/epoch, contradiction/deletion handling, and replay before durable promotion |
| Memory/skill writes correlate with later command recurrence, but are confounded | Sessions after any prior artifact write had shape-hit rate `.397` and exact-hit rate `.124`, versus `.027`/`.008` with no prior write; direct-after-write sessions were `.393`/`.095` | Treat this as a cohort-selection signal for a randomized memory/skill replay study, not evidence that writing a file caused improvement |
| The memory-write association survives a within-project permutation check but remains non-causal | Across 13 projects with both states, pooled prior-minus-no-prior differences were `.366` for shape hits and `.114` for exact hits; fixed-project-count permutation p-values were `.0042` and `.0186`, while temporal trend and user choice remained uncontrolled | Use writes to enrich replay sampling; do not promote memory or skill artifacts without randomized changed-system outcomes |
| The authorized changed-system cohort is now machine-gated | A content-free two-task manifest passed structural validation but was correctly promotion-ineligible (1 target, 1 hard negative, 0 NIL/unclear); an incomplete fixture failed on consent, holdouts, arms, and task presence | Use the contract/validator as the partner ingestion gate; public proxies cannot satisfy the causal promotion requirements |
| Public traces have enough identifier-collision candidate supply for a review study | Chronological train-only strata contained 2,125 same-project exact pairs, 2,610 same-surface/different-path pairs, 306 cross-project same-surface/exact-path pairs, and 1,601 cross-project same-surface/different-path pairs | Use the frozen train pool for annotation and hard-negative review; recurrence is not semantic truth and cannot replace dual labels or replay |

The source/replay overlap auditor is now an executable gate. A family-disjoint
aggregate cannot be produced without a zero-overlap receipt:

- contaminated native replay: 4 overlapping task IDs;
- contaminated sequential prefix: 2 overlapping task IDs;
- authoritative car-to-broker replay: 0 overlapping task IDs.

## Independent skill-learning reality checks

The broader intervention set sharpens the claim boundary beyond the retrieval
benchmarks:

- The published SkillOpt checkpoint produced zero wins for no-skill, placebo, and
  candidate on four previously unused ALFWorld families at a 12-step horizon;
  one fair-horizon 35-step task also produced zero wins for all three arms.
  These are bounded negative slices, not a disproof of SkillOpt.
- A BIRD-SQL SkillGen reproduction generated a candidate from 6/8 failures, but
  held-out exact execution fell from `0.500` to `0.375` (zero repairs, one
  regression); the release gate rejected it.
- An independently replayed RHO candidate fell from `0.643` to `0.388` on
  eight held-out LOCOMO tasks. The self-preference signal did not predict
  independent utility on this slice. A Codex-adapted ReasoningBank run scored
  `0.593` versus `0.703` for its matched no-memory control on two held-out
  questions, so it remains quarantined.
- The first Codex portability probe over SkillLearnBench's enterprise-search
  task improved exact Q1 precision from `.80` to `1.00` with unchanged recall
  (`1.00`) when the human-authored skill was supplied; Q3 remained `1.00/1.00`
  in both arms. This is one task on a host-path adapter, so it is directional
  feasibility evidence only.
- The complete six-instance enterprise-search family replay improved q1
  micro-recall from `.811` to `.925`, precision from `.956` to `1.000`, and
  published-check pass rate from `3/6` to `5/6`, with no observed regression.
  The human arm used `1.76x` input context. This strengthens the directional
  retrieval-skill signal, but still lacks q2 labels, changed-system replay,
  user outcomes, and the official Docker execution path.
- The published one-shot generated skill on the same six instances reached q1
  recall `.868`, precision `1.000`, and pass rate `2/6`: better precision and
  recall than null, but materially weaker than the human procedure (`.925`,
  `5/6`). Generated artifacts are therefore useful candidates, not automatic
  replacements for reviewed procedures; composition/review is the next test.
- An isolated retry completed the sixth task and a non-imputing receipt merge
  now gives the reviewed-procedure plus two generated data-navigation skills
  q1 `53/53`, precision `1.000`, published-check pass rate `6/6`, and exact q3
  on all six instances. This is a stronger composition signal, not a causal
  result: it is one public family, q2 is unlabeled, arms were not randomized
  in one simultaneous run, and the host adapter is not the official Docker
  runner. The next matrix must randomize human-only, generated-only, composite,
  placebo, and null arms on task-disjoint families before promotion.
- A one-task changed-data proxy renamed `ContentForce` to `ContentHub`. The
  reviewed procedure retained q1 recall `1.000` and precision `1.000`; the
  composite retained precision but fell to `.875` recall, while null had
  `1.000` recall with one false positive. This is not enterprise transfer, but
  it shows that composition is not automatically more robust under changed
  names/data than a reviewed procedure alone.
- A public changed-data proxy renamed `ContentForce` to `ContentHub` in the
  prompt, product filename, and artifact contents. Null q1 recall fell to
  `.875`, while reviewed and composite arms stayed exact (`1.000` q1 and q3).
  This is robustness evidence for a controlled rename, not enterprise causal
  skill evidence; no user identity or independent outcome is present.
- A repeat of the same rename exposed a composition hard edge: the human arm
  again stayed exact, but the composite missed one q1 ID while null returned
  all IDs with one false positive. Generated procedures therefore add
  capability but can also dilute robustness; composition needs repeated seeds,
  mutation families, and a negative-transfer gate.
- A transparent query-expansion probe found keyword, pseudo-document, entity,
  and document-enrichment proxies improving synthetic MRR from `.847222` to
  `.958333`, while corpus feedback produced no lift. Conversation rewriting
  improved the two conversational cases. This supports approved search-only
  expansion and explicit history rewriting as candidates, not semantic
  enterprise alias discovery.
- A new stratified sample from the 1,013-session, multi-harness
  `zhiyaowang/dataclaw-zhiyaowang` corpus preserved tool outputs, branches,
  explicit errors, and project/model metadata. Hash-only recurrence found 9
  successful multi-session call-input candidates, 2 spanning multiple project
  labels and 4 spanning model labels; none crossed harness-source labels. Two
  same-shape error→success sessions were observed. These are the first richer
  public-history candidate signals in this program, but they are still review
  queues: the corpus supplies no independent task outcomes, organizational
  identity, or changed-system validation.
- Frontier review of eight of those candidates produced only `5/8` repeat
  agreements. The two cross-project candidates split between reusable and
  unsafe labels, while single-project candidates were mostly context-specific.
  Frequency plus a frontier judgment is therefore a useful review queue, not
  a release decision.

Together these results say that validation, replay isolation, and exact outcome
measurement are working. They do not yet show that a mined or published skill
improves future enterprise work. The decisive next test remains a powered,
task/user/project/time-disjoint factorial with no-skill, placebo, human,
trace-mined, SkillOpt, SkillGen, RHO, and regeneration arms.

## What the academic literature does and does not show

SkillLearnBench, SkillFlow, SkillFoundry, MUSE-Autoskill, SkillOpt, ReasoningBank,
Dreams, LangMem, Graphiti, AgentRx, AgentEvals, Phoenix, Opik, and Langfuse each
validate useful components or benchmark-specific learning loops. None of the
reviewed work establishes the complete Frankengate claim: private multi-user
traces, same-surface identifier collisions, governed artifact capsules,
authorization/deletion epochs, changed-system replay, and prospective enterprise
outcomes in one protocol.

Therefore the correct interpretation is **boundary finding**, not paper
disproof. A null on our four-task or eight-task cohort can mean the candidate,
task family, horizon, harness, or outcome oracle was insufficient. It cannot
refute a paper's result on its own benchmark.

Two newer results sharpen the next experiment rather than overturning this
boundary:

- [SAGE](https://arxiv.org/abs/2512.17102) reports a strong AppWorld gain, but
  its main sequential rollout keeps skills inside the same scenario and uses
  expert SFT plus RL and a skill-integrated reward. Its practical retrieval
  ablation is therefore not equivalent to dropping a mined procedure into a
  different database family. Our null is a test of frozen-procedure transfer,
  not a refutation of outcome-trained sequential skill learning.
- [Walmart's retrieval-evolution pipeline](https://arxiv.org/abs/2607.10096)
  combines cross-batch and metadata-aware hard negatives with warm-start
  distillation when changing embedding backbones, reporting production lift.
  This supports testing continuity-preserving adapter updates, not blindly
  replacing the current encoder. It still lacks our authority, deletion, and
  changed-tool replay requirements.

The closest enterprise hard-negative study, [ACL Industry
2025](https://aclanthology.org/2025.acl-industry.72/), selects negatives that
are closer to the query than the positive but farther from the positive than
the query. It reports internal reranker MRR@3 `.57`/MRR@10 `.64` versus
`.42`/`.45` without fine-tuning. This is a strong recipe for our alias and
wrong-system corpus, but not proof of trace or skill utility.

## Architecture decision

Keep the required production core to:

1. Aurora PostgreSQL as the evidence, authority, artifact, and experiment store.
2. A loss-aware canonical trajectory DAG with explicit tool proposal,
   authorization, execution, observation, and state-delta events.
3. Exact identifiers, aliases, structured scope, and lexical retrieval.
4. Optional pgvector/dense retrieval behind authorized structured candidates.
5. Versioned SQL/tool capsules with provenance, schema/parameter contracts,
   expiry, replay, rollback, and deletion lineage.
6. A frontier/SME review queue and a no-skill/placebo/neutral experiment harness.

Graph databases, TurboVec/VectorChord/pgContext, custom embeddings, automatic
memory writes, and cross-user recommendations remain experimental add-ons. The
current evidence does not justify making any of them a mandatory dependency.

## Required next experiments

1. Run 20–40 sequential tasks across multiple source/evaluation families with
   user/project/time disjointness, no-skill, neutral, formatting, mined,
   SkillOpt, SkillGen, and RHO arms.
2. Use a changed database or tool environment, sealed outcome labels, independent
   semantic/security verification, paired repair/regression metrics, and cost and
   latency accounting.
3. Replay validated artifacts across real or public schema migrations and tool
   contract versions, comparing exact fingerprints, name-only adaptation, and
   semantic-ID mappings before measuring downstream task success.
4. Build a corporate alias/hard-negative set with SME adjudication, including
   same token/different system, undocumented aliases, NIL cases, and temporal
   renames; hold out users, projects, tenants, and time.
5. Compare exact/lexical/structured, dense, reranking, and frontier-model passes
   on the same candidate set with blinded quality labels and a fixed cost budget.
6. Measure prospective human usefulness and skill-gap recommendations only in a
   consented, privacy-reviewed cohort; public traces cannot establish employee
   capability or collaboration claims.

## Research and publication fit

The publishable contribution is a governed evidence-to-artifact lifecycle with
leakage gates and explicit claim boundaries, not “enterprise memory improves
agents.” The proposed public/sealed reproduction package and partner shortlist
are in [`publication-partner-opportunities-2026-08-02.md`](publication-partner-opportunities-2026-08-02.md).
The concrete run-level evaluation bridge is the
[`skill-in-use-verifier-contract-2026-08-02.md`](../protocols/skill-in-use-verifier-contract-2026-08-02.md)
protocol.
The tracking epic is [#118](https://github.com/pierretokns/frankengate/issues/118).

All current receipts and code are on the pushed branch
`codex/trace-intelligence-academic-program`.

The [publication/partner evidence update](publication-partner-evidence-update-2026-08-02.md)
incorporates the exact-vs-shape, memory-lifecycle, friction-format, and
dataset-integrity results. It keeps the paper framing on a governed
evidence-to-artifact lifecycle and identifies causal changed-system replay as
the missing experiment.
