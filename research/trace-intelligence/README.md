# Frankengate trace-intelligence research harness

This directory is the reproducible artifact for the trace-intelligence empirical
program. It is deliberately separate from the production analytics service.

The current broad program, including the independent concept audit, measured
negative results, staged composition tests, and architecture reversal gates, is
documented in
[`enterprise-trace-intelligence-independent-and-composed-program-2026.md`](../../docs/roadmap/research/enterprise-trace-intelligence-independent-and-composed-program-2026.md).
The program treats AgentRx, Signals, AgentEvals, temporal/graph memory,
dreaming, skill learning, similar-work discovery, collaboration, and embedding
adaptation as separable mechanisms. Product or framework names do not count as
empirical evidence.

The latest public-data discovery audit adds a rights- and provenance-gated queue
of Hugging Face candidates spanning native user sessions, OTel-native traces, and
labeled workflow/diagnosis traces. It is discovery only until revisions and
licenses are frozen; see
[`huggingface-agent-trace-discovery-2026-07-31.md`](experiments/summaries/huggingface-agent-trace-discovery-2026-07-31.md).

Latest public-OTel and composition checkpoints:

- [`DiscoPosse OTel shard audit`](experiments/summaries/hf-disco-otel-shard-audit-2026-07-31.md)
  projects a pinned shard through canonical, ATIF, and OpenInference/OTel
  adapters with explicit loss accounting;
- [`workload-stratified Signals results`](experiments/summaries/hf-disco-otel-signals-2026-07-31.md)
  and its [`browsecompplus negative control`](experiments/summaries/hf-disco-otel-signals-browsecomp-2026-07-31.md)
  show workload-sensitive selector behavior;
- [`governed hypothesis policy experiment`](experiments/summaries/hypothesis-policy-experiment-2026-07-31.md)
  and [`resettable intervention replay`](experiments/summaries/hypothesis-intervention-replay-2026-07-31.md)
  validate controls and isolation without claiming causal utility; and
- [`public OTel composition gate`](experiments/summaries/public-otel-composition-gate-2026-07-31.md)
  fails closed and defers automatic promotion.

The current requirement-level status is captured in the
[`program completion audit`](experiments/summaries/program-completion-audit-2026-08-01.md).
It records the program as active/incomplete: local mechanics and publication
are proven, while CMU raw access, managed Aurora operations, and causal
enterprise outcomes remain open.

## Historical Claude/Codex mining

The historical-log work is tracked in GitHub epic
[#125](https://github.com/pierretokns/frankengate/issues/125) and its
friction, intent, benchmark, and review subissues. The native Claude adapter
([`native_history_friction_mining.py`](native_history_friction_mining.py))
and Codex rollout adapter
([`codex_history_friction_mining.py`](codex_history_friction_mining.py)) keep
structured executor outcomes separate from text-level error markers, preserve
native provenance, and emit content-free aggregate receipts.

The Claude screen covers 28 public histories, 413 user prompts, 4,264 tool
calls, and 269 structured tool-result errors (6.31%); the text scanner would
have called 762 results errors. The Codex screen covers 34 small public
sessions, 3,182 function calls, and 255 non-zero exit-code outputs versus 535
keyword markers. These are detector screens, not friction, satisfaction,
intent, or skill labels. The next required gate is blinded episode
adjudication stratified by executor outcome, correction/retry/rephrase, and
clean controls, followed by replayable-eval promotion only when an expected
artifact and validator exist. See the Claude
[`summary`](experiments/summaries/native-history-friction-tracelab-2026-08-02.md)
and Codex
[`summary`](experiments/summaries/codex-history-friction-public-local-2026-08-02.md).

The companion [`signal association analysis`](experiments/summaries/native-history-signal-association-tracelab-2026-08-02.md)
finds negative session-level rank correlations between structured-error rate
and dissatisfaction, correction, retry, and clarification counts. This is a
useful detector failure mode: global error density mistakes long productive
exploration for friction. Episode ordering, recovery, abandonment, terminal
outcome, and adjudicated labels are required.

The [`NL2SQL alias baseline`](experiments/summaries/nl2sql-alias-mining-cohort-2026-08-02.md)
uses 314 pinned Defog PostgreSQL rows and links only exact morphological surface
variants to identifiers in gold SQL. It found 492 links and 13 cross-database
collision classes. This is evidence that alias/collision mining has a measurable
lexical starting point, not evidence of semantic alias truth. Human/frontier
adjudication and same-surface/different-system hard negatives remain open.

The [`GLiNER term-extraction probe`](experiments/summaries/term-extraction-gliner-wisp-2026-08-04.md)
tested a typed-span candidate generator on 49 admitted Wisp documents. A
deterministic pass found 15,391 unique terms, 666 acronym forms, and 191
reformulation candidates; GLiNER emitted 567 spans. An initial context-free
probe hit `2/8`, while a corrected contextual probe hit `7/8`; output still
over-produced project/tool labels. This supports a review-queue role for
zero-shot term extraction, not automatic corporate alias or ontology promotion.
The independent [`Termolator termhood probe`](experiments/summaries/termolator-wisp-2026-08-04.md)
also completed on the same 49-document cohort: it emitted 3,000 candidates,
the configured cap, with a 1.61-token mean among the top 100. This establishes
that a classical foreground/background baseline is runnable, not that its
terms are correct. Blinded labels, alias/NIL handling, and retrieval impact
remain open.

The bounded [`query-expansion probe`](experiments/summaries/query-expansion-probe-2026-08-01.md)
shows why this must remain a search-only projection: approved keyword,
pseudo-document, entity, and document enrichment improved a six-document toy
fixture, while corpus-feedback expansion did not. It is a mechanics control,
not evidence of enterprise semantic generalization.

The first search-impact control is the [`train-only alias enrichment replay`](experiments/summaries/nl2sql-alias-enrichment-2026-08-04.md).
On 41 held-out Defog rows, aliases covered only 2/260 target objects at
support-one and 17/260 at support-two; MRR was unchanged at support-one and
fell slightly at support-two. This is a public-proxy coverage null, not a
rejection of reviewed enterprise vocabulary mining.

The bounded [`query-expansion mechanics probe`](experiments/summaries/query-expansion-probe-2026-08-01.md)
then tested transparent proxies for QueryGym, ConvGQR, and SIRA-style arms on
12 synthetic cases. Approved keyword/pseudo-document/entity/document
enrichment improved MRR from `.8472` to `.9583`; a history-plus-follow-up
rewrite improved the two conversational cases from `1/2` to `2/2`; corpus
feedback was unchanged. These are mechanics results, not replications of the
named systems or enterprise evidence.

The follow-up [`NL2SQL identifier hard-negative benchmark`](experiments/summaries/nl2sql-identifier-hard-negative-2026-08-02.md)
made those collisions executable. On 492 conservative links, exact identifier
matching with known database scope reached MRR `0.6867` / Recall@5 `0.9980`,
while `nomic-embed-text` with scope reached MRR `0.4151` / Recall@5 `0.7236`.
Unfiltered exact matching had a 14.43% same-surface collision-before-target
rate; scope filtering reduced it to 0.20%. This is a retrieval baseline, not
semantic alias truth or agent utility, but it establishes that structured
identifier/scope lanes must remain ahead of generic dense retrieval.

A frontier calibration pass ([`NL2SQL collision-sample adjudication`](experiments/summaries/nl2sql-alias-frontier-adjudication-2026-08-02.md))
then used `gpt-5.6-luna` on 22 public collision cases: 22/22 in-scope
candidates were accepted as exact/semantic aliases and 40/40 cross-scope
candidates were labeled wrong-system. This calibrates the hard-negative
construction only; it is not independent human truth, and its generic sample
contained no `nil`/`unclear` cases.

The [`MATM embedding/model cascade audit`](experiments/summaries/matm-embedding-model-cascade-audit-2026-08-02.md)
joins two same-revision leave-one-model-out receipts without pooling their
different targets. Action-only embeddings improved candidate Recall@20 by
`+0.123` over lexical action retrieval, while outcome-conditioned successful
neighbors improved the top-10 success rate by `+0.067` but had an AUC delta of
`-0.056`; both confidence intervals cross zero for the outcome prioritization
claim. This supports embeddings as candidate generation and outcome/model
scoring as review prioritization, not autonomous skill release.

The first [`fold-local domain embedding adapter`](experiments/summaries/matm-domain-embedding-adapter-2026-08-02.md)
was then trained only on non-held-out MATM models using repeated-work positives
and high-similarity different-work negatives. Recall@20 changed from `0.5301`
to `0.5331` (bootstrap CI crosses zero), while MRR changed from `0.3315` to
`0.3300` (CI crosses zero). This is a neutral adapter result, not a rejection
of corporate fine-tuning: the silver labels and simple metric learner are not
enterprise alias truth. It does establish that custom adaptation must earn its
promotion on adjudicated hard negatives and downstream artifact utility.

The [`artifact capsule reuse lab`](experiments/summaries/artifact-capsule-reuse-2026-08-02.md)
adds the missing executable-capsule mechanic. A parameterized SQL capsule was
accepted only under its recorded scope, epoch, schema fingerprint, parameter
contract, freshness, and result shape; stale epoch, wrong scope, expiry,
parameter mismatch, and schema drift all failed closed. Bound injection-shaped
parameters were never interpreted as SQL. This is a SQLite mechanics proof,
not PostgreSQL/Aurora semantic equivalence or artifact utility.

The follow-up [`artifact_capsule_postgres_reuse.py`](artifact_capsule_postgres_reuse.py)
binds the same capsule contract to the real governed executor against a
disposable PostgreSQL 16.12 instance. It creates a temporary RLS-enabled table
and least-privilege role, then verifies valid bound reuse, stale epoch/scope,
expiry, parameter mismatch, schema drift, and injection-shaped values. The
receipt shows all five denial cases fail closed and that the injection-shaped
value is bound (zero rows), never interpreted as SQL. This is still a
mechanics proof; it does not establish mined-artifact utility or semantic
equivalence. See
[`experiments/summaries/artifact-capsule-postgresql-reuse-2026-08-02.md`](experiments/summaries/artifact-capsule-postgresql-reuse-2026-08-02.md).

The historical-log research contract and prior-art survey are recorded in
[`experiments/summaries/historical-trace-mining-prior-art-2026-08-02.md`](experiments/summaries/historical-trace-mining-prior-art-2026-08-02.md).

The first independent/composed checkpoint is available in:

- [`trace-signal-diagnosis-eval-chain-wisp-2026-07-30.md`](experiments/summaries/trace-signal-diagnosis-eval-chain-wisp-2026-07-30.md),
  a natural-history concept proxy with no changed-system execution;
- [`wisp-recovery-adjudication-packet-2026-07-30.md`](experiments/summaries/wisp-recovery-adjudication-packet-2026-07-30.md),
  which produces the blinded human-labeling set; and
- [`memory-mechanism-factorial-fixture-2026-07-30.md`](experiments/summaries/memory-mechanism-factorial-fixture-2026-07-30.md),
  a complete six-mechanism fixture that establishes mechanics, not utility.

The paired
[`Wisp PostgreSQL planner-statistics experiment`](experiments/summaries/wisp-postgres-planner-statistics-2026-07-30.md)
shows why database alternatives remain behind measured failure gates. On the
same governed rows, `ANALYZE` reduced controlled-FTS p50 from 57.188 ms to
2.167 ms while all denied authorities continued to receive zero pre-ranking
candidates.

The new [`planner readiness gate`](experiments/summaries/planner-readiness-gate-2026-08-02.md)
turns that observation into a deterministic release check: the fresh
bulk-load phase is `not_ready`, while the post-`ANALYZE` phase is `ready` only
after all four frozen p50 budgets, zero-denial checks, and required redacted
plan signatures pass. This remains a local PostgreSQL gate, not an Aurora SLO
or failover claim.

The
[`natural trace memory factorial`](experiments/summaries/natural-trace-memory-factorial-2026-07-30.md)
runs 16 arms over 23 later-read queries. Latest-only, verbatim, bitemporal,
evidence retrieval, and every composition tied at 16 exact and 7 stale
outcomes. This is a real negative result: the corpus exposes useful pre-query
evidence but does not contain the target types needed to distinguish the
mechanisms.

The separately sourced
[`“Jeopard” identity report`](../../docs/roadmap/research/jeopard-gepa-identity-resolution-and-integration-protocol-2026.md)
resolves the requested system to GEPA/gskill with high confidence and defines
it as an optional candidate-search treatment, not a trace store or release
authority.

The
[`upstream AgentEvals interoperability run`](experiments/summaries/agentevals-upstream-wisp-2026-07-30.md)
executes the pinned v0.9.7 library on three natural Wisp histories. Its
deterministic modes cleanly separate tool order from membership/arguments. The
local semantic judge caught all response reversals but rejected one unmodified
baseline, so it cannot be the sole release gate.

The follow-up
[`changed-system replay`](experiments/summaries/changed-system-replay-wisp-2026-07-30.md)
executes resettable original, benign-audit, and harmful-drop implementations.
Exact matching catches the harmful change but also rejects every benign audit
addition; ordered and unordered matching accept the benign addition while
catching every tested omission. The result is prospective for the bounded
transition model, not a reconstruction of the source host.

The
[`recovery-label stability study`](experiments/summaries/wisp-recovery-model-adjudication-stability-2026-07-30.md)
runs three prompt-order/skepticism variants over six blinded natural episodes.
Outcome and relation were moderately stable; usefulness and evidence strength
were not. These are review-prioritization signals, not gold labels.

The
[`ATIF/OTel coding-and-RL round trip`](experiments/summaries/atif-rl-roundtrip-2026-07-30.md)
measures exact capability-fact retention over 88 Wisp coding trajectories and
2,130 MATM ALFWorld trajectories. Both projections lose load-bearing evidence,
especially RL reset/reward/termination state; preserving event identity is not
the same as preserving a replayable environment.

The follow-up
[`ATIF capability-extension run`](experiments/summaries/atif-capability-extension-2026-08-02.md)
adds a versioned `extra.frankengate.capability_extension` v2 profile rather than
changing portable ATIF. Profile-aware round trips completed for all 88 Wisp and
2,130 MATM trajectories, retaining structural authority/epoch, reset and
termination, reward, replay-reference, and memory-lineage facts. A frontier
Luna schema review required explicit hash/canonicalization, reader-version,
governed-reference, retention, and reset/termination semantics; those boundaries
are now in the contract. Prompt/tool payloads and opaque state snapshots remain
hash-only and receipted; the profile is therefore a compatibility aid, not an
evidence authority or replay guarantee.

The corrected
[`Defog NL2SQL terminal-protocol P0`](experiments/summaries/defog-sql-terminal-protocol-repair-p0-2026-07-30.md)
eliminates all missing terminal actions across twelve real model/PostgreSQL
episodes. No-skill, placebo, and expert arms still solve the same two of four
tasks, so trace-mined and hidden-family arms remain sealed.

The bounded
[`faithful Graphiti/LangMem run`](experiments/summaries/faithful-memory-components-2026-07-30.md)
uses the real pinned libraries. Both pass small structured smokes, but no
natural case completes: Graphiti returns empty structured responses on the
first full document and hits the experiment ceiling. No proxy score is
substituted, and neither component has earned a production role.

The follow-up [`independent LangMem natural arm`](experiments/summaries/langmem-natural-independent-2026-08-01-r2.md)
removed the Graphiti timeout as a confounder. The real LangMem manager executed
on all 3/3 selected Wisp/Fable cases, but returned zero durable candidates,
zero exact-identifier recall, and zero existing-memory updates. This is a
faithful model/runtime outcome—not a proxy—and still does not establish memory
quality, utility, or enterprise transfer.

The [`Llama 3.2 alternative natural arm`](experiments/summaries/faithful-memory-components-llama32-natural-2026-08-02.md)
then ran the same cohort with an explicit unpinned model override. LangMem
completed one case before two typed `AttributeError` failures; Graphiti reached
one case and returned a typed `ValidationError`; no natural Graphiti case
completed. This rules out treating the Qwen3 failure as the only boundary, but
it is still a negative execution result, not a component-quality score.

The [`faithful diagnosis-concept audit`](experiments/summaries/faithful-diagnosis-concept-audit-wisp-2026-07-30.md)
runs deterministic Signals and AgentRx concepts over 104 pinned Wisp histories.
The queue selected 11/21 candidates with tool errors, versus 7 for a length
baseline and 2 for seeded random. This is descriptive screening, not accuracy:
there were no independent informative-trace labels. The AgentRx-style layer
emitted 11 evidence-linked hypotheses, zero abstentions, and zero root-cause
claims. OpenRCA is not executable on this corpus because aligned timestamps,
metrics, topology, and environment snapshots are absent.

The [`retrieval backend parity study`](experiments/summaries/retrieval-backend-parity-e2-2026-07-30.md)
reuses the pinned 145-document/99-query cohort and forced-RLS PostgreSQL
receipts. PostgreSQL remains the authority. CASS 0.6.22 was capability-probed
but its installed index is not the same corpus; Frankensearch, pg_textsearch,
pgContext, and Turbopuffer remain explicit nulls rather than invented scores.
TurboVec now has a same-corpus adapter checkpoint
([summary](experiments/summaries/turbovec-codetracebench-2026-07-31.md)): its
2-bit local index matched exact dense Recall@20 on this slice and passed
allowlist, persistence, and deletion checks, but it is still only a dense
component—not an authority, lexical engine, or skill system. Promotion requires
same-corpus relevance, pre-ranking authorization, deletion closure, latency,
and cost evidence.

The CASS recovery pass found a genuinely new architecture question: whether a
Palantir/Semantica-style typed, temporal context graph adds value above the
canonical trajectory DAG. The recovered work also describes TypeGraph-style
BM25 + vector + graph traversal compiled into one SQL query, and schema-first
ontology bootstrapping before frontier refinement. These are now captured as
an empirical projection protocol, not adopted dependencies:
[`CASS architecture refresh`](experiments/summaries/cass-prior-research-architecture-refresh-2026-08-04.md)
and [`ontology/action replay protocol`](experiments/protocols/ontology-action-trace-architecture-2026-08-04.md).
The initial implementation target is the existing governed PostgreSQL fixture:
typed objects and evidence-linked edges, recursive SQL expansion, FTS, and
optional pgvector. A graph database is explicitly out of scope until graph
expansion is measured as the bottleneck.

The first independent vocabulary run is now complete:
[`GLiNER/Wisp probe`](experiments/summaries/term-extraction-gliner-wisp-2026-08-04.md).
On 49 non-empty Wisp files, the deterministic baseline surfaced 666 acronym
forms and 191 reformulation candidates; GLiNER produced 567 typed spans. The
corrected contextual probe hit 7/8 expected labels (the initial context-free
probe hit 2/8), so GLiNER is currently a candidate-span generator, not an
automatic glossary or ontology writer. The
receipt verifier passed, and raw spans remain outside Git.
Termolator independently completed on the same 49 documents and reached its
3,000-candidate cap; this is a runnable termhood baseline, not a quality result.

The [`FinanceBench embedding-choice benchmark`](experiments/summaries/finance-mteb-retrieval-benchmark-2026-08-02.md)
adds a separate finance/NL2SQL relevance gate over the cached, revision-pinned
FinanceMTEB/FinanceBench corpus (189 documents, 150 queries, 35 multi-positive
queries). The finance-specialized `BalyasnyAI/multilingual-e5-base` reached
Recall@20 1.000 and MRR 0.809, ahead of Qwen3-Embedding-0.6B (0.993 / 0.716)
and TF-IDF (0.687 / 0.301) on this slice. This is strong evidence for testing
a finance-specialized embedding in a governed shadow lane, not a production
promotion: the data has no enterprise hard-negative labels, and the run did
not evaluate RLS, deletion, Aurora behavior, or cross-domain transfer. Raw
texts and vectors remain outside Git; the runner is
`finance_mteb_retrieval_benchmark.py`.

The [`FinanceBench harness-parity gate`](experiments/summaries/finance-mteb-harness-parity-2026-08-02.md)
replayed the same 2,500-character projection through the loopback Ollama
`nomic-embed-text:latest` API. The local Ollama arm reached Recall@20 0.453 and
MRR 0.166, versus Recall@20 1.000 and MRR 0.811 for the local
SentenceTransformers BalyasnyAI arm. The gap is a real model/harness finding,
not an authorization result: nomic's bounded projection truncated 82 filings,
and neither arm exercised RLS or deletion. Frankengate should not silently use
the existing nomic endpoint for finance trace retrieval; a finance-specialized
model needs its own governed serving lane and parity test.
The Ollama arm is implemented by `finance_mteb_ollama_embedding_benchmark.py`
and joined by `finance_mteb_harness_parity.py`; its loopback endpoint and
context projection are recorded in the machine-readable receipts.

The [`FinanceBench governed pgvector replay`](experiments/summaries/finance-governed-retrieval-2026-08-02.md)
then loaded the same projected corpus into a disposable PostgreSQL 16 +
pgvector 0.8.1 table with native `vector(768)` storage, HNSW, forced RLS, and
a `NOSUPERUSER NOBYPASSRLS` application role. The BalyasnyAI arm retained
Recall@20 1.000 and MRR 0.802 at a 2.023 ms p50 query latency. Six negative
authority cases (tenant, subject, stale/missing epoch, purpose, and clearance)
returned zero candidates; a deleted document disappeared before ranking; and
the data transaction rolled back to zero rows before table cleanup. This is
the first local evidence that finance-specialized retrieval can compose with
Frankengate's policy-before-ranking and deletion contract. It does not claim
Aurora scale, failover, or production promotion. The migration and runner are
`sql/012_finance_retrieval_768.sql` and
`finance_governed_retrieval_replay.py`.

The [`skill-learning faithful preflight`](experiments/summaries/skill-learning-faithful-preflight-2026-07-30.md)
audits pinned Hermes Self-Evolution, GEPA/gskill, ReasoningBank, and
Trace2Skill implementations. It finds no executable natural-trace candidate
generation plus held-out outcome path in this checkout. Hermes also has a
source-contract mismatch: it extracts body-only skill text while the validator
requires frontmatter, and it contains a direct live skill write. These are
typed nulls and source findings, not evidence that the mechanisms cannot work.
No SKILL.md or MEMORY.md was activated or written.

The [`current SkillOpt / SkillOpt-Sleep / RHO / SkillGen audit`](experiments/summaries/skill-improvement-strategy-audit-2026-07-30.md)
now pins Microsoft's current SkillOpt source and v0.2.0 release. Its local
deterministic mock experiment moved held-out score from 0.3333 to 1.0 and
blocked a harmful edit, proving only the gate plumbing. External SkillOpt
reports claim 52/52 best-or-tied cells and Sleep replay gains, while RHO and
SkillGen report promising external results; none is a natural Frankengate
intervention with independent enterprise outcomes. SkillOpt-style bounded edits,
independent gates, staged adoption, and rollback are adopted as proposal
mechanics. Automatic adoption and cross-user skill sharing remain gated.

The bounded [`SkillGen upstream mechanics audit`](experiments/summaries/skillgen-upstream-mechanics-audit-2026-08-01.md)
pins `yccm/SkillGen` at `3c4537bb`. Compile/import, candidate persistence,
fail-closed routing, and paired repair/regression accounting all pass a
deterministic offline check. The fixture correctly rejects a one-repair/
one-regression candidate with net gain zero. This is mechanics evidence only:
no trajectory sampling, skill induction, replay, or held-out efficacy result
was produced, so SkillGen remains outside the integration set.

The bounded [`SkillGen Codex frontier reproduction`](experiments/summaries/skillgen-codex-frontier-mini-2026-08-02.md)
then exercised the pinned pipeline through the Codex subscription-backed
frontier harness: eight deterministic tasks, one baseline run, serial calls,
and a 90-second per-call cap. All eight baseline trajectories passed, so the
upstream pipeline stopped before induction and generated no candidate. This is
useful negative evidence about the cohort (no failure signal), not evidence that
SkillGen cannot improve skills. The run also used a deterministic hashed
embedding substitute because SkillGen hard-codes OpenAI embeddings; it is not an
OpenRouter-faithful efficacy result and is not eligible for promotion.

The frontier long-horizon SkillOpt replication
([summary](experiments/summaries/alfworld-luna-skillopt-four-family-35step-2026-07-31.md))
closed the earlier horizon gap: four family-disjoint expert-solvable ALFWorld
tasks, 35 steps, and three paired arms. All arms scored 0/4 wins, and a fresh
environment replay verified all 12 action sequences. This is a valid null
checkpoint at a sufficient horizon, not a general method-ineffective claim;
the candidate remains quarantined.

The executable [`SkillGen BIRD-SQL frontier reproduction`](experiments/summaries/skillgen-codex-bird-frontier-2026-08-02.md)
finally exercised the upstream pipeline on a failure-bearing real corpus rather
than a synthetic all-pass cohort. On eight BIRD-SQL training tasks, the Codex
baseline passed 2/8 exact SQLite execution checks and SkillGen generated a
candidate. On eight held-out tasks, baseline accuracy was 0.500 and the skill
arm was 0.375: zero repairs, one regression, net gain -1, and the independent
release gate rejected the candidate. This is direct negative efficacy evidence
for this cohort; it does not prove SkillGen ineffective generally, but the
candidate is not eligible for Frankengate integration.

The independent [`RHO frontier LOCOMO reproduction`](experiments/results/rho-frontier-locomo-bounded-2026-08-02.json)
ran the pinned upstream RHO diagnosis strategy through the Codex subscription
on its own LOCOMO benchmark. One candidate was accepted by RHO's self-preference
gate (mean preference score 1.0). A matched no-harness control on the same two
held-out questions scored 0.703 mean versus 0.511 for the accepted candidate,
for a -0.192 delta and one regression. This is a deliberately small, bounded
negative slice—not a universal RHO rejection—but it demonstrates why RHO's
self-preference acceptance cannot be used as Frankengate utility evidence or a
promotion authority.

The separate [`ReasoningBank LOCOMO bounded attempt`](experiments/summaries/reasoningbank-locomo-bounded-2026-08-02.md)
reached local embedding setup but stopped before memory extraction because the
upstream documented Azure Foundry provider invokes `az`, which is unavailable
on this machine. It is recorded as a typed provider-unavailable result—not as
evidence for or against ReasoningBank memory quality.

The follow-up [`ReasoningBank Codex frontier reproduction`](experiments/summaries/reasoningbank-codex-frontier-bounded-2026-08-02.md)
kept the upstream runner unchanged and substituted only the unavailable memory
client with Codex subscription calls. Two train memories were created and the
frozen held-out score was 0.593 versus 0.703 for the matched no-harness control
(delta -0.110, one regression). This bounded negative slice keeps ReasoningBank
out of the integration set; it is not a universal method rejection.

The [`integration promotion audit`](experiments/results/integration-promotion-audit-2026-08-02.json)
now makes the downstream boundary explicit across eighteen tested mechanisms and
named concepts:
zero are eligible for automatic Frankengate integration. Skill/memory methods
are quarantined on negative or unproven utility; retrieval and PostgreSQL are
shadow-only; MLOps is mechanics-only; and provider/artifact failures remain
typed unavailable or blocked. A passing protocol or backend benchmark is not
an integration authorization.
The concise decision record is in
[`integration-promotion-audit-2026-08-02.md`](experiments/summaries/integration-promotion-audit-2026-08-02.md).

The [`independent completion audit`](experiments/results/independent-completion-audit-2026-08-02.json)
keeps the parent gate explicitly incomplete: fair powered controls, independent
changed-agent/enterprise outcomes, and cross-method power/cost/null calibration
remain open. This prevents the receipt inventory itself from being mistaken for
completion.

The [`powered RHO candidate replay`](experiments/summaries/rho-candidate-harness-powered-2026-08-02.md)
closed the fairness gap in the earlier slice. The upstream candidate was
rejected by its own self-preference gate, then independently replayed against
the exact initial-harness control on eight held-out LOCOMO tasks: `0.388` versus
`0.643` (paired delta `-0.255`, five regressions, one win, two ties). The
bootstrap interval crosses zero because the cohort is still small, so this is
bounded negative evidence and a quarantine decision—not a universal RHO claim.

The [`GEPA v0.1.4 native-tool protocol arm`](experiments/summaries/gepa-native-tool-protocol-2026-08-02.md)
now runs the actual pinned optimizer against a separate three-episode train and
three-episode holdout split using the local Llama model. GEPA made 11 metric
calls, proposed two mutations, rejected both, and retained the empty seed at
2/3 holdout matches. This validates the adapter, reflection, acceptance, and
holdout plumbing; it produces no protocol lift and no enterprise skill claim.

The [`natural trace memory factorial`](experiments/summaries/natural-trace-memory-factorial-2026-08-02-r2.md)
was rerun over 217 public histories and 30,496 source records. Its 16-arm
factorial had 23 eligible later reads; every runnable singleton and the
composed arm recovered 16/23 exact states. This validates cutoff-safe evidence
availability, not memory utility: the mechanisms were observationally
indistinguishable on current-state reads, and Dream/procedure release arms had
no independently released natural artifacts to evaluate.

The [`MATM outcome-conditioned procedure retrieval study`](experiments/summaries/matm-trace-skill-retrieval-2026-08-02.md)
adds an offline outcome-labeled transfer arm: 2,130 ALFWorld trajectories
across 34 leave-one-model-out folds. Successful-trace recommendations improved
top-10% success precision by 0.067 over all-trace neighbors, but the mean AUC
contrast was -0.056 and both bootstrap intervals crossed zero. This is useful
recommendation signal, not evidence that a changed agent performs better.

The [`larger family-disjoint ALFWorld replay`](experiments/summaries/alfworld-family-disjoint-powered-r9-2026-08-02.md)
closed the next replication slice on eight previously unused task paths. Llama
3.2 and Qwen 3 4B used the same Ollama-native harness and the same two paths
from each of four task families, with an expert plan confirming every path fit
the 35-step horizon. Both models produced `0/8` wins for no-skill and the
trace-derived procedure. The candidate emitted 66 invalid actions for Llama
versus 0 baseline, and 140 for Qwen versus 280 baseline. This is model-dependent
protocol movement without task-success lift; the aggregate projection verifier
passed, but promotion remains closed. The interrupted duplicate Qwen run is
recorded as a typed service `unexpected EOF` null rather than scored.

The [`second-harness replay`](experiments/summaries/alfworld-family-disjoint-powered-r11-openai-llama-2026-08-02.md)
then sent those exact eight paths through Ollama's OpenAI-compatible endpoint.
Llama again produced `0/8` wins in both arms, with 66 invalid actions for the
trace-derived candidate versus 0 for no-skill. This makes the negative result
harness-consistent on the tested task set, while independent semantic/security
recomputation and a larger powered cohort remain open.

The [`replayable outcome verification`](experiments/summaries/alfworld-family-disjoint-powered-r12-replayable-2026-08-02.md)
then retained only environment action sequences and independently replayed all
32 episodes in fresh ALFWorld environments. Every terminal outcome and step
count matched with zero mismatches. The verifier also confirmed every replayed
action was admissible at the corresponding fresh state. This closes the
independent task-outcome recomputation gate for the cohort, but does not
establish authorization/security correctness or positive skill utility.

The [`formatting-placebo control`](experiments/results/alfworld-family-disjoint-powered-r13-controls-2026-08-02.json)
added the required output-format placebo to those same eight tasks. Llama 3.2
through both harnesses produced `0/8` for no-skill, placebo, and trace-derived
procedure; an independent verifier replayed all 48 rows with zero mismatches.
The [`Qwen control replication`](experiments/results/alfworld-family-disjoint-powered-r14-qwen-controls-2026-08-02.json)
then reproduced the three-arm result on Qwen 3 4B's native API (`0/8` for each
arm; 24/24 rows independently replayed). This closes the second-model control
replication gate, not the overall skill-release gate: SkillOpt/SkillGen/RHO
candidate arms, security/policy verification, larger power, and enterprise
outcomes remain open.

An attempted additional frontier four-family, 35-step cohort was stopped after
the sequential Codex subscription runtime became unbounded. It has a typed
interrupted receipt ([summary](experiments/summaries/alfworld-codex-four-family-35step-interrupted-2026-08-02.md));
no partial episode is counted. This is an operational gap, not a quality
result, and does not alter the completed r9/r11/r12/r13/r14 evidence.

A direct attempt to run SkillOpt's own ALFWorld optimizer is recorded as a
typed runtime null. After installing the dependency stack and applying a
disposable modern-Python TextWorld compatibility patch, SkillOpt and ALFWorld
initialized and reached baseline rollout, but the configured local model
endpoint was unavailable. No SkillOpt response, candidate skill, or scored
episode was counted. This is not a quality result; the independent Frankengate
runner remains the only scored optimizer-like intervention so far. See
[`skillopt-alfworld-local-intervention-r16-2026-08-02.json`](experiments/results/skillopt-alfworld-local-intervention-r16-2026-08-02.json)
and the earlier dependency preflight
[`skillopt-alfworld-local-runtime-attempt-r15-2026-08-02.json`](experiments/results/skillopt-alfworld-local-runtime-attempt-r15-2026-08-02.json).

The [`deterministic SkillOpt lifecycle smoke`](experiments/results/skillopt-deterministic-lifecycle-r17-2026-08-02.json)
separately exercises rollout, reflection, aggregation, update, and gate
rejection with an in-process deterministic backend. It generated and applied a
candidate, then rejected it because baseline and candidate scores were both
`0.0`. The shim intentionally ignores task content and makes no model calls;
this validates lifecycle mechanics only, not skill quality.

The [`real Codex-backed SkillOpt run`](experiments/results/skillopt-alfworld-codex-r18-2026-08-02.json)
then generated a candidate with `gpt-5.6-luna` through the Codex subscription
harness. SkillOpt rejected it at its own selection gate (`0.0` baseline and
candidate). A bounded [`Codex transfer pilot`](experiments/summaries/alfworld-codex-skillopt-r19-2026-08-02.md)
compared the candidate with no-skill and a formatting placebo on two held-out
tasks: all three arms were `0/2`, and a fresh verifier checked all six action
sequences with zero mismatches. This is real optimizer evidence, but not a
positive utility claim or a powered release result.

The follow-up [`r20 horizon pilot`](experiments/summaries/alfworld-codex-skillopt-r20-2026-08-02.md)
ran the same candidate at eight steps on one held-out task. No-skill, placebo,
and candidate were each `0/1`; all three sequences replayed cleanly. The
longer pilot removes the three-step truncation ambiguity, but remains
underpowered and does not authorize promotion.

The [`r21 sufficient-horizon pilot`](experiments/summaries/alfworld-codex-skillopt-r21-2026-08-02.md)
repeated the comparison on a task independently solved by the hand-coded
expert in six steps. At eight steps, all three arms were `0/1`; replay passed
for all rows, but the receipt later proved to reference an empty candidate;
it is retained as protocol/replay evidence only, not negative skill evidence.

The follow-up [`r22 corrected real-candidate pilot`](experiments/results/alfworld-codex-skillopt-r22-real-candidate-2026-08-02.json)
closed a provenance defect: the r20/r21 receipts referenced an empty candidate
file, so those rows are not skill-quality evidence. R22 used the actual
213-byte SkillOpt candidate, on the same sufficient-horizon task, and again
obtained `0/1` for no-skill, formatting placebo, and candidate; the fresh
environment verifier passed all three rows. This remains a one-task,
underpowered negative result, not an impossibility claim or release gate.
The [`candidate provenance audit`](experiments/results/skillopt-candidate-provenance-audit-2026-08-02.json)
records the distinction by hash and never emits candidate text.

The subsequent [`r23 two-task replication`](experiments/results/alfworld-codex-skillopt-r23-real-candidate-2026-08-02.json)
used that same real candidate on two independently expert-solvable tasks
(expert horizons six and seven). No-skill, placebo, and candidate were each
`0/2`; all six rows used eight admissible actions and the fresh verifier
matched every row. This increases power modestly while leaving the
pre-registered larger family-disjoint and enterprise-outcome gates open.

The local-only [`Qwen3 4B model-dream attempt`](experiments/results/natural-model-dream-procedure-2026-08-02.json)
generated proposals from three content-free structural summaries. None passed
the controlled JSON/evidence-grounding rubric; the independent receipt verifier
passed, and no semantic or utility claim was made. External-model generation
over trace-derived data was intentionally not used.

The same local protocol with Llama 3.2 produced three parseable proposals and
one structural-quality pass out of three. The difference is model-format
sensitivity, not semantic procedure utility: no proposal was executed against
a changed system or scored against an independent task outcome.

The explicitly authorized frontier [`Luna natural-trace procedure arm`](experiments/results/natural-model-dream-procedure-luna-2026-08-02.json)
also produced three parseable, evidence-grounded proposals and one
structural-quality pass out of three. Its independent verifier passed all three
receipts. Luna therefore matched Llama on this small structural gate, while
the run still establishes neither semantic procedure quality nor causal utility;
the model saw only content-free summaries and no proposal was executed against
an independent task outcome.

The [`frontier Luna SkillOpt family replication`](experiments/summaries/alfworld-luna-skillopt-family4-2026-08-02.md)
then evaluated the published SkillOpt ALFWorld checkpoint, no-skill, and a
formatting placebo on four previously unused ALFWorld task families. All three
arms were `0/4` wins at the common 12-step horizon, with zero invalid actions;
the fresh verifier replayed all 12 rows successfully. This adds real frontier
model and family coverage, but the horizon truncated every arm and therefore
does not establish general semantic skill utility or authorize promotion.

The [`fair-horizon Luna follow-up`](experiments/summaries/alfworld-luna-skillopt-long-horizon-2026-08-02.md)
extended one of those tasks to 35 steps. No-skill, placebo, and the published
SkillOpt checkpoint all remained `0/1`; all three action sequences were
admissible and independently replayed with zero mismatches. This removes the
short-horizon explanation for that task while remaining a one-task model and
harness slice, not a general skill-benefit or enterprise-outcome result.

The [`NatureBench natural-trace skill-transfer preflight`](experiments/summaries/naturebench-skill-transfer-preflight-2026-07-30.md)
adds a bounded, family-disjoint outcome matrix across five public
harness/model arms. Ten task families were observed for each arm, with
historical success rates ranging from 0.10 (Claude Code/GLM 5.1) to 1.00
(Gemini CLI/Gemini 3.5 Flash). This confirms that natural tool-rich traces and
cross-model/harness variation are available for the decisive experiment; it
does **not** confirm a skill effect because no candidate was injected and no
no-skill/placebo control was replayed. The next bead is the intervention matrix
with paired repairs/regressions and independent verification.

The [`natural-trace candidate audit`](experiments/summaries/naturebench-skill-candidate-audit-2026-07-30.md)
then extracted a six-step procedure from a successful Opus trace and checked it
against DeepSeek, GLM, Codex, and Gemini same-task outcomes. Three of four
available transcripts satisfied every predicate, including both timeout runs;
Codex succeeded while missing a Claude-specific predicate, and Gemini had no
transcript. This is a useful negative transfer diagnostic, not evidence of
optimization. The local synthetic intervention is a separate protocol-only
null; domain-valid candidate replay remains open.

The [`local natural-trace skill protocol intervention`](experiments/summaries/natural-trace-skill-protocol-intervention-2026-07-30.md)
is the first real model arm: Ollama `llama3.2:latest`, six paired synthetic
episodes, no-skill versus formatting placebo versus trace-mined terminal
discipline. All three arms matched 3/6 and had 3/6 text-without-terminal
failures. This confirms the real tool-loop path, but is not SQL quality or
enterprise skill benefit.

The [`Ollama Llama 3.2 native-tool control`](experiments/summaries/native-tool-protocol-ollama-llama32-2026-07-30.md)
adds an independent local model control: 18 episodes across three protocol
variants, each at 3/6 terminal matches. The follow-up
[`two-model transfer matrix`](experiments/summaries/model-harness-transfer-native-tool-2026-07-31.md)
completed the same fixture on Qwen3 4B: no-skill was 6/6, formatting placebo
0/6, and trace-mined discipline 3/6, with 40–47 s mean latency versus Llama's
1.1–1.3 s. The candidate is therefore model-sensitive and harmful on this
Qwen protocol slice; this rejects automatic promotion but is not a semantic or
enterprise-quality result. A true cross-harness held-out replay remains open.

The [`cross-harness Llama replay`](experiments/summaries/model-harness-transfer-llama-openai-vs-ollama-2026-07-31.md)
then ran the same fixture through the OpenAI-compatible and Ollama-native
adapters. All three arms matched exactly (3/6 each) with similar latency,
indicating no adapter-specific effect on this protocol slice. This validates
the harness normalization only; held-out domain quality and skill transfer
remain unproven.

The [`Defog trace-mined skill pilot`](experiments/summaries/defog-trace-mined-skill-pilot-2026-07-30.md)
is the first domain-valid local-model intervention: four visible-selection
PostgreSQL tasks, the governed no-BYPASSRLS role, and the same three paired
arms. All 12 runs had valid authorization and zero unauthorized observations,
but none reached a terminal submission or semantic success. The trace-mined
arm produced one successful SQL execution versus zero in either control while
making more attempts, so this is a runtime diagnostic—not confirmation that
traces optimize skills. The decisive family-disjoint held-out replay with an
independent verifier and a repaired terminal protocol remains open.

The [`broker family-transfer pilot`](experiments/summaries/defog-family-transfer-broker-2026-07-31.md)
ran four held-out broker tasks through both Llama harnesses under the same
governed role. All 24 runs were authorized and had zero unauthorized
observations, but every arm failed terminal submission; no semantic estimate
is valid. The Qwen attempt timed out before its first arm. This is evidence that
the current SQL protocol must be repaired before any trace-derived skill
quality claim can be made on held-out families.

The [`terminal-fallback pilot`](experiments/summaries/defog-terminal-fallback-pilot-2026-07-31.md)
adds an arm-independent controller that submits the latest successful
authorized candidate or abstains. It makes evaluation reachable, but produced
zero semantic wins: the held-out broker fold had no successful SQL, and the
car-dealership trace-mined arm had one successful but incorrect query. This
separates terminal formatting from SQL quality without turning the fallback
into a skill claim.

The [`Qwen native governed SQL probe`](experiments/summaries/defog-qwen-native-probe-2026-07-31.md)
ran one car-dealership task through the native Ollama adapter. All arms were
authorized, but Qwen emitted zero SQL tool calls, so the controller abstained
and no semantic score was possible. This is a typed runtime null, not a
quality result.

The consolidated [`skill-optimization evidence checkpoint`](experiments/summaries/skill-optimization-evidence-2026-08-01.md)
is the current decision record: no trace-derived skill has yet produced a
held-out semantic lift. We have tested two live models (Llama 3.2 and Qwen 3
4B), two tool-loop harnesses, synthetic intervention controls, and governed
SQL probes. The pinned Qwen3.5-9B-OptiQ manifest is not a completed run—the
7.1 GB snapshot is absent locally and no Qwen3.5 listener is running—so it is
explicitly excluded from the evidence base.

The [`paired skill-optimization meta-analysis`](experiments/summaries/skill-optimization-meta-analysis-2026-08-02.md)
recomputes the intervention contrasts without reading raw traces. It keeps
protocol compliance separate from semantic correctness and keeps the
expert-written schema seed separate from trace-mined candidates. The Llama
trace-mined protocol arm is tied with its baseline (0.0 risk difference); the
Qwen3 4B trace-mined arm is lower by 0.5 (bootstrap 95% interval −0.833 to
−0.167; exact McNemar p=0.25); and the only reachable semantic comparison,
the four-task expert seed, is tied 2/4 versus 2/4. This strengthens the
negative conclusion: current evidence supports candidate generation and
diagnosis, not a causal skill lift or automatic release. The runner is
`skill_optimization_meta_analysis.py`.

An additional six-task car-dealership replay
(`defog-trace-mined-skill-heldout-car-2026-08-02.md`) ran all three arms.
Authority validation succeeded for all 18 runs and unauthorized observations
were zero, but every arm exhausted the SQL protocol: semantic correctness and
successful SQL were 0/6, with six terminal fallbacks per arm. This is a typed
model/protocol null, not evidence for or against a skill benefit; protocol
remediation and independent outcome/security verification remain required.

The accompanying [`independent receipt verification`](experiments/summaries/defog-trace-mined-skill-heldout-car-independent-verification-2026-08-02.md)
rechecked all 18 external raw audits: hashes, attempt chains, authority/epoch
bindings, policy invariants, terminal scheduling, and unauthorized-observation
flags all passed. It explicitly leaves semantic recomputation unclaimed because
the disposable PostgreSQL executor is no longer running.

After restoring the local executor, a second protocol repair injected the
authorized schema catalog into every arm's system context and retained the
larger interaction budget. The [`schema-injected replay`](experiments/summaries/defog-trace-mined-skill-heldout-car-schema-injected-2026-08-02.md)
reached semantic evaluation: no-skill, formatting placebo, and trace-mined
arms each submitted 2/6 candidates, with 1/6 semantic-correct, 1/6
semantic-incorrect, and 4/6 abstentions. A fresh governed executor independently
recomputed every candidate/gold comparison with zero mismatches, and the raw
security verifier passed. The paired trace-mined contrast is 1/6 versus 1/6
(risk difference 0.0), so the protocol confound is reduced but no causal skill
lift is demonstrated.

The two intermediate repairs are also retained: the larger-budget replay
remained policy-denied because Llama skipped schema discovery, and the
schema-first instruction alone produced the same zero-schema-call null
([budget replay](experiments/summaries/defog-trace-mined-skill-heldout-car-repaired-2026-08-02.md),
[schema-first replay](experiments/summaries/defog-trace-mined-skill-heldout-car-schema-first-2026-08-02.md)).
The paired meta-analysis includes both nulls and the schema-injected semantic
tie; it now covers 18 endpoint/study strata and still authorizes no promotion.

The subsequent [`family-disjoint broker replay`](experiments/summaries/defog-trace-mined-skill-family-broker-schema-injected-2026-08-02.md)
used six previously unused broker tasks under the same schema-injected
protocol. No-skill and trace-mined arms submitted 0/6 candidates; the placebo
submitted one correct candidate (1/6). Independent semantic and raw-security
verifiers passed. This is transfer evidence against automatic trace-mined
promotion, but remains small and abstention-heavy.

The first authenticated frontier replay is now recorded in the
[`Codex/Luna broker family-transfer study`](experiments/summaries/defog-codex-frontier-broker-transfer-2026-08-02.md).
Across four family-disjoint broker tasks, the car-derived trace candidate was
3/4 semantic-correct, exactly tying the formatting placebo; no-skill was 0/4.
An independent governed-PostgreSQL verifier matched all 12 outcomes with zero
errors. This confirms the frontier replay path and a protocol/scaffolding
effect, not artifact-specific skill improvement or promotion eligibility.

The follow-up [`frontier transfer multiseed screen`](experiments/summaries/defog-codex-frontier-transfer-multiseed-2026-08-02.md)
made the seed explicit and independently verified three matched seeds (36
arm episodes). The shared-cluster aggregate was no-skill 6/12, formatting
placebo 10/12, and trace-mined 5/12; trace-mined vs placebo had risk
difference −0.417 and exact McNemar p=.125, while trace-mined vs no-skill was
−.083 (p=1.0). A separate two-seed run placed each seed in its own disposable
PostgreSQL container, governed role, Codex proxy, and audit roots; it yielded
no-skill 5/8, placebo 3/8, and trace-mined 4/8 (both paired p=1.0). The
direction changed under isolation, but neither run supports promotion. This
is stochastic screening evidence, not a universal claim that trace mining is
harmful.

The decisive [`length-matched neutral control`](experiments/summaries/defog-codex-frontier-neutral-control-2026-08-02.md)
then replayed the same four broker tasks in a fresh isolated database with a
fourth arm whose generic text was exactly the trace artifact's 308-character
length. The neutral arm scored 4/4 semantic-correct, formatting placebo 3/4,
no-skill 1/4, and trace-mined 1/4 (3/4 submissions). Trace-mined versus the
neutral control was −0.75 risk difference (exact McNemar p=.25), and it tied
no-skill (p=1.0). Every trajectory passed independent semantic/security
verification. This is not a universal claim about neutral text, but it is
direct evidence that this candidate does not earn promotion over a
length-matched context control.

The [`sealed paraphrase transfer`](experiments/summaries/defog-codex-frontier-paraphrase-transfer-2026-08-02.md)
run then changed only the four user questions while preserving task IDs, gold
SQL, database state, and authority. On one fresh seed, trace-mined scored 4/4
versus 3/4 for both no-skill and the length-matched neutral (each exact
McNemar p=1.0 because only one discordant block existed). This is suggestive
transfer compatibility, not a causal result: the unmutated run scored the
same trace artifact 1/4 while its neutral control scored 4/4. Three-seed,
second-harness replication is required before interpreting the direction. The
completed three-seed aggregate is trace-mined 8/12, no-skill 6/12, and
length-matched neutral 7/12; trace-versus-neutral risk difference is +.083
(exact McNemar p=1.0), so the direction is still not promotion evidence.

The [`cross-harness screen`](experiments/summaries/defog-codex-frontier-cross-harness-2026-08-02.md)
ran the same paraphrase matrix through the HTTP proxy and a direct native
Codex CLI harness. The proxy's three-seed aggregate was trace 8/12 versus
neutral 7/12; the native harness was trace 2/4 versus neutral 3/4 and tied
no-skill at 2/4. This direction reversal closes the “same harness only” gap:
the artifact is not robust across implementations and remains unpromoted.

An additional audit corrected a separate Trace2Skill-style compiler smoke: the
430000 compiler source and replay shared the same broker task IDs, so its
apparent 4/4 result is contaminated development evidence. The authoritative
disjoint car-to-broker compiler replay (seed 440000) scored 3/4, tying no-skill
and length-matched neutral; the formatting placebo scored 4/4. All 16 episodes
passed independent semantic/security/authority verification. Compilation and
governed replay remain supported mechanics, but no cross-database skill lift
has been shown. See
[`Trace2Skill contamination correction`](experiments/summaries/trace2skill-compiled-native-replay-2026-08-02.md).

The [`Trace Commons full-cohort analysis`](experiments/summaries/trace-commons-full-content-minimized-analysis-2026-08-02.md)
then attested all 28 public native Claude Code histories byte-for-byte against
the pinned manifest (17,991 records and 4,264 tool calls) before analysis. The
content-minimized S1→S2→S4→S6 ladder produced 263 structural episode
candidates and 269 eval-review records, while automatic memory/skill writes,
skill-gap claims, and cross-user recommendations remained zero. This expands
the public evidence base, but still contains no outcome labels and therefore
cannot establish a skill or productivity effect.

The [`combined evidence matrix`](experiments/summaries/combined-evidence-matrix-2026-08-02.md)
now consumes those attestation receipts alongside the ATIF/OTel, retrieval,
memory, and skill-release arms. It records the CMU raw-shard requirement as
approval-gated—not waived—and keeps all enterprise causal and Aurora-scale
claims closed.

The matrix now also consumes the [`ATIF/RL round-trip receipt`](experiments/results/atif-rl-roundtrip-2026-07-30.json)
instead of treating the small canonical projection fixture as the whole schema
story. Across 2,130 MATM ALFWorld trajectories, ATIF retained 0.067 of measured
capability facts and OpenInference/OTel retained 0.327; neither retained RL
reset state, rewards, or termination facts. The source omits memory snapshots
and authorization fields, so schema fidelity is not evidence of memory utility
or skill learning.

The full-corpus analysis was subsequently rerun from the local pinned cache;
the [`reproducibility receipt`](experiments/results/trace-commons-analysis-reproducibility-2026-08-02.json)
matched 19 aggregate metrics, including the 263 recovery episodes, 269
eval-review records, and zero automatic memory/skill writes. This confirms the
analysis pipeline is reproducible, not that the structural signals predict
correctness or improve skills.

The same matrix now consumes the [`paired skill meta-analysis`](experiments/summaries/skill-optimization-meta-analysis-2026-08-02.md)
and both model/harness transfer receipts: 22 endpoint strata, Llama 3.2 and
Qwen 3 4B, and OpenAI-compatible plus Ollama-native loops. The aggregate keeps
protocol compliance separate from semantic correctness and records causal
benefit and automatic promotion as false.

A fresh full 18-episode Qwen3 4B native-Ollama replay completed without a
single native tool call in any arm (no-skill, placebo, or trace-mined). It is
recorded as a typed model/harness null and added to the meta-analysis, which
now contains 23 endpoint strata; it is not treated as a semantic skill result.

The candidate was then mined from the completed car raw audits rather than
hand-supplied: the miner sealed an aggregate source digest and procedure hash,
and the resulting artifact was injected into a fresh broker fold. The true
train-on-car/test-on-broker trace-mined arm again scored 0/6, while no-skill
scored 0/6 and the placebo 1/6; independent semantic and security verification
passed. See [`trace-mined candidate transfer`](experiments/summaries/trace-mined-skill-candidate-car-to-broker-2026-08-02.md).

A Qwen3 4B replication on the same broker fold was intentionally not scored:
the loopback model produced 14/18 raw episode files before one request exceeded
the practical wall-time budget, leaving one no-skill episode without a
task-end receipt. The incomplete run is recorded separately and excluded from
the meta-analysis; it provides model/harness latency evidence, not a quality or
skill claim.

The [`CMU access audit`](experiments/summaries/cmu-access-and-adapter-readiness-2026-07-30.md)
records the exact boundary for the requested CMU corpus: the pinned Hub
revision is discoverable, but authenticated download is still approval-gated,
the license is `NOASSERTION`, no raw files are local, and no trajectory-level
metric is claimed. Public cohorts therefore remain the active empirical input;
CMU admission is a tracked prerequisite rather than silently substituted data.

The embedding gate is equally explicit. E2 provides general dense, structured,
and lexical baselines, but its silver labels are not human task-similarity gold
and there is no reviewed hard-negative or user/project/time-held-out adaptation
split. Enterprise fine-tuning therefore remains a gated null: first create
governed similar-work labels, then require a preregistered lift without exact-ID,
subgroup, deletion, latency, memorization, or rollback regressions.

Bulk raw corpora stay outside Git so revisions remain small and reproducible.
Dataset manifests pin exact source revisions and adapters read explicit local
paths. Frankengate's governed database may retain full internal trace content
for authorized internal analysis; sending that content to an external model or
API remains a separate egress decision.

## Reproduce the committed artifact

The dependency lock covers the tested Python 3.9–3.13 range. PyArrow 21 does
not publish a Python 3.14 wheel, so the upper bound is deliberate:

```bash
cd research/trace-intelligence
uv sync --python 3.9 --frozen
uv run make verify
```

`make verify` runs every unit/conformance test, validates dataset manifests and
canonical governed fixtures, parses every aggregate result, checks that no raw corpus
file is committed, and compiles the Python harness. It performs no network request,
model call, database mutation, or dataset download.

The latest pinned audit (`uv run --frozen make verify`) ran 497 research tests
with 13 explicit environment skips and no failures, plus 61/61 NL2SQL
capability tests. It validated 83 aggregate results, 44 dataset manifests, 12
governed fixtures, zero committed raw corpus files, and Python compilation.
The Seatbelt skips are host-runtime gates; Linux/container replay remains the
required authority for sandbox execution. The separate no-install host audit
may report additional optional-dependency skips, but is not the authoritative
full-suite result.

The governed Wisp target is intentionally separate because it mutates a disposable
research schema and requires explicit private inputs:

```bash
make governed-wisp \
  GOVERNED_POSTGRES_DSN='postgresql://…' \
  WISP_CORPUS_ROOT='/private/research-cache/wisp/transcripts'
```

The Hugging Face NL2SQL structural audit is also external-input-only. It verifies
pinned BIRD-SQL and CRMArena task/trace hashes and emits aggregate replay
classification without retaining prompts, SQL, tool arguments, observations,
answers, or identifiers:

```sh
python3 hf_nl2sql_trace_audit.py \
  --bird-root /private/path/bird \
  --bird-manifest configs/datasets/wmh-bird-sql-traces.json \
  --crmarena-root /private/path/crmarena \
  --crmarena-manifest configs/datasets/wmh-crmarena-traces.json \
  --output experiments/results/hf-nl2sql-trace-audit-2026-07-30.json
```

The audited WMH files contain real tool arguments and environment observations,
but not parent-linked/wall-clock OTel or full assistant messages. BIRD is
reconstructable from an external mini-dev archive; CRMArena is reconstructable
from its official SQLite dump and is non-commercial research only. See
[`experiments/summaries/hf-nl2sql-trace-audit-2026-07-30.md`](experiments/summaries/hf-nl2sql-trace-audit-2026-07-30.md).
The domain decision, prior State of AI synthesis, modular skill taxonomy, and
smallest causal sequence are recorded in
[`experiments/summaries/nl2sql-enterprise-skill-domain-assessment-2026-07-30.md`](experiments/summaries/nl2sql-enterprise-skill-domain-assessment-2026-07-30.md).

The causal SQL layer uses a separate, content-free 96-task Defog manifest and
four disposable PostgreSQL databases. The hardened runner requires a governance
subject and an exact current authorization epoch bound to database, scope,
user, team, and virtual key. It parses and allowlists a single read-only query,
authorizes sensitive columns across projections, predicates, joins, grouping,
ordering, windows, functions, and correlated subqueries, fixes the governed
search path, enforces PostgreSQL and result limits, and reports authority,
policy, execution, leakage, benchmark correctness, and strict answer shape
separately:

```sh
DEFOG_SOURCE_ROOT=/private/path/defog-sql-eval \
DEFOG_REPLAY_DSN_TEMPLATE='host=127.0.0.1 port=55432 user=... dbname=fg_defog_{database}' \
DEFOG_RAW_AUDIT_DIR=/private/path/defog-raw-audit \
uv run make defog-sql-conformance
```

The conformance run matched all 95 PostgreSQL-executable tasks: 93 under the
default policy and two only with explicit field-level entitlements. One source
task is invalid PostgreSQL and remains quarantined. All security controls passed
on all four database families. This proves the replay/verifier boundary, not
model quality or causal skill benefit. See
[`experiments/summaries/defog-governed-sql-replay-conformance-2026-07-30.md`](experiments/summaries/defog-governed-sql-replay-conformance-2026-07-30.md).

The content-free four-fold factorial contract can be regenerated without
network or benchmark content:

```sh
uv run make defog-sql-design
```

The first cache-disabled 12-episode mechanics smoke completed with 12/12 valid
authority receipts and zero unauthorized observations. Every arm solved the
same 2/4 tasks, so the expert seed showed no lift. Terminal-protocol failure was
25% for no-skill, 50% for placebo, and 25% for the expert seed, exceeding the
preregistered 10% gate. The 23-task effect screen and hidden family therefore
remain sealed until an arm-independent protocol repair passes a new P0. See
[`experiments/summaries/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md`](experiments/summaries/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md).

An independent, content-free native-tool pilot then ran six paired synthetic
fixtures across the all-tools control, remaining-budget annotations, and
terminal-only tool availability. All variants completed 6/6 expected terminal
actions, establishing that per-request terminal-only switching is compatible
with the pinned MLX/Qwen runtime. Because the controls also passed, this is not
evidence of causal improvement and does not reopen P1. Reproduction and exact
receipts are in
[`experiments/summaries/native-tool-protocol-compliance-pilot-2026-07-30.md`](experiments/summaries/native-tool-protocol-compliance-pilot-2026-07-30.md)
and
[`experiments/summaries/mlx-lm-tool-runtime-audit-2026-07-30.md`](experiments/summaries/mlx-lm-tool-runtime-audit-2026-07-30.md).

The subsequent capability audit found that the current single process keeps
source task IDs, all stage memberships, gold SQL, the candidate executor, and
evaluation code in one address space. P1 and hidden evaluation therefore also
remain blocked on executable solver/broker/resolver/evaluator isolation,
append-once attempt evidence, and separately sealed stage manifests. The exact
minimum architecture and 27 release-gate tests are specified in
[`nl2sql-capability-isolation-design-2026-07-30.md`](../../docs/roadmap/research/nl2sql-capability-isolation-design-2026-07-30.md).

The expanded capability-isolation implementation checkpoint now passes 61/61
component tests. In addition to strict DTO, broker, attempt, evaluator, and
stage-sealing contracts, it includes separate supervisor/evaluator resolver
methods, a fresh-process solver harness with inherited Unix peers, and a
fail-closed OCI profile contract. The frozen profile passed 21 real Linux/runc
enforcement and protocol gates after the runtime test exposed and corrected a
missing safe `fstatfs` syscall and an unsafe host-global `RLIMIT_NPROC`
assumption. A bounded real PostgreSQL 16 audit also
passed distinct candidate/evaluator roles and application names, write denial,
three candidate plus three evaluator-only gold executions, database snapshot
stability, and cleanup. A composition test proves that an empty model preview
can still yield the correct verdict from the full sealed result while candidate
execution remains exactly one. P1 is **not** reopened: the abstract resolver
still needs OS peer credentials, the solver needs a minimal image and
episode-specific identity/two-run isolation, database execution needs
independently signed server/broker receipts, and crash recovery, signed
evaluation/OTel receipts, and the complete 27-gate same-profile run remain.
See
[`experiments/summaries/nl2sql-capability-isolation-component-checkpoint-2026-07-30.md`](experiments/summaries/nl2sql-capability-isolation-component-checkpoint-2026-07-30.md).
The real PostgreSQL slice is recorded separately in
[`experiments/summaries/nl2sql-postgres-role-audit-2026-07-30.md`](experiments/summaries/nl2sql-postgres-role-audit-2026-07-30.md).
The actual Linux profile, discovered failures, and raw-evidence contract are in
[`experiments/summaries/nl2sql-linux-oci-conformance-runbook-2026-07-30.md`](experiments/summaries/nl2sql-linux-oci-conformance-runbook-2026-07-30.md).

Spider2 is admitted only as a later external-validity layer. The source audit
found 135 local Lite tasks across 30 database families, but only 16/24 published
gold SQL files pass the upstream self-check. Of 68 DBT tasks, 59 are strictly
self-consistent and 62 work with deterministic filename aliases; the proposed
cohort is 60. The upstream agent also executes ordinary tool actions twice.
See
[`spider2-local-replay-audit-2026.md`](../../docs/roadmap/research/spider2-local-replay-audit-2026.md).

The real OpenTelemetry E0 arm is also separate because it downloads a pinned
Collector release, binds a disposable loopback receiver, and builds the pinned
Go SDK sender:

```bash
make otel-roundtrip
```

It verifies the release archive and extracted binary, keeps the content-minimized
SDK manifest and Collector storage out of Git, runs lossless and deliberate-drop
pipelines, and writes aggregate JSON only. See
[`experiments/summaries/otel-collector-roundtrip-e0-2026-07-30.md`](experiments/summaries/otel-collector-roundtrip-e0-2026-07-30.md).

See `CITATION.cff`, `LICENSES.md`, each `configs/datasets/*.json` manifest, and each
`experiments/summaries/*.md` interpretation before reusing a result.

The expanded real-history discovery receipt is rebuilt offline from pinned,
content-free manifests:

```bash
make history-discovery
```

It records 359 Hugging Face discovery hits, the indexed and tree-enumerated
native Claude/Codex supply, the first verified near-complete public Claude
home-state tree, portable bundle/partial-home/native archive classifications,
and the observed adjacency of Codex auth files. It commits no prompt, path,
identifier, tool argument/result, secret candidate, or raw trace.

The first executable pilot answers two narrow questions:

1. Can a native SWE-agent conversation be converted into a source-neutral event
   sequence without silently dropping source events?
2. Do label-blind, deterministic friction signals enrich externally failed attempts
   within matched tasks?

It does **not** establish that a trace is diagnostically informative, identify a
decisive failure step, infer a person's skill, or justify a production feature.

## Authorized local-model longitudinal experiment

The longitudinal state-selection experiment deliberately keeps useful trace
content intact inside the governed internal boundary. Authorized users and
administrators may inspect full-fidelity source evidence within their scope.
Redaction is a disclosure control for third-party, lower-privilege, cross-scope,
or public copies—not a destructive preprocessing step for Frankengate's own
logs. Credentials are a separate class: authorization/cookie headers, bearer
and session tokens, API/virtual-key values, OAuth codes, private keys, and
secret-manager values must be stripped before durable capture or any
model/evaluator/index path.

The frozen experiment evaluates 17 cutoff-safe context-artifact units from the
Trace Commons and Fable-5 strata across five memory surfaces and five repeated
invocations. Those invocations measure deterministic repeatability, not five
statistically independent samples: the local runtime uses temperature zero and
does not promise seed support. It calls only a pinned model server bound to
loopback. Raw prompts, model responses, trace content, unit identifiers, and the
unminimized base result stay in explicit internal paths outside Git:

```sh
PYTHON=python3 \
TRACE_COMMONS_ROOT=/private/path/trace-commons \
FABLE5_PREPARED_ROOT=/private/path/fable5-content-addressed \
LONGITUDINAL_LOCAL_ENDPOINT=http://127.0.0.1:8765 \
LONGITUDINAL_RAW_AUDIT_DIR=/private/path/new-empty-audit-dir \
LONGITUDINAL_BASE_RESULT=/private/path/base-result.json \
LOCAL_TOKENIZER_PYTHON=/path/to/pinned/python \
LOCAL_MODEL_SNAPSHOT=/private/path/pinned-model-snapshot \
make longitudinal-memory-local-model

PYTHON=python3 \
LONGITUDINAL_RAW_AUDIT_DIR=/private/path/completed-audit-dir \
LONGITUDINAL_BASE_RESULT=/private/path/base-result.json \
make longitudinal-memory-local-finalize
```

The finalizer fails closed on missing, duplicate, or inconsistent attempts. Its
committed artifact contains only source-stratified rates, decision-reason and
protocol-failure counts, token totals, evidence-budget pressure, stability,
content-free input receipts, and a hash commitment to the internal audit set.
This bounded study tests state evidence selection; it does not measure employee
skill, causal memory benefit, or enterprise-wide generalization.

The completed first pilot is recorded in
[`experiments/summaries/longitudinal-memory-local-model-replication-2026-07-30.md`](experiments/summaries/longitudinal-memory-local-model-replication-2026-07-30.md).
All 425 loopback calls produced valid native-tool responses, but the four
evidence-bearing arms agreed behaviorally and had identical aggregate scores.
This is not evidence that the mechanisms are equivalent: the pilot exposed
design confounds. The nominal dream arm did not dream, arm labels were visible,
`latest_only` retained context, the bitemporal surface was incomplete, and the
runtime/source was not attested at process launch. The checked-in result is
therefore explicitly exploratory; a corrected paper-grade replication must
remove those confounds and install an always-on credential-only input gate.

## Run the matched pilot

The input is JSON Lines with the public
[`nebius/SWE-agent-trajectories`](https://huggingface.co/datasets/nebius/SWE-agent-trajectories)
schema. Raw traces stay outside Git.

```bash
python3 research/trace-intelligence/tracebench.py pilot \
  --input /tmp/frankengate-nebius-matched-pilot.jsonl \
  --output /tmp/frankengate-nebius-pilot-result.json
```

The command:

- canonicalizes every source turn;
- marks inferred tool calls/results as `reconstructed`, never `observed`;
- emits an information-loss audit;
- computes deterministic Signals-inspired friction features without reading the
  outcome;
- compares a preregistered friction score and a length heuristic at a fixed review
  budget; and
- writes a content-addressed result manifest.

Run the frozen conformance suite with:

```bash
uv run python -m unittest discover \
  -s tests \
  -p 'test_*.py'
```

The frozen environment adds `jsonschema`, `psycopg2-binary`, `pyarrow`, and
`sqlglot` for artifact validation, governed PostgreSQL experiments, admitted
Parquet manifests, and fail-closed SQL parsing. Core adapters and most tests
remain standard-library-only.

The paper-grade design, gates, and later E0–E7 experiments are specified in
[`docs/roadmap/research/trace-intelligence-public-dataset-empirical-program.md`](../../docs/roadmap/research/trace-intelligence-public-dataset-empirical-program.md).

## Governed PostgreSQL lab

The `sql/` directory adds a disposable trace schema to the existing local PostgreSQL
16 + pgvector fixture. It validates RLS-before-FTS/vector retrieval using a
`NOSUPERUSER NOBYPASSRLS` application role. `postgres_loader.py` loads the frozen
Nebius pilot through that restricted role and preserves reconstructed tool proposals
and results as typed events.

The eight-dimensional vectors in this lab encode deterministic signal features. They
exercise PostgreSQL authorization and retrieval composition only; they are not an
embedding-quality experiment.

## Real trace and versioned-memory conformance

`trace_commons_memory_conformance.py` runs over a pinned 4,555,068-byte,
two-session Trace Commons cohort. The raw JSONL stays in an external disposable
cache. The adapter verifies source hashes, native parent edges, and exact
tool-call/result joins; reconstructs only successful writes and edits; and treats a
later read that differs from the last evidenced state as an interval-censored
version gap.

The real run preserved 1,602 records and 1,266/1,266 parent edges. All eight
context-artifact calls joined to results. One memory write exactly matched a read
in the later session, two edits replayed deterministically, and a second artifact
correctly produced one version-gap receipt. These are import and provenance
results—not evidence that the memory was correct or useful.

Re-run with the two manifest-pinned files under an external root:

```sh
TRACE_COMMONS_ROOT=/private/path/trace-commons-cache \
PYTHON=python3 \
make trace-memory
```

The committed aggregate is
[`experiments/summaries/trace-commons-memory-conformance-2026-07-30.md`](experiments/summaries/trace-commons-memory-conformance-2026-07-30.md).

## Full-cohort memory composition

`trace_commons_memory_composition.py` expands the native audit to every one of
the 28 pinned Claude Code histories (57,104,737 verified bytes and 17,991
records). It reproduces the frozen broad context inventory—14 histories, 67
joined operations, 19 reads, 37 writes/edits, and 11 shell/search operations—
then compares deterministic verbatim, context-collapsing latest-only,
contextual-bitemporal, and proposal-only dream mechanics.

The natural cohort yielded only three reconstructable later-read cutoffs, one
changed post-observation case, and one exact cross-session
write-to-later-read transition. The 50 state observations represented 48 unique
contextual revisions. Verbatim and bitemporal storage retained all 48;
latest-only retained 20 and overwrote 28. Online scoring returned one exact
state and two stale states; the two version gaps became known only from the
later read results and therefore could not legitimately cause pre-read
abstention. The contextual arm passed all six same-basename/different-project
placebos, while deliberately context-collapsing latest-only failed by retrieving
foreign-project evidence in three. All 48 evidence-linked dream proposals
remained inactive, but failed-job atomicity was not run and is not claimed.
All preregistered quality-comparison power gates failed. No model-quality,
human-review, causal-usefulness, or enterprise-transfer claim is allowed from
this run.

The source receipt is
[`configs/datasets/trace-commons-memory-full-cohort.json`](configs/datasets/trace-commons-memory-full-cohort.json),
and the implementation-sensitive protocol is
[`configs/experiments/trace-commons-memory-composition-2026.json`](configs/experiments/trace-commons-memory-composition-2026.json).
Raw histories remain outside Git.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 trace_commons_memory_composition.py \
  --manifest configs/datasets/trace-commons-memory-full-cohort.json \
  --experiment-config configs/experiments/trace-commons-memory-composition-2026.json \
  --source-root /private/path/trace-commons-cache \
  --output experiments/results/trace-commons-memory-composition-2026-07-30.json \
  --summary experiments/summaries/trace-commons-memory-composition-2026-07-30.md
```

The aggregate result is
[`experiments/summaries/trace-commons-memory-composition-2026-07-30.md`](experiments/summaries/trace-commons-memory-composition-2026-07-30.md).

The separate PostgreSQL H5 slice binds that content-free aggregate to a
context-preserving procedure and rejects basename-only latest memory. All
26 forced-RLS, role-separation, hidden-test, release, exposure, influence,
withdrawal, and rollback assertions passed on PostgreSQL 16.12 with pgvector
0.8.1; the transaction and residue check left zero study rows. This is a
bounded database-mechanics result, not an Aurora operations or memory-benefit
result. See
[`experiments/summaries/trace-commons-memory-h5-postgres-2026-07-30.md`](experiments/summaries/trace-commons-memory-h5-postgres-2026-07-30.md).

The subsequent source-stratified external replication adds the pinned
[Glint Fable-5](https://huggingface.co/datasets/Glint-Research/Fable-5-traces)
top-level native Claude stratum without modifying the original
preregistration. A path-minimizing preparer excludes 36 nested subagent files
and materializes 79 verified histories under content digests. Combined with
Trace Commons, the exploratory mechanics counts are 17 reconstructable reads,
ten changed cases, and five exact cross-session transitions. The original
`10 / 5 / 2` count gate passes, but a confirmatory diversity gate of three
source families and five exact-transition project contexts fails at two and
three. Model or human work may proceed only as an exploratory replication; no
population or enterprise claim is unlocked.

The Glint archive is a 115/115 byte-exact mirror of the pinned cfahlgren1
archive and counts once. Its card describes unsanitized synthetic telemetry and
does not establish independent contributors. An aggregate-only scan of 338,210
strings found 65 redaction markers and 11 bearer-token-shaped candidates
without emitting candidate values. Third-party model/evaluator/training egress
is blocked until a credential-only hard deny and destination-approved PII
transform rescan the final evidence pack and pass fail closed. Authorized
same-scope local analysis may retain PII, but never reusable credentials.

Rebuild from external caches:

```sh
TRACE_COMMONS_ROOT=/private/path/trace-commons-cache \
FABLE5_SOURCE_ROOT=/private/path/fable5/claude/projects \
FABLE5_PREPARED_ROOT=/private/path/fable5-content-addressed \
PYTHON=python3 \
make longitudinal-memory-expansion
```

The deterministic result and prospective pre-model protocol are
[`experiments/summaries/longitudinal-memory-cohort-expansion-2026-07-30.md`](experiments/summaries/longitudinal-memory-cohort-expansion-2026-07-30.md)
and
[`configs/experiments/longitudinal-memory-model-human-replication-2026.json`](configs/experiments/longitudinal-memory-model-human-replication-2026.json).
The sensitive scan is interpreted in
[`experiments/summaries/fable5-sensitive-token-scan-2026-07-30.md`](experiments/summaries/fable5-sensitive-token-scan-2026-07-30.md).

The H5 concurrency extension then uses independent PostgreSQL sessions to test
failed-job atomicity, promotion and withdrawal serialization, exposure races,
epoch and membership revocation, hard deletion, and provenance retention.
The mechanics pass, but the run proves four hard edges: exposure metadata can
commit after withdrawal unless both operations share a lock; REPEATABLE READ
retains old authorization/deletion snapshots; governance mutation needs a
narrow persistent non-owner boundary; and provenance FKs require an explicit
tombstone/redaction policy. The new atomic lifecycle procedures then passed a
rollback-only assertion and a two-session race: exposure creation and
withdrawal serialize on the release row, withdrawal ends the exposure and
appends one event, and zero active exposure metadata remains. REPEATABLE READ
and Aurora/RDS Proxy limitations remain. It is a local PostgreSQL 16.12 result,
not Aurora.

```sh
PYTHON=python3 make memory-h5-concurrency
```

The corrected lifecycle contract is reproduced with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  tests/run_skill_release_atomic_lifecycle_race.py
```

Its procedure contract is [`sql/009_skill_release_atomic_lifecycle.sql`](sql/009_skill_release_atomic_lifecycle.sql),
with rollback-only assertions in [`sql/010_skill_release_atomic_lifecycle_assertions.sql`](sql/010_skill_release_atomic_lifecycle_assertions.sql).

See
[`experiments/summaries/trace-commons-memory-h5-concurrency-postgres-2026-07-30.md`](experiments/summaries/trace-commons-memory-h5-concurrency-postgres-2026-07-30.md).

### Disposable replication and promotion lab

The Colima runtime probe initially reported a broken macOS Docker shim. A
capability check now finds the daemon through `colima ssh`, and the disposable
[`aurora_like_replication_lab.py`](aurora_like_replication_lab.py) exercises a
fresh PostgreSQL 16 primary/standby pair with tenant RLS, physical replication,
marker propagation, promotion, and a post-promotion write. The latest receipt
measured marker visibility in 293.694 ms and promotion in 309.056 ms, with RLS
isolation verified. This is evidence for local PostgreSQL mechanics only; it is
not evidence for managed Aurora failover, PITR, RDS Proxy, extension
compatibility, concurrency, or production SLOs. PITR remains explicitly
unexecuted.

The machine-readable result is
[`experiments/results/aurora-like-replication-lab-2026-08-02.json`](experiments/results/aurora-like-replication-lab-2026-08-02.json).

The separate [`postgres_pitr_lab.py`](postgres_pitr_lab.py) receipt also
completed a local WAL recovery-target check: seven archive files were seen and
a marker written after the named restore point was absent after recovery. This
closes local PostgreSQL PITR mechanics only; managed Aurora backup retention,
cross-region restore, and RDS operational guarantees remain unmeasured. See
[`experiments/results/postgres-pitr-lab-2026-08-02.json`](experiments/results/postgres-pitr-lab-2026-08-02.json).

## E2 same-work retrieval factorial

`e2_authorized_retrieval_factorial.py` evaluates a frozen trace-to-trace
same-work pilot over the existing raw CodeTraceBench blocked-test allowlist. It
compares a fixed `2 x 2 x 2` structured/lexical/dense design while retaining an
exact-identifier channel in every arm. The optional dense lane is pinned to
`Qwen/Qwen3-Embedding-0.6B` revision
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`. It encodes documents without a
prompt and queries separately with the frozen instruction `Given an agent
trajectory, retrieve other trajectories attempting the same task`; the result
records the instruction, template, device, and snapshot hashes.

The task identity is a silver positive and hard negatives are metadata-derived.
Neither is a substitute for blinded human task-family adjudication. The quality
factorial runs offline; it references the existing forced-RLS PostgreSQL result as
an independent runtime proof and explicitly does not claim a joint quality/RLS,
deletion, selective-scope latency, or Aurora result. Raw text and vectors remain
outside Git.

Run with external, hash-verified inputs:

```sh
CODETRACEBENCH_FULL=/private/path/bench_manifest.full.parquet \
CODETRACEBENCH_ARCHIVE_ROOT=/private/path/codetracebench-raw \
QWEN3_EMBEDDING_SNAPSHOT=/private/path/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
QWEN3_EMBEDDING_DEVICE=auto \
PYTHON=python3 \
make e2-retrieval
```

`e2_postgres_joint_retrieval.py` then loads those same documents and pinned
1,024-dimensional vectors into the forced-RLS research table in one rollback-only
transaction. All five denied authority scenarios return zero candidates for
base, FTS, trigram, and vector queries. Withdrawal and deletion are filtered
before ranking and the independent post-rollback count is zero.

On this small local cohort, exact pgvector reached `0.6667` Recall@20 at
`3.017 ms` sequential p50. Three-way FTS/trigram/vector RRF reached only
`0.6717` Recall@20, reduced nDCG and MRR, and cost `256.843 ms` p50. The tested
hybrid is therefore rejected; the experiment supports exact pgvector as the
smallest native lane while structured plus dense remains the best offline
quality arm. This is not an Aurora, concurrency, or scale result.

Re-run it only against a disposable schema with SQL migrations 001–004 applied:

```sh
GOVERNED_POSTGRES_DSN=postgresql://... \
CODETRACEBENCH_FULL=/private/path/bench_manifest.full.parquet \
CODETRACEBENCH_ARCHIVE_ROOT=/private/path/codetracebench-raw \
QWEN3_EMBEDDING_SNAPSHOT=/private/path/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
PYTHON=python3 \
make e2-postgres-joint
```

## Latest frontier intervention and retrieval checkpoints

The pinned upstream [`RHO hermetic audit`](experiments/summaries/rho-upstream-hermetic-audit-2026-08-01.md)
installed `wbopan/retro-harness` in isolation. Its targeted DPP, ReasoningBank,
primitive-evaluation, and harmful/no-op promotion mechanics passed `29/29`.
The full hermetic suite was `294 passed, 6 failed, 1 collection error, 1
skipped`; failures are typed environment/upstream compatibility issues, not
silently converted passes. This validates RHO mechanics only, not its reported
held-out benchmark lift or a Frankengate integration.

The faithful [`AgentRx static-stage audit`](experiments/summaries/agentrx-independent-static-audit-2026-07-31.md)
ran the pinned upstream IR converter and `AllVerifier` over seven bundled Tau
trajectories. All seven IRs validated, but the bundled static artifact covered
`0/10` labeled failure steps and emitted zero violations because no dynamic
invariants were loaded. The same artifact's eight Python invariant snippets
also fail compilation. A diagnostic repair of only those syntax and trigger
defects recovered 3/10 labeled failure steps but emitted 26 violations, so it
is not sufficient for efficacy scoring. This is a bounded upstream
compatibility result, not a full AgentRx efficacy test; dynamic generation,
retained judge artifacts, and blinded diagnosis scoring remain required.

The long-horizon [`Luna SkillOpt factorial`](experiments/summaries/alfworld-luna-skillopt-four-family-35step-2026-07-31.md)
used four family-disjoint valid-unseen ALFWorld tasks, a 35-step cap, and
no-skill, formatting-placebo, and the pinned Microsoft SkillOpt candidate. All
three arms were `0/4` with zero invalid actions and independent replay passed.
This is a valid null on a zero-headroom cohort, not a general claim that
SkillOpt is ineffective.

The frontier [`self-feedback loop`](experiments/summaries/alfworld-luna-self-feedback-four-family-35step-2026-07-31.md),
[`generated durable memory`](experiments/summaries/alfworld-luna-generated-memory-four-family-35step-2026-07-31.md),
and [`family-matched retrieved memory`](experiments/summaries/alfworld-luna-retrieved-memory-four-family-35step-2026-07-31.md)
interventions were also independently replayed. Each had `0/4` wins on the
same four held-out families; self-feedback added two invalid actions while the
memory arms added none. The generic
[`outcome release gate`](experiments/summaries/outcome-release-gate-memory-retrieval-2026-07-31.md)
therefore quarantines all three candidates and sets exposure to zero.

The complementary [`canary/rollback lifecycle fixture`](experiments/summaries/mlops-feedback-canary-rollback-2026-08-02.md)
exercises the opposite operational path: a verified positive candidate is
released to a 10% canary, passes the first monitoring window, fails the second
window on success lift and invalid-action delta, and is rolled back to the
previous artifact with zero exposure. It is deterministic lifecycle evidence
only; no model or user utility is claimed.

The [`SkillOpt × retrieved-memory interaction factorial`](experiments/summaries/alfworld-luna-interaction-factorial-four-family-35step-2026-07-31.md)
tested all four combinations on those tasks. Every pair tied, with no main
effect, positive interaction, or validity regression. Because every arm was
also `0/4`, this is a mechanics-complete interaction null with no success
headroom; a powered cohort with baseline wins is still required.

The same-corpus [`TurboVec retrieval benchmark`](experiments/summaries/turbovec-codetracebench-2026-07-31.md)
is a component result only: 2-bit compression preserved Recall@20 (`0.6667`)
and top-1 (`0.6364`) versus exact vectors, with `0.1125 ms` mean query time,
`0.9483` filtered exact-top-k overlap, and deletion/allowlist checks passing.
It does not establish lexical search, authorization, deletion-ledger, or skill
utility, so no backend promotion follows.

The [`MATM local embedding similarity benchmark`](experiments/summaries/matm-embedding-similarity-benchmark-2026-08-02.md)
adds a loopback Ollama `nomic-embed-text` arm over 2,130 public trajectories.
On 33 leave-one-model-out folds with the goal hidden, embedding action-only
retrieval improved same-work Recall@20 by 12.3 points over lexical action-only
(bootstrap CI +5.3 to +20.6), while successful-neighbor precision improved only
3.1 points with a CI crossing zero. This supports semantic review retrieval,
not skill utility, custom-model promotion, or similarity-based employee claims.

The [`frontier MATM reranker checkpoint`](experiments/summaries/matm-frontier-reranker-2026-08-02.md)
then compared nine leave-one-model-out candidate pools using lexical ranking,
cached embeddings, and `gpt-5.6-luna`. Lexical and Luna both reached MRR and
Recall@1/3/5 of `1.0`; embedding MRR was `.674`, and Luna's top-3 success rate
`.704` tied lexical. The candidate pool and same-goal labels were silver and
frontier calls saw no outcomes, so this is a null incremental ranking result,
not a semantic-insight or skill-utility claim. Keep frontier ranking off the
hot path and reserve it for ambiguous hard-negative adjudication or human review.

The [`MATM cascade cost replay`](experiments/summaries/matm-embedding-model-cascade-cost-2026-08-04.md)
reran the same nine calls with wall-clock instrumentation. All calls completed
in `104.118s` total (`11.569s` mean), without changing the quality metrics. The
CLI token counter is retained only as a diagnostic, not as provider billing.

The direct [`native Codex paraphrase replication`](experiments/summaries/defog-codex-frontier-native-paraphrase-multiseed-2026-08-02.md)
completed a balanced three-seed, four-arm transfer test over renamed broker tasks.
No-skill scored `8/12`, formatting placebo `10/12`, length-matched neutral `9/12`,
and trace-mined terminal discipline `9/12`; all 48 trajectories passed authority
and independent semantic verification. Trace-mined versus neutral tied exactly
(`1–1`, ten ties, exact McNemar `p=1.0`) and versus no-skill was only `+0.083`
(`p=1.0`). The trace arm used fewer SQL attempts/tool calls, but did not improve
semantic correctness. Its direction also reversed relative to the loopback-proxy
paraphrase aggregate, so the current artifact is not promotion-eligible and the
transport/harness effect is itself a required replication variable.

The [`stratified alias adjudication gate`](experiments/summaries/nl2sql-stratified-alias-adjudication-2026-08-02.md)
adds the missing NIL and ambiguous cases to the earlier collision sample. Two
independent Luna roles scored 23 synthetic exact-alias, semantic-alias,
wrong-system, NIL, and unclear cases with perfect construction-time accuracy,
abstention, and agreement. This validates the label contract and verifier only;
authorized enterprise examples and SME labels remain required.

The [`real Defog alias/NIL benchmark`](experiments/summaries/nl2sql-real-alias-benchmark-2026-08-03.md)
then ran the same idea against a real public NL2SQL cohort. On 22 frozen cases,
exact/lexical/dense target MRR was `.893/.806/.690`, while Luna reached `1.0`
and abstained on all 8 constructed scope-swapped NIL cases. The result supports
an explicit late-stage abstention gate, not automatic semantic-alias truth or
artifact utility; enterprise/SME labels and changed-system replay remain open.

The [`same-scope collision benchmark`](experiments/summaries/nl2sql-same-scope-collision-2026-08-03.md)
isolated the failure mode hidden by broad gold-object labels. Across 17
deterministic focus-object proxies with same-normalized-name siblings in one
database, Nomic dense retrieval put a sibling before the proxy target in 23.5%
of cases, versus 5.9% for lexical retrieval and 0% for exact matching; Luna
reached `.941` Recall@1 with 0% collision-before-target. This is not semantic
alias truth, but it empirically supports table/column identity preservation and
selective frontier adjudication for ambiguous same-scope candidates.

The [`database-family-held-out adaptation benchmark`](experiments/summaries/nl2sql-collision-embedding-adaptation-2026-08-03.md)
then trained a small hard-negative pair adapter on two schema families and
tested on the third. It underperformed deterministic structured scoring and
raised collision-before-target to 51.2%. Table-aware embeddings improved
identifier-only Recall@1 but still had 29.8% collision-before-target. This is a
negative promotion result, not a disproof of custom-embedding research.

The [`identifier-aware held-out reranker`](experiments/summaries/nl2sql-identifier-reranker-2026-08-03.md)
tested a cheaper alternative: a leave-one-database-out logistic ranker over
scope, table/identifier surfaces, token overlap, lexical score, and collision
features. It reached `.647` Recall@1 and `.882` Recall@5 with 0% observed
collision-before-target, while 4x hard-negative weighting added no lift. This
supports a cheap structured reranking lane before frontier review, not a claim
that the model learned corporate semantic aliases.

The sealed [`BIRD changed-agent outcome checkpoint`](experiments/summaries/changed-agent-outcome-bird-2026-08-02.md)
is the largest current future-task replay: 20 family-disjoint tasks produced
20 candidate/control ties, zero exact-outcome wins or losses, and a latency
ratio of `.989`. It is bounded no-lift evidence, not a disproof of skill-learning
research or a universal enterprise null.

The [`validated-artifact consumption screen`](experiments/summaries/artifact-reuse-visible-paraphrase-four-task-2026-08-03.md)
closes a narrower missing mechanics gate. Across four paired Defog paraphrases,
no-skill, placebo, and previously validated SQL artifacts all reached `4/4`;
the artifact arm used 4 versus 6/5 SQL attempts and every trajectory passed
independent governed-PostgreSQL semantic recomputation. Because each artifact
was paired with its paraphrase, this is an upper-bound consumption test, not
evidence of retrieval or causal reuse benefit.

The [`train-only validated-artifact retrieval benchmark`](experiments/summaries/validated-artifact-retrieval-benchmark-2026-08-03.md)
is the first unpaired reuse screen. A same-database lexical retriever selected
validated artifacts for ten held-out broker/car questions; all ten were
authority-authorized and executable, but none matched the target semantics.
This is a bounded negative result: nearest-question lookup is insufficient,
not evidence that structured templates, dense retrieval, or frontier
adjudication cannot help.

The follow-up [`retrieval-family comparison`](experiments/summaries/validated-artifact-retrieval-comparison-2026-08-04.md)
tested lexical, frozen Nomic dense, SQL-identifier-aware, and lexical+dense
hybrid selectors on the identical cohort, including top-three governed
execution. Every scope-filtered arm remained `0/10` on semantic transfer. With
scope removed, lexical and dense selected the correct database `7/10` times,
while identifier and hybrid selected it `5/10` times. This strengthens the
bounded null: the problem is not only lexical ranking, and database/project
scope must be a hard boundary. No structural NIL cases were available in this
two-database cohort, so NIL abstention and regeneration remain open gates.

The [`artifact-pool coverage ceiling`](experiments/summaries/validated-artifact-pool-coverage-2026-08-04.md)
then executed every one of the 33 admitted source artifacts against every one
of the ten targets: all 165 executions were authorized, but zero targets had
any semantically equivalent source artifact. Even an evaluation-only
target-gold structural oracle found `0/10` top-one and top-three matches. This
classifies the current null primarily as missing library coverage: better
ranking cannot recover query plans that are not present. The next artifact
test must therefore include parameterized/composable templates and frontier
regeneration, not only more nearest-neighbor tuning.

The controlled [`shared-intent artifact benchmark`](experiments/summaries/validated-artifact-shared-intent-2026-08-04.md)
provides that missing positive control. Twenty deterministic prompt-only
paraphrases each had a known reusable source artifact; lexical, frozen Nomic,
and hybrid retrieval recovered it top-one `20/20`, with all `60/60` top-three
governed executions authorized and semantically correct. This is an upper-bound
mechanics result, not natural enterprise utility: the next test needs
SME-labeled paraphrases, parameterized variation, regeneration, and changed
system outcomes.

The [`composable artifact frontier replay`](experiments/summaries/composable-artifact-frontier-replay-2026-08-04.md)
then tested validated source-query subplans rather than whole-query nearest
neighbors. In the authoritative unique seed-840000 rerun and seed-850000
receipt, the composable procedure reached `10/10` semantic correctness versus
`5/10` for no-skill and `5/10` for a formatting placebo, with independent
verification, zero unauthorized observations, and fewer SQL/tool calls. The
original default receipt path was overwritten by a concurrent worker and is
quarantined; it is not used in these counts. This is a promising composability
signal, not a powered causal or cross-family result; changed schemas,
regeneration, NILs, and negative transfer remain required.

The [`frontier-versus-local Wisp adjudication`](experiments/summaries/wisp-frontier-local-adjudication-2026-08-03.md)
tested whether a frontier model and a local model could be treated as
interchangeable trace-insight labelers. On six blinded candidates under the
same contract, all-field agreement was `0%`; field agreement ranged from `0%`
for usefulness to `33.3%` for cause. Luna's output was schema-valid and every
evidence reference was candidate-local, but agreement is not correctness. The
result supports using inexpensive models for triage/drafting only, with
independent model or human adjudication before promoting a memory, skill, or
eval.

The next enterprise gate is preregistered in the
[`semantic-label and changed-system replay protocol`](experiments/protocols/enterprise-semantic-label-and-drift-2026-08-03.md).
It freezes candidate generation before SME labels, requires user/project/system/time
holdouts, and treats false semantic acceptance during schema/tool drift as a
release-blocking failure.

The 2026 skill-lifecycle refresh adds [SKILL-DISCO](https://arxiv.org/abs/2606.26669),
[RESOURCE2SKILL](https://arxiv.org/abs/2606.29538), and the [SoK on agentic
skills](https://arxiv.org/abs/2602.20867). They reinforce the two-layer
artifact design: an executable, parameterized procedure for replay plus a
provenance/identity packet for semantic and governance checks. They do not
close the enterprise changed-system or causal-utility gates. The exact/adjacent
classification is recorded in
[`skill-library-prior-art-update-2026-08-02.md`](experiments/summaries/skill-library-prior-art-update-2026-08-02.md).
The representation comparison is now preregistered in
[`skill-representation-and-replay-2026-08-01.md`](experiments/protocols/skill-representation-and-replay-2026-08-01.md):
no-skill, length-matched prose, retrieval memory, executable procedure, and
executable-plus-evidence arms on changed systems.
The domain-embedding refresh records convergent evidence from semiconductor
logs, process-industry graph contrastive learning, interpretable event
features, and retrieval-augmented schema linking:
[`skill-hard-negative-prior-art-update-2026-08-02.md`](experiments/summaries/skill-hard-negative-prior-art-update-2026-08-02.md).
It also records the important positive schema-retrieval precedent: a
leave-one-corpus-out study uses schema-generated queries and
granularity-aware hard negatives, so our MATM adapter null is not a blanket
negative result for domain adaptation.
The matched follow-up is preregistered in
[`schema-adaptive-embedding-2026-08-01.md`](experiments/protocols/schema-adaptive-embedding-2026-08-01.md).
Its first run covers 601 schema-grounded cases across four leave-one-database-
family-out folds. Frozen Nomic beat the regularized schema-adaptive pair scorer
on MRR (`.1824` vs `.1573`), Recall@1 (`.0933` vs `.0761`), and Recall@10
(`.3760` vs `.3214`); the scorer also had slightly more same-scope collisions
before the target (`.1094` vs `.1013`). This is a stronger public-proxy null,
not a disproof of corporate embedding adaptation: generated labels, no SME
aliases/NILs, and no downstream artifact utility were measured.
The corrected v2 receipt adds known-scope scoring: frozen Nomic MRR `.217356`
versus the pair scorer `.201527`, with Recall@10 `.447275` versus `.425539`;
pooled-corpus metrics remain `.182393` versus `.157347`. The v2 result and
independent verifier are linked from
[`nl2sql-schema-adaptive-retrieval-2026-08-01.md`](experiments/summaries/nl2sql-schema-adaptive-retrieval-2026-08-01.md).

## Claim boundary

The committed experiments currently establish representation, authorization,
structural-selection, and proposal mechanics. They do not yet satisfy the program's
full E0–E7 acceptance gates. In particular:

- a bounded failure-to-later-success episode is a review candidate, not causal repair;
- a stored-trace assertion is a retrospective audit, not a rerun;
- an independent benchmark pass is not longitudinal user learning;
- no public corpus supplies a gold enterprise skill-gap label;
- cross-user suggestions require consent, minimum cohorts, privacy defenses, and
  prospective outcomes; and
- custom embeddings remain gated on a frozen hard slice where exact, PostgreSQL
  full-text, and structured retrieval demonstrably fail; and
- the SQL replay/verifier boundary passes on all 95 executable Defog tasks and
  the no-skill/placebo/expert-seed mechanics factorial has run, but it failed
  its terminal-protocol gate; the independent synthetic and governed
  trace-mined pilots prove runtime compatibility but not remediation; the
  governed four-task pilot produced one successful SQL execution in the mined
  arm but zero terminal or semantic wins; solver/evaluator capability
  isolation, a fresh P0, and the causal quality screen have not run.
