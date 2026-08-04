# A1 Deductive Inference Analysis

## Thesis

The deductive shape of the Frankengate trace-intelligence program is:

1. A trace can support a claim only when the claim's required premises are explicitly present in governed evidence or in a receipted, loss-aware projection.
2. Similarity, structural friction, model judgment, later non-error tool output, and released benchmark labels are not premise-equivalent to identity, skill, causation, correctness, permission, or intervention benefit.
3. Every higher-level enterprise claim needs a typed inference status:
   `deterministic_observation`, `statistical_candidate`, `causal_effect`, `reviewed_release`, or `unsafe_or_unsupported`.

The current evidence supports a kernel: a governed canonical event DAG, current authority checks, loss receipts, typed tool lifecycle, bitemporal evidence, proposal/release/influence records, credential-only exclusion, and local PostgreSQL/RLS mechanics. It does not deductively support automatic memories, skill-gap claims, named collaborator recommendations, root-cause automation, custom embeddings, external vector/search authorities, or leaving Aurora/PostgreSQL.

In A1 terms, the main invalid implication chains are:

- "These traces are semantically close" therefore "the same work/person/skill gap exists."
- "An error was followed by a non-error result" therefore "the later action fixed the task."
- "A selector finds informative traces" therefore "it diagnosed cause."
- "A projection round-tripped spans" therefore "authorization, replay state, and evidence semantics survived."
- "A memory or skill influenced later behavior" therefore "later behavior independently validates it."
- "Local RLS worked" therefore "all sidecars, caches, Aurora failover, and analytics preserve authority."

The smallest defensible architecture is therefore not a maximal trace-intelligence stack. It is one governed evidence and release authority with adapters and experimental arms around it.

## Top Findings

1. **§F1 [Kernel Candidate]: The canonical governed event DAG is the only valid source of enterprise evidence; ATIF and OTel/OpenInference are projections.**
   - **Evidence:** `canonical-projection-e0-conformance-2026-07-30.md` reports that ATIF accounted for all 48 governed fixture events but retained `0 / 48` canonical event identities and `0 / 34` parent edges after reimport, while OTel/OpenInference recovered `48 / 48` identities and `34 / 34` parent edges but redacted 75 content/authority fields and left three authorization/replay fields unsupported. `otel-collector-roundtrip-e0-2026-07-30.md` reports a real SDK/Collector/file-exporter round trip preserving projected span topology, but its drop control shows a downstream receipt cannot discover spans dropped before storage without an out-of-band expected-count manifest. `atif_adapter.py` explicitly says ATIF is an interchange projection and emits loss receipts rather than silently dropping events.
   - **Reasoning chain:** If a target format cannot preserve authority, environment, evaluation, replay, parentage, or event identity, then conclusions requiring those premises cannot be drawn from that projection. OTel may preserve operational topology; ATIF may preserve selected conversation/tool lifecycle examples. Neither entails full enterprise evidence.
   - **Deployment-calibrated severity:** High. In an internal enterprise system, the risk is less public disclosure and more audit/RCA/memory claims being made from a lossy projection that lacks policy and replay facts.
   - **Confidence:** High.
   - **So what:** Keep the canonical DAG in PostgreSQL/Aurora as authority. Use ATIF for selected portable task/eval examples and OTel/OpenInference for content-minimized observability, each with source hashes, expected counts, and loss receipts. Never feed a reduced projection into another analysis arm while canonical evidence is available.

2. **§F2 [Kernel Candidate]: Authority is a premise, not a filter applied after retrieval.**
   - **Evidence:** `wisp-governed-postgres-benchmark-2026-07-30.md`, `nebius-governed-postgres-pilot-2026-07-30.md`, and `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` all report zero denied candidates before ranking under local PostgreSQL RLS. `sql/001_trace_research.sql` defines typed tenant, subject, team, purpose, classification, authorization epoch, `FORCE ROW LEVEL SECURITY`, and `NOBYPASSRLS` roles. `nl2sql_capabilities/governed_broker.py` revalidates principal, database handle, epoch, snapshot, expiry, and operation authority before every solver operation. `tests/test_governed_broker.py` includes tests for stale authority, cross-episode handles, post-terminal authority checks, and zero-SQL submit failures.
   - **Reasoning chain:** A claim about what a user, team, or admin may see is valid only if the candidate set was authorized before scores, counts, snippets, vectors, cursors, caches, exports, or model inputs existed. Post-filtering can remove content but cannot erase side-channel evidence already created by unauthorized candidates.
   - **Deployment-calibrated severity:** Critical for cross-user/team/admin surfaces. Internal users may be authorized for full PII/classified content inside scope, but cross-scope candidate leakage remains a policy failure.
   - **Confidence:** High for the invariant; medium for production readiness because Aurora failover, reader lag, RDS Proxy, concurrency, sidecars, and caches have not passed the same gauntlet.
   - **So what:** Treat "authorized candidate set equality" as a launch invariant across SQL, FTS, pgvector, graph/search sidecars, caches, telemetry, memory extraction, eval generation, and exports. Any external vector/search system must receive only authorized, credential-clean chunks or opaque IDs and must be rechecked before display or learning.

3. **§F3 [Kernel Candidate]: Same-work retrieval is a candidate generator; it does not imply identity, skill, or collaboration utility.**
   - **Evidence:** `codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md` reports structured plus dense retrieval reached `0.818` Recall@20 on silver task labels, but task identity is not a blinded human task-family label and same benchmark work does not imply collaboration value. `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` shows exact pgvector reached `0.667` Recall@20 at `3.017 ms` p50, while the tested hybrid only reached `0.672` at `256.843 ms` p50. `public-native-history-fidelity-2026-07-30.md` finds mirrored, flattened, scrubbed, merged, and native histories rather than an independent enterprise panel. `enterprise-question-composed-factorial-v3-2026.json` explicitly sets `retrieval_similarity_is_identity: false`.
   - **Reasoning chain:** "Same task label" or "near vector neighbor" supplies at most a retrieval candidate. Identity of work requires objective, environment, tool menu, time, authorization, task boundary, and human or executable labels. Collaboration utility additionally requires consent, availability, reciprocal need, and measured outcomes.
   - **Deployment-calibrated severity:** High. A named people finder built from embeddings or exact identifiers would be socially unsafe even for authorized admins because it invites employee surveillance and false skill narratives.
   - **Confidence:** High.
   - **So what:** Display same-work retrieval as artifact or pattern candidates, not named worker matches. Cross-user introductions require reciprocal opt-in and prospective outcome measurement. Custom embeddings remain gated on a frozen hard slice where exact, structured, lexical, and general dense retrieval fail under the same authority/deletion rules.

4. **§F4 [Kernel Candidate]: Friction/recovery evidence is not deductively equivalent to root cause or skill gap.**
   - **Evidence:** `wisp-share-codex-canonical-bounded-recovery-2026-07-30.md` finds 89 Wisp and 31 share-codex matched bounded episodes using explicit typed errors, unique linkage, post-error same-family success, a 12-event window, and greedy one-to-one assignment, but says this does not prove the later operation fixed the problem. `wisp-share-codex-cross-corpus-replication-2026-07-30.md` warns that raw error prevalence is not portable across harnesses. `codetracebench-raw-e3-e4-factorial-2026-07-30.md` reports best deterministic localization top-1 `0.286`, equal to reverse chronology, and no calibrated judge. `defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md` reports every arm passed the same `2 / 4` tasks and protocol-failure rates of 25-50 percent.
   - **Reasoning chain:** A trace can show "typed error before later non-error result." To infer "recovery," the system needs independent task outcome or human outcome labels. To infer "cause," it needs alternative explanations and an intervention/replay design. To infer "skill gap," it additionally needs evidence that capability was required, available, teachable, not blocked by permissions/tools/environment/model/protocol, and improved by a targeted suggestion.
   - **Deployment-calibrated severity:** Critical if attached to employees, staffing, training mandates, performance review, or manager dashboards; medium if kept as private review candidates.
   - **Confidence:** High.
   - **So what:** Product and API language should use "friction candidate," "recovery candidate," "eval proposal," or "support opportunity." It should not say "root cause," "skill deficit," or "the user learned" without a separate causal design.

5. **§F5 [Kernel Candidate]: Memory, temporal evidence, Graphiti/LangMem/MemInsight/Memory Palace, dreams, and `MEMORY.md` compose only through a proposal-release-influence ledger.**
   - **Evidence:** `bitemporal-memory-conformance-2026-07-30.md` passes 15/15 assertions over evidence-scope intersection, contextual contradiction, valid/system time, copy-on-write release, rollback, deletion closure, and influence exclusion. `trace-commons-memory-composition-2026-07-30.md` reports verbatim/bitemporal retention of all 48 unique revisions while latest-only retained 20 and overwrote 28; latest-only leaked same-basename foreign-project evidence in 3/6 placebos. `longitudinal-memory-local-model-replication-2026-07-30.md` reports identical aggregate scores for evidence-bearing arms and confounds including visible arm labels, non-dreaming dream arm, incomplete bitemporality, and unattested runtime/source. `dream_release_pipeline_v2.py` implements query-independent dream inputs, citation-based proposals, independent verification, authority intersection, copy-on-write release, and deletion-aware visibility.
   - **Reasoning chain:** A memory claim requires exact source evidence, context identity, known-at/valid-at cutoff, scope/purpose/classification, contradiction handling, review state, deletion state, and influence lineage. A generated memory, graph edge, or `MEMORY.md` line lacks those premises unless it is backed by the release ledger. Latest-wins and semantic merge destroy identity and time premises.
   - **Deployment-calibrated severity:** High. Memory is the place where future leakage and self-validation are easiest to hide because later traces may be influenced by the very artifact being validated.
   - **Confidence:** High for representation invariants; medium for eventual utility because corrected model results do not exist yet.
   - **So what:** Treat Graphiti, LangMem, MemInsight, Memory Palace, cloud dreaming, and `MEMORY.md` as mechanisms or destinations over Frankengate-native evidence. Do not make any of them a live authority or automatic writer.

6. **§F6 [Kernel Candidate]: Intervention benefit requires sealed, independent, held-out evaluation; current NL2SQL and Trace2Skill evidence is mechanics-only.**
   - **Evidence:** `defog-governed-sql-replay-conformance-2026-07-30.md` semantically matched all 95 PostgreSQL-executable tasks under policy, proving verifier/security boundary rather than model improvement. `defog-sql-factorial-preregistration-2026-07-30.md` defines no-skill, placebo, and expert procedure arms with sealed families, terminal tools, and primary endpoint `semantic_correct AND policy_accepted AND NOT unauthorized_observation`. `defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md` failed the protocol and paired-win gates, leaving P1 and hidden sealed. `nl2sql-capability-isolation-component-checkpoint-2026-07-30.md` reports 61/61 component tests and one real Linux/runc boundary pass, but lists missing final minimal image, OS peer credentials, server/broker receipts, crash recovery, signed OTel, and full 27-gate proof. `trace2skill-governed-stage0-2026-07-30.md` is a one-task verifier/sandbox result where both arms passed after recalculation.
   - **Reasoning chain:** A replay/verifier boundary can establish that an outcome is measurable. It does not establish that a prompt, procedure, memory, model, or skill caused improvement. Causal benefit requires an intervention contrast with no-skill/placebo controls, sealed families, fixed tool/model/budget, independent evaluator, influence tracking, and no hidden leakage.
   - **Deployment-calibrated severity:** High. Automatic skill release or self-improvement loops would create confident but circular enterprise guidance.
   - **Confidence:** High.
   - **So what:** Repair the Defog terminal protocol, rerun P0 under new hashes, then test one trace-mined procedure against no artifact and placebo on family-disjoint tasks. Until then, ReasoningBank, Hermes/Jeopard-style skills, Trace2Skill, RL histories, and cloud dreaming stay as proposal mechanisms.

7. **§F7 [Owner-Acknowledged Limitation]: Public traces and current pilots prove adapters and mechanics, not enterprise population facts.**
   - **Evidence:** `public-agent-history-discovery-2026-07-30.md` finds abundant public agent-history availability but says it does not prove independent users, task correctness, employee skill, or intervention benefit. `public-native-history-fidelity-2026-07-30.md` distinguishes byte-native, scrubbed-native, normalized, merged, flattened, and mirrored sources. `longitudinal-memory-cohort-expansion-2026-07-30.md` passes small count gates but fails confirmatory diversity gates at two source families and three exact-transition project contexts; the Glint archive is a byte-exact mirror of a pinned cfahlgren1 archive. `MODES_ANALYSIS_PROGRESS.md` records owner-acknowledged limitations: current cohort too small, only two independent source families, and no current evidence for leaving Aurora or training a custom embedding.
   - **Reasoning chain:** A public trace can validate parser fidelity, loss receipts, structural detectors, or review-candidate construction. It cannot determine enterprise prevalence, employee capability, collaboration utility, or cross-organization transfer without consented internal labels and prospective outcomes.
   - **Deployment-calibrated severity:** Medium-high. The internal context permits full-fidelity same-scope analysis, but false organizational generalization remains harmful.
   - **Confidence:** High.
   - **So what:** Use public corpora as fixtures, negative controls, and ecological stress tests. Require a consented internal cohort before team or enterprise recommendations. Mark this as an owner-acknowledged limitation, not a new discovery.

8. **§F8 [Kernel Candidate]: Credential exclusion, deletion semantics, provenance, and feedback-loop quarantine are non-optional invariants.**
   - **Evidence:** `credential_only_gate.py` intentionally preserves PII, paths, code, IDs, and ordinary high-entropy data while removing authorization headers, cookies, virtual/API keys, OAuth values, DSN passwords, provider tokens, private keys, signed URL secrets, and known encoded variants. `tests/test_credential_only_gate.py` verifies idempotence, keyed content-free receipts, final rescan fail-closed behavior, and preservation of noncredential PII. `fable5-sensitive-token-scan-2026-07-30.md` found 11 bearer-token-shaped candidates and blocked raw external egress. `trace-commons-memory-h5-concurrency-postgres-2026-07-30.md` found visibility-safe but metadata-nonatomic exposure/withdrawal, REPEATABLE READ revocation limits, lack of persistent non-owner governance writer, provenance deletion requiring tombstone/redaction policy, and lifecycle event coupling gaps.
   - **Reasoning chain:** Authorized content can remain inside scope, but reusable credentials cannot. Deletion does not follow from hiding rows if derivative releases, exposures, candidates, indexes, telemetry, and provenance references persist. A downstream trace influenced by a memory/skill/retrieval release cannot independently validate that release.
   - **Deployment-calibrated severity:** Critical for credentials; high for deletion/provenance/feedback because internal authorization does not make stale or circular evidence valid.
   - **Confidence:** High.
   - **So what:** Install credential-only gating before durable capture, model/evaluator/index/replay/tool paths, output artifacts, and egress. Add influence quarantine and explicit tombstone/redaction policies before production memory/skill/search releases.

## Standalone Concept Assessment

| Concept | Enterprise question it can answer | Required evidence and labels | Deductive status | Invalid implication to reject |
|---|---|---|---|---|
| ATIF | Can selected conversation/tool trajectories be exchanged or turned into portable eval examples? | Source hashes, event mapping, unsupported-field receipt, no silent drops. | Deterministic projection for mapped subset. | ATIF step list proves enterprise authorization, side effects, replay, or memory truth. |
| OpenTelemetry/OpenInference | What operational topology, timing, tool lifecycle, and span navigation exist? | Expected-trace manifest, backend round trip, content/authority allowlist, loss receipt pointer. | Deterministic topology projection when round-tripped. | Span identity retention proves evidence, policy, reward, or replay semantics. |
| AgentRx | Which invariant violation or failure hypothesis should a reviewer inspect? | Declarative invariants, sandboxed checks, human/executable labels, alternatives. | Hypothesis generator. | Checker violation is root cause or user skill gap. |
| Signals | Which traces deserve cheap review before model/judge spending? | Frozen selector, random audit stratum, outcome-blind labels, length baseline. | Statistical selector. | Signal score is diagnosis, frustration, productivity, or competence. |
| AgentEvals | Which stored traces could become audits or replay fixtures? | Assertion type, evidence IDs, mutant tests, allowed-variation false positives, changed-system boundary. | Proposal/audit candidate. | Retrospective assertion sensitivity proves a changed agent will work. |
| Phoenix, Opik, Langfuse | How should datasets, annotations, experiments, feedback, and evaluator revisions be managed? | One authoritative Frankengate dataset/release/eval schema. | Lifecycle concepts only. | A separate tool's dataset/delete/feedback state is a second authority. |
| OpenRCA | Which trace/log/metric/topology alternatives might explain an incident? | Synchronized modalities, topology, alternatives, interventions or replay. | RCA hypothesis. | Correlated spans/logs prove cause. |
| Graphiti | How can temporal episode/fact ideas be represented? | Entity namespace, valid/system time, evidence citations, contradiction edges, ACL traversal tests. | Relational/bitemporal pattern; possible ephemeral graph experiment. | Graph proximity or entity merge establishes authorization, identity, or truth. |
| LangMem | How can create/update/delete memory candidates be generated? | Prompt/model pins, citations, scope, abstention, review, deletion closure. | Proposal generator. | Extracted memory should mutate live store. |
| MemInsight | Which typed task/entity/constraint/outcome fields might structure memory and diagnosis? | Ontology, entity-resolution tests, sensitive-attribute policy, labels. | Schema inspiration. | Attribute inference is automatically valid for enterprise people analytics. |
| Memory Palace | How should verbatim and contextual evidence be retained for recall? | Revision retention, same-name/different-project negatives, valid/system time. | Representation discipline and UX metaphor. | A compact narrative memory is evidence authority. |
| Temporal evidence | What was true or knowable at a query cutoff? | Known-at, valid-at, observed-at, lineage, conflict/gap status. | Kernel invariant. | Later read result can justify earlier abstention or selection. |
| `MEMORY.md` | What reviewed state should be rendered to a file/tool destination? | Release snapshot, citations, scope, expiry, rollback, deletion propagation. | Destination rendering. | File text is canonical evidence. |
| Cloud dreaming | Can background synthesis propose memory/eval/procedure candidates? | Pre-cutoff input release, query independence, generator pins, independent verifier, quarantine. | Experimental proposal mechanism. | Dream output can promote itself or validate itself. |
| ReasoningBank | Can success/failure trajectories yield generalized procedures? | Independent outcomes, family-disjoint source/test, no-skill/placebo controls. | Hypothesis/procedure candidate. | Lesson mined from traces is proven beneficial. |
| Hermes / Jeopard-style skill learning | Can bounded skill artifacts be proposed and released safely? | Protected-write contract, sealed tasks, rollback, independent eval, exact influence receipts. | Lifecycle pattern after causal gate. | Self-evolution can edit live skills because it improved on seen traces. |
| RL environment histories | Can environment interactions support replay or reward-linked learning? | Reset, action, observation, state, termination, resource, and reward provenance. | Valid only with environment attachments. | Flat chat/tool transcript is a replayable environment. |
| CASS | How should local/personal history search feel? | Local rights, import receipts, destination transform, no shared raw index. | UX/import inspiration. | Local store semantics transfer to multi-tenant enterprise authority. |
| Doodlestein/CM | How might memory/control surfaces be ergonomic for agents? | Scope, contestability, deletion, no hidden cognitive/person profiling. | UX/control concept. | Interface convenience is evidence validity. |
| claude-history | Can native histories be imported and searched? | Parser fidelity, native IDs, loss receipts, source rights. | Adapter/fixture concept. | Parsed public histories are an enterprise cohort. |
| Prompt-Scope | How can prompts/sessions be inspected and organized? | Purpose, scope, privacy, trace boundary, evidence citations. | Personal inspection concept. | Prompt similarity is intent or skill. |
| Frankensearch | Can exact/fuzzy/vector retrieval be improved? | ACL-before-retrieval, stale/delete/tombstone tests, bakeoff versus PostgreSQL. | Optional sidecar experiment. | Search index becomes policy or evidence authority. |
| Aurora PostgreSQL JSONB | Can sparse provider/tool payloads live beside typed authority? | Typed relational authority/time/outcome columns, JSON schema validation, migration checks. | Baseline persistent authority. | Authority hidden inside JSONB is enough for RLS and auditing. |
| PostgreSQL FTS / pg_textsearch | Can exact terms, identifiers, and text search find candidates? | Same authorized candidates, query safety, recall/latency labels. | Baseline retrieval lane. | Lexical match is same work or cause. |
| pgvector / VectorChord / pgContext | Can in-database vectors add candidate recall under RLS? | Same candidate set, deletion closure, exact recall oracle, extension operations review. | Conditional in-database candidate lane. | Vector distance is identity, permission, skill, or collaboration. |
| Turbovec / Turbopuffer | Can a specialized or managed vector system beat the in-database lane? | Pre-ranking authorization equivalence, tombstones, HA/PITR/cost proof, no regression. | Replacement candidate only after failure gate. | Feature checklist justifies a second authority. |
| General embedding models | Can semantic paraphrase/procedure similarity add candidates? | Human/executable labels, hard negatives, model/index manifests, RLS tests. | Candidate generator. | General embedding quality proves enterprise adaptation is needed. |
| Enterprise-adapted embeddings | Can organization-specific terminology improve retrieval? | Rights-cleared labels, train/val/test by source/user/team/time, +5 absolute Recall@20, no safety regression. | Premature hypothesis. | Fine-tuning improves general intelligence or user skill. |
| Agentic coding/research traces | Can tool-call-complete histories test import, selectors, eval proposals, and memory candidates? | Native lifecycle, source rights, task/outcome labels, family holdouts. | Mechanics substrate. | Public coding traces imply employee competence or enterprise prevalence. |
| NL2SQL traces with complete tool calls | Can SQL procedures improve governed executable tasks? | DB snapshots, schema/tool calls, authority, SQL attempts, policy verdicts, independent verifier, sealed families. | Best first causal domain after P0 repair. | SQL replay conformance or protocol smoke proves skill benefit. |

## Composition and Non-Composition Matrix

| Composition | Valid interface | Valid conclusion | Contradiction or invalid chain | Smallest falsifier |
|---|---|---|---|---|
| Canonical DAG + ATIF | Loss-receipted export/import for mapped conversation/tool events. | Portable task/eval examples for the represented subset. | ATIF reimport becomes canonical evidence for auth, replay, deletion, or side effect. | Fixture with unsupported authority/tool-side-effect fields must remain unsupported, not coerced. |
| Canonical DAG + OTel/OpenInference | Content-minimized spans with expected-count manifest and receipt pointer. | Operational topology and trace navigation. | OTel backend becomes evidence store or cannot detect upstream whole-trace loss. | Deliberate whole-trace, partial-span, schema-evolution, and duplicate controls. |
| PostgreSQL authority + FTS/vector | Candidate generation after current RLS/purpose/classification/epoch filtering. | Authorized candidate lists and retrieval metrics. | ANN/sidecar candidates influence counts, cache, scores, snippets, or timings before authorization. | Unauthorized exact term/vector neighbor/delete/stale-epoch permission oracle. |
| Signals + AgentRx | Signals select; invariants/hypotheses explain possible mechanisms with alternatives. | Review queue and diagnostic hypothesis. | Selector score renamed "root cause" or "skill gap." | Human/executable labels where signal does not beat length/random or mislabels environment/permission failures. |
| AgentRx + OpenRCA + AgentEvals | Hypothesis, multimodal evidence, and audit/replay proposals stay separate. | Evidence-backed eval or RCA hypothesis. | Retrospective assertion or correlated topology counted as causal proof. | Changed-system replay contradicts stored-trace assertion. |
| Phoenix/Opik/Langfuse concepts + Frankengate | Native release/eval/feedback tables own state. | Better lifecycle ergonomics. | Multiple tools own datasets, feedback, evaluator revisions, or deletions. | Deletion/withdrawal in one tool leaves stale candidate in another. |
| Graphiti + temporal ledger | Graph/episode extraction writes candidates with citations and bitemporal facts in authority. | Temporal fact hypothesis. | Entity merge/proximity bypasses scope, overwrites contradiction, or collapses same-name projects. | Cross-project same-basename and stale/contradictory evidence tests. |
| LangMem + Dreams + Memory Palace + `MEMORY.md` | Extract/propose, verify, release, render; each step cites evidence and scope. | Reviewed memory proposal or destination file. | Direct background write, future-influenced dream, or file text becomes source truth. | Deleted support or target-query-influenced proposal must invalidate release. |
| ReasoningBank/Hermes + NL2SQL replay | Frozen procedure artifacts are tested on sealed family-disjoint tasks. | Causal effect of that artifact for that model/tool/policy. | Generator sees hidden/gold data, judges itself, or later influenced traces validate ancestor. | No-skill/placebo arm matches or beats procedure; hidden canary leaks; security violation occurs. |
| CASS/claude-history/Prompt-Scope + enterprise history | Import adapters emit governed traces and loss receipts. | Personal history/search UX improvements. | Local raw index becomes shared enterprise evidence or training corpus. | Loss receipt missing for transformed/flattened sources; credential candidate appears in exported pack. |
| General embeddings + structured retrieval | Dense lane returns cited candidates within authorized set; exact channel preserved. | Candidate recall lift on labeled task similarity. | Embedding cluster establishes identity, permission, skill, or collaborator. | Hard negatives with same vocabulary but different objective/privilege outrank positives. |
| Enterprise embedding + feedback loop | Reviewed labels, influence tracking, deletion/memorization tests, frozen holdouts. | Representation improvement for retrieval only. | Clicks, generated memories, or influenced success traces become unreviewed positives. | Deletion or influence holdout regression; no +5 absolute Recall@20 over general baseline. |
| RL histories + canonical traces | Environment state, reward, reset, and termination become first-class attachments. | Replay or reward-linked learning in that environment. | Chat/tool transcript treated as environment state. | Reset/divergence test cannot reproduce state or reward. |

## Enterprise Questions Answered and Not Answered

| Question | Deductive answer today | Premises still missing |
|---|---|---|
| What has an authorized user worked on? | Deterministically answerable in local mechanics when native import, authority, source revision, and loss receipts exist. | Production Aurora/failover/concurrency/deletion gates and complete internal adapters. |
| Which traces contain repeated friction or possible recovery? | Candidate selectors are supported for typed errors, bounded later non-error results, retries, malformed records, loops, and structural features. | Independent outcome labels, canonical error taxonomy, environment/tool/permission labels, precision/recall validation. |
| Which stored traces should become evals? | Evidence-linked eval proposals are supported. | Human approval, assertion semantics, changed-system replay, allowed-variation gates, outcome verifier. |
| What should become memory or `MEMORY.md`? | Reviewed, cited, scoped memory candidates can be represented. | Corrected v2 model/human result, source diversity, utility, deletion/influence production proof. |
| Who is doing materially similar work? | Candidate retrieval is partially supported on silver labels and local RLS mechanics. | Human task-family labels, objective/environment/tool labels, consented enterprise cohort, privacy controls. |
| Which cloud/domain skill might a user benefit from? | Not supported as a claim. Only support-opportunity hypotheses are permitted. | Required capability labels, availability/teachable evidence, non-skill alternatives, prospective intervention outcomes. |
| Which prompt, tool, memory, route, model, or skill improves outcomes? | Not supported yet. NL2SQL is the best first causal domain after protocol repair. | No-skill/placebo controls, sealed families, fixed model/tool/budget, independent evaluator, influence tracking. |
| Should two users be introduced? | Not supported. | Q1 retrieval labels, reciprocal opt-in, minimum cohorts, no cross-scope disclosure, measured collaboration outcomes. |
| Should Frankengate leave Aurora/PostgreSQL? | No current deductive basis. | Frozen workload failure after tuning on selective RLS, p95/p99/concurrency, deletion closure, extension availability, HA/PITR/cost. |
| Should an enterprise embedding be trained? | Premature. | Frozen labeled hard slice where exact/structured/FTS/general-dense fail; rights, deletion, memorization, and no-regression tests. |
| What remains impossible or socially unsafe? | Person-level competence, productivity, protected traits, intent, off-platform effort, hidden-manager surveillance, and causation from passive traces alone. | These require either unacceptable inference or dedicated consented studies and still may remain policy-prohibited. |

## Empirical Tests and Falsifiers

1. **Projection invariant test:** Round-trip canonical fixtures through ATIF, OTel/OpenInference, AgentEvals exports, and any production telemetry backend. Falsify canonical use if any authority, parentage, observation status, tool proposal/result, deletion, or expected-count field silently disappears.

2. **Permission oracle test:** For SQL, FTS, pgvector, graph/search sidecars, caches, snippets, cursors, aggregates, telemetry, exports, and model inputs, compare unauthorized, stale-epoch, revoked-team, withdrawn-release, deleted-source, wrong-purpose, and classification-denied queries. Falsify a backend if hidden rows affect count, score, distance, timing, cache hit, cursor, or error wording.

3. **Same-work retrieval test:** Freeze human-adjudicated positives and hard negatives with exact objective, environment, tool, permission, and task-family labels. Falsify dense/custom embeddings if exact/structured/lexical baselines match them or if same-vocabulary/different-objective and same-objective/different-privilege negatives outrank positives.

4. **Friction/recovery test:** Have reviewers label bounded episodes for actual task outcome, retry relationship, environment blocker, permission/tool cause, and user action. Falsify structural recovery if precision/recall does not exceed cheaper selectors or if non-error results frequently fail task outcomes.

5. **Root-cause and eval test:** Separate stored-trace audit assertions from changed-system replay. Falsify root-cause language if deterministic or LLM localization does not beat reverse chronology and calibrated abstention on independent labels, or if mutation-sensitive assertions fail benign variation controls.

6. **Corrected memory v2 test:** Run latest snapshot, temporal ledger, and temporal plus released dream with hidden labels, query-independent generation, whole-item budgets, credential gate, runtime attestation, and source/project stratification. Falsify memory benefit if temporal/dream arms do not reduce harmful selection versus controls, if future/lineage leakage occurs, or if diversity gates fail.

7. **NL2SQL causal skill test:** Repair terminal protocol arm-independently, rerun P0, then compare no artifact, length-matched placebo, and one frozen reviewed trace-mined procedure on family-disjoint tasks. Falsify skill learning if the procedure fails to beat both controls, any unauthorized observation occurs, or gains vanish on hidden families.

8. **Influence quarantine test:** Mark every memory, skill, route, retrieval release, prompt, model, index, and eval exposure. Falsify release validation if a descendant trace is counted as independent evidence for its ancestor outside a declared exposure/control analysis.

9. **Aurora operations test:** Run production-like ingest/search/delete/re-embed/release/aggregate workloads with selective RLS, deletion churn, failover, reader lag, RDS Proxy, backup/restore, and cold-cache/concurrent queries. Falsify Aurora-first only after measured tuning fails a named SLO or correctness gate.

10. **Credential and egress test:** Apply credential-only transform to capture, model input/output, evaluator, index, tool input/output, replay, export, and sidecar paths, including encoded/chunked/homoglyph/private-key/DSN/signed-URL cases. Falsify an egress path if any reusable credential or known secret variant survives.

## Architecture Consequences

The A1 architecture follows from the premises:

- **Authority invariant:** every claim must carry the authority envelope that made its evidence visible: tenant, subject, team, audience, purpose, classification, policy revision, authorization epoch, and current-validity check.
- **Identity invariant:** same artifact, task, person, project, database, or fact identity cannot be inferred from string/vector similarity. It needs explicit keys or reviewed equivalence relations.
- **Time invariant:** every memory, fact, release, and outcome needs at least observed/source time, valid time, known/system time, and release/exposure time. Later evidence cannot be used as if known earlier.
- **Provenance invariant:** every derived artifact needs exact evidence IDs, source hashes, adapter/projection revisions, model/prompt/tool/policy versions, and loss receipts. Projection loss is part of the claim.
- **Tool-call invariant:** proposal, authorization, dispatch, execution, result, durable side effect, terminal submission, refusal, retry, fallback, cancellation, and missingness are different states.
- **Deletion invariant:** deletion and withdrawal must close over candidates, releases, exports, indexes, caches, telemetry pointers, influences, and rendered files. If raw evidence must be retained as provenance, it needs a tombstone/redaction policy rather than accidental FK protection.
- **Feedback invariant:** influenced traces are not independent validation for the artifact that influenced them. Influence lineage is required for memories, skills, prompts, routes, retrieval releases, models, indexes, and evals.

Smallest architecture that satisfies these invariants:

1. Frankengate gateway/governance remains the enforcement point.
2. Aurora/PostgreSQL holds canonical traces, authority, JSONB payloads, exact/structured search, FTS, bounded pgvector, bitemporal facts, candidates, releases, exposures, influence, evals, deletion/tombstones, and experiment manifests.
3. Existing object storage holds large immutable content and raw internal audits under explicit scope.
4. ATIF, OTel/OpenInference, Phoenix/Opik/Langfuse-compatible datasets, `MEMORY.md`, Frankensearch, Graphiti, LangMem, and vector services are projections or experiments, not authorities.
5. A worker/evaluator plane runs credential gates, proposal generation, replay, and model calls with signed receipts and capability isolation.

Architecture changes not justified now:

- A production graph database for memory.
- A production external vector/search authority.
- Enterprise-adapted embeddings.
- Automatic memory or skill writes.
- Cross-user named similarity/collaboration.
- Manager dashboards that rank people by friction, skill, productivity, or model usage.
- Leaving Aurora/PostgreSQL before the operations/retrieval gates fail.

## Risks Identified

- **Projection laundering:** lossy ATIF/OTel/eval exports are reimported as evidence.
- **Post-filtered retrieval leakage:** unauthorized candidates affect scores, counts, snippets, timing, or caches.
- **Similarity-to-identity conflation:** vector/lexical neighbors become "same work," "same user need," or "collaborator."
- **Selector-to-diagnosis conflation:** Signals, deterministic invariants, or LLM judges become root-cause labels.
- **Recovery overclaim:** later non-error tool result becomes "success" or "causal repair."
- **Skill-gap overclaim:** repeated failures become employee capability or productivity claims.
- **Future leakage:** later reads, hidden labels, or descendants affect pre-cutoff memory/retrieval decisions.
- **Circular validation:** generated memory/skill/retrieval release influences traces later counted as independent support.
- **Deletion residue:** withdrawn/deleted evidence remains in releases, exposures, indexes, caches, telemetry, or rendered files.
- **Credential boundary failure:** public availability, same-scope PII permission, or raw trace usefulness is mistaken for credential safety.
- **Framework stacking:** Phoenix/Opik/Langfuse/Graphiti/LangMem/vector sidecars each own partial lifecycle state.
- **Local-to-production overreach:** local PostgreSQL mechanics are treated as Aurora operations, scale, failover, and concurrency proof.

## Recommendations

1. Add a claim-type field to every user-visible and API-visible inference: `observed`, `candidate`, `reviewed_release`, `statistical_estimate`, `causal_effect`, or `unsupported`.
2. Make evidence receipts first-class. A claim should link to evidence IDs, projection loss receipts, authority epoch, valid/known time, source hash, derivation revision, and influence state.
3. Keep the first product private and proposal-oriented: personal history, exact/structured search, evidence previews, friction/recovery review queues, and cited eval/procedure/memory proposals.
4. Ban product language that says "skill gap," "root cause," "collaborator," "productivity," or "learned" unless the needed premises and experiments exist.
5. Run the permission-oracle gauntlet before any sidecar, cache, aggregate, telemetry backend, or vector service can influence user-visible results.
6. Implement influence quarantine before releasing memory, skill, prompt, route, model, retrieval, index, or eval artifacts.
7. Repair NL2SQL protocol and use it as the first causal skill-learning domain. Do not generalize from SQL to all enterprise work until external-validity studies pass.
8. Treat Graphiti, LangMem, Dreams, ReasoningBank, Hermes, Phoenix, Opik, Langfuse, OpenRCA, Frankensearch, Turbopuffer, Turbovec, VectorChord, pg_textsearch, and pgContext as experimental arms or implementation references until they beat the one-authority baseline under the same premises.

## New Ideas and Extensions

- **Proof-carrying claim cards:** every UI/API claim carries a compact premise checklist: authority, identity, time, provenance, tool lifecycle, outcome, intervention, independence, deletion, and feedback status.
- **Inference linter:** block or downgrade claims when copy/API fields imply causation, skill, identity, or collaboration from candidate-only evidence.
- **Evidence algebra:** formalize operations such as `project`, `filter_authorized`, `derive_candidate`, `review_release`, `expose`, `influence`, `delete`, and `validate_independent`; forbid invalid compositions by type.
- **Permission-oracle differential test suite:** one harness that replays the same query over authorized, unauthorized, stale, revoked, withdrawn, deleted, and sidecar paths and compares all observable outputs.
- **Influence quarantine ledger:** a table keyed by artifact release and downstream trace so validation code can automatically exclude descendants from independent support.
- **Claim downgrade receipts:** when a result is useful but underpowered, confounded, or missing a premise, store the exact downgrade reason rather than only a boolean failure.
- **Non-composition fuzzing:** generate traces where similarity, basename, task label, or tool family is intentionally misleading; require every memory/search/diagnosis arm to abstain or mark candidate-only.

## Assumptions Ledger

- The deployment is internal and policy-governed; authorized same-scope users/admins may see full PII/classified trace content.
- Reusable credentials are never ordinary trace content and must be stripped before durable capture or any model/evaluator/index/replay/export path.
- Frankengate governance remains the enforcement point.
- Public corpora are valid for parser/mechanics and negative controls when admitted by manifest, but not for employee or enterprise-population inference.
- The current local PostgreSQL results are meaningful mechanics evidence but not Aurora production operations proof.
- Current corrected v2 memory primitives are preregistered or implemented, but no corrected model result exists.
- Existing sibling mode outputs are treated as perspective context, not as primary evidence for A1 findings.

## Questions for Project Owner

1. Which first product surface should carry cross-user aggregate patterns, if any, before a consented prospective cohort exists?
2. What minimum cohort and complement-suppression rules should apply to team/admin aggregates?
3. Should artifact-first introductions be allowed after reciprocal opt-in, or should named collaboration remain out of scope for the first release?
4. What production SLOs will define "Aurora failed after tuning" for selective-RLS retrieval?
5. What policy should govern provenance source deletion: hard delete, tombstone, redacted retained proof, or time-limited legal hold?
6. Which internal NL2SQL or BI task families can be consented and labeled without turning the study into employee evaluation?

## Points of Uncertainty

- Whether Aurora with pgvector/FTS/structured views will meet hundreds-of-GB selective-RLS latency and concurrency targets after realistic tuning.
- Whether human task-family labels will agree enough to validate same-work retrieval beyond silver public labels.
- Whether corrected v2 memory arms will produce useful discordant results after blinding, true bitemporality, query-independent dreams, and runtime attestation.
- Whether a trace-mined SQL procedure can beat no-skill/placebo after terminal protocol repair.
- Whether graph traversal will provide real value after relational bitemporal recursive queries are benchmarked.
- Whether enterprise-adapted embeddings will improve private terminology retrieval without memorization, deletion, or exact-identifier regression.
- How strict aggregate privacy should be in an internal admin context where raw access may be authorized but people-analytics misuse remains possible.

## Agreements and Tensions with Other Perspectives

- **Agreement with B9 Simplicity/MDL:** A1 reaches the same kernel from a different route. B9 says one governed authority minimizes system description length; A1 says the same authority is necessary because otherwise the premises for authority, time, identity, deletion, and influence split across systems and invalid implications become hard to detect.
- **Agreement with L2 Debiasing:** L2 warns that mechanics success can be overweighted. A1 formalizes why: a mechanics pass satisfies representation or authorization premises, not outcome, causation, or intervention-benefit premises.
- **Agreement with H2 Adversarial Review:** H2 emphasizes people-finder, post-filtering, and self-validating memory/skill attacks. A1 recasts those as violations of identity, authority, and feedback-loop invariants.
- **Agreement with I4 Perspective-Taking:** I4 argues adoption depends on presenting evidence and proposals, not employee-insight oracles. A1 supplies the rule for that product language: every claim must state which premises it has and which it lacks.
- **Tension with likely F7 Systems Thinking:** Systems thinking may want to model broad feedback loops early. A1 agrees feedback loops are load-bearing, but insists they cannot validate themselves. Any reinforcing loop must have influence quarantine and external holdouts before being treated as learning.
- **Tension with likely G6 Multi-Criteria Decision:** G6 may rank architectures by cost, latency, and operational burden. A1 says no favorable score can compensate for missing authority/deletion/provenance premises; such architectures are invalid before they are suboptimal.
- **Tension with likely K2/F1:** Scientific and causal modes may push for broader factorials. A1 supports factorials only after each arm's inputs are type-equivalent and non-circular; otherwise interaction estimates are syntactically impressive but logically invalid.

## Confidence

Overall confidence: **High** for deductive claim boundaries and invariants; **medium** for specific future architecture thresholds.

| Area | Confidence | Reason |
|---|---:|---|
| Projection cannot replace canonical evidence | High | Direct E0/OTel results and adapter code show exact retained and missing premises. |
| Authority-before-ranking invariant | High | Multiple local RLS and broker tests support the rule; production sidecars remain untested. |
| Similarity cannot imply identity/skill/collaboration | High | This follows deductively and is repeatedly owner-acknowledged. |
| Friction/recovery cannot imply cause/skill | High | Current artifacts lack independent outcomes and causal interventions. |
| Memory proposal/release/influence ledger is necessary | High | Bitemporal, H5, concurrency, and pilot confounds all point to the same invariant. |
| NL2SQL as first causal domain | Medium-high | It has executable outcomes and tool calls, but P0 protocol failed and hidden remains sealed. |
| Aurora/PostgreSQL sufficiency | Medium | Local mechanics are strong; production operations and scale remain open. |
| No custom embedding now | High | Current gates and retrieval results do not justify training; future hard-slice results could change this. |
