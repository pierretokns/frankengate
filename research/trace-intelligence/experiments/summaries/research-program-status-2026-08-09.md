# Corporate trace artifact-learning status update (2026-08-09)

This update consolidates the latest independent runs. It is a status ledger,
not a claim that the full enterprise research objective is complete.

## What is now supported by evidence

### 1. Validated artifact mechanics

Recorded SQL/tool success must be independently executed and validated before
it becomes an artifact. In the BIRD trace corpus, only **76/193** executable
trace candidates matched the independent gold result. Typed parameter replay
then succeeded **75/75** in a controlled cohort. The lesson is to store
validated, parameterized capsules with scope, schema, authority, freshness,
and replay validators—not raw successful calls.

### 2. Retrieval has two separate jobs

The no-target-append TRAJECT-Bench reranker control showed that Luna can improve
ordering among already-covered candidates (MRR `.360 → .886`) while target
coverage remains `.458`. A ToolQP-inspired query-planning probe improved
public-tool coverage (`.667 → .750`) and MRR (`.348 → .563`) on eight diverse
cases. These are candidate-generation/ranking results, not artifact acceptance.

When applied to the harder BIRD SQL artifact cohort, however, query planning
produced **0/16** executable matches at @1, @5, and @10, just like the lexical
baseline. The artifact pool contained almost no naturally repeated compatible
procedures. Query planning cannot create a missing artifact.

### 3. Trajectory supervision is adaptable but incomplete

The LRAT public sample audit found 10 completed trajectories, 280 ordered
steps, 130 tool calls, and 130 non-empty outputs. The samples contained no
explicit correctness, failure, friction, reward, or enterprise-artifact
fields. LRAT is therefore a good candidate-coverage method to adapt, not a
complete corporate skill-learning dataset.

Cursor provides the closest production precedent for the next retrieval arm:
its published method uses later search/open behavior plus frontier ranking to
distill a custom retriever, then checks it with both an internal session-derived
benchmark and controlled online ablations. This validates the *protocol* we
should reproduce, not a claim that Cursor's private model transfers to governed
SQL/tools. Our adaptation must add exposure sets, authority/refusal reasons,
replay outcomes, changed-system holdouts, and explicit NIL/wrong-system labels.
See [Cursor historical retrieval supervision](cursor-historical-retrieval-supervision-2026-08-09.md).

FastContext is a related but non-admissible source: its withdrawn arXiv record
describes a separate trajectory-trained repository explorer and reports strong
token/resolution gains, but the paper has no license and its linked repository
is unavailable. We retain the separation-of-exploration hypothesis as a future
experiment only; none of its numerical claims enter the evidence matrix. See
[the audit](fastcontext-withdrawn-method-audit-2026-08-09.md).

The independent [separate-explorer probe](traject-bench-separate-explorer-probe-2026-08-09.md)
tested that surviving hypothesis on two eight-case Luna runs. On the public
tool-selection proxy, a full-pool explorer raised candidate coverage to `.750`
and `.708333` versus `.500` for both lexical baselines, while returning about
`3.8` tools instead of `16`. This is candidate-generation evidence, not
validated artifact utility; the full-pool prompt averaged about 45.9k
characters and per-call cost/latency were not recorded. Keep the explorer
optional and replay-gated.

The [WMH-BIRD SQL explorer bridge](wmh-bird-sql-separate-explorer-probe-2026-08-09.md)
then tested the same pattern against exposed tables and independent SQLite
replay. Across two eight-case runs, strict target MRR/Recall@1 were `1.0` for
the explorer versus `.8375/.75` for lexical top-8; replay-compatible selected
rate was `.979167` versus `.418006`, with a mean shortlist of `2.5` versus
`6.375`. This is a promising candidate-generation and noise-reduction result,
but the cases are a tiny public proxy with BIRD hints and no enterprise
authority or changed-system labels. It does not authorize alias or artifact
promotion.

The larger [44-case task-disjoint SQL explorer cohort](wmh-bird-sql-explorer-cohort-2026-08-09.md)
preserves the signal: explorer strict MRR/Recall@1 were `.965909/.931818`
versus `.796266/.704545` for lexical top-8; replay-compatible selected rate was
`.924242` versus `.391153`, and the explorer selected `2.068` tables on average
versus `5.545`. The effect is not universal—Debit Card Specializing and
Thrombosis Prediction were weaker—so family-stratified failures remain part of
the gate. This is still a hinted public proxy without authority, human intent,
or changed-system outcomes.

### 4. Structured tool fields are useful metadata, not a retrieval replacement

The field-aware TRAJECT-Bench probe evaluated 5,297 domain-scoped records with
name-only, name-plus-description, field-aware, and identifier/schema arms. On
1,975 hard records, field-aware Recall@10 was `.423` versus `.421` for name-only,
but MRR was lower (`.631` versus `.671`) and descriptions reduced MRR to `.574`.
This is enough reason to preserve parameter/API/output fields for later
compatibility checks, but not enough reason to promote field-weighted lexical
ranking or claim semantic alias resolution.

The [SSL Scheduling--Structural--Logical crosswalk](ssl-representation-crosswalk-2026-08-02.md)
places that result against the recent skill-registry paper: SSL reports a
positive `.649 -> .729` MRR@50 change on 6,184 public skills, but our trace
probe is not an SSL reproduction because it lacks grounded scene graphs,
logical effects, authority decisions, and verified outcomes. The adaptable
part is the projection model: derive interface, execution-DAG, and typed
effect views from the same trace IDs while keeping LLM normalization
review-only. This is a representation-design hypothesis, not yet a corporate
skill-learning result.
The follow-up [SSL-shaped TRAJECT proxy](traject-bench-ssl-proxy-2026-08-02.md)
held domain-local candidate pools fixed across 5,297 records. Scheduling-only
metadata tied name retrieval, while structural/logical proxies reduced hard
Recall@10 (`.405251` name versus `.291558` structural and `.346664` logical);
the rich combination recovered only simple-query Recall@10 by `.004527` and
lost hard-query Recall@10. This is a proxy null caused by missing grounded
scene/effect labels, not a disproof of SSL, and it reinforces that metadata
concatenation is not enough.
The [frontier SSL normalizer probe](traject-bench-ssl-normalizer-probe-2026-08-02.md)
then tested grounded extraction on 20 public tool records. Luna preserved
exact tool/API/domain identifiers on `20/20` and achieved `0.9875` evidence
substring grounding, but emitted zero structural scenes and only one
conservative logical action per record. This shows that a frontier model can
produce a grounded skeleton, while single-tool descriptions lack the
trajectory structure needed for rich SSL scenes/effects; normalization remains
review-only until tested on multi-step traces.
The follow-up [multi-tool trajectory probe](traject-bench-ssl-trace-normalizer-probe-2026-08-02.md)
used 19 eligible parallel/sequential records. Tool order and logical action
order were preserved `19/19`; the model emitted `2.63` scenes and `.63`
transitions per trajectory, but fully grounded every evidence quote on only
`.684` of records (sequential `.556`). This confirms that real trajectories
unlock the structural signal while showing why scene/effect normalization must
remain review-only and replay-backed.
The [real cctrace session probe](cctrace-ssl-normalizer-probe-2026-08-02.md)
extends this to one MIT-licensed Claude Code session: 10 bounded episodes
preserved tool/action order `10/10`, emitted `1.9` scenes and `.9` transitions
per episode, and fully grounded `.800` of episodes (`.922619` of evidence
items). This validates the ingestion/normalization path on coding traces, but
one publisher and no independent terminal labels are insufficient for skill,
alias, or cross-user claims.
The companion [cctrace quality audit](cctrace-ssl-normalizer-quality-audit-2026-08-02.md)
checked the external model outputs against source invariants: action order,
scene coverage, and transition references all passed `1.000`, while the
conservative tool-name action-type reference reached `.983607`. This supports
using the projection as a structurally complete review artifact, not as a
semantic correctness or skill-utility label.
The [parameter-aware artifact probe](cctrace-artifact-capsule-probe-2026-08-02.md)
found a separate schema edge: input-key fidelity was `1.000`, but repeated
top-level tool order was `0.0`, per-action resource identity was only `.300`,
and `.918` of actions were conservatively literal-only. This requires separate
immutable tool identity, resource reference, parameter bindings, and template
fields; a model-proposed template is never a replay authorization.
The [deterministic capsule round-trip](cctrace-deterministic-capsule-roundtrip-2026-08-02.md)
then compiled the same 10 episodes without a model and preserved tool order,
input keys, action order, invocation uniqueness, and source provenance at
`1.000`. This is the correct artifact identity baseline; model enrichment must
attach to it rather than replace it.
The cross-harness [Claude command normalization audit](claude-command-artifact-normalization-2026-08-09.md)
found 1,352 paired Bash outcomes: parameterized normalization collapsed 140
extra exact commands into 29 collision buckets and produced 3 mixed-outcome
buckets, even though all observed repeats succeeded. Normalized keys are
therefore candidate-retrieval aids only; immutable invocation identity,
scope, and bindings must remain separate.
The four-cohort [Claude command transfer audit](claude-cross-cohort-command-transfer-2026-08-09.md)
found only one exact artifact shared across cohorts, versus nine normalized
artifacts covering 72 occurrences with one failure. Jobseek normalized
cross-scope reuse was `72.22%`, below its `96.67%` same-scope rate. This is
direct evidence for scope-bound retrieval and against cross-user automatic
artifact reuse.
The [cross-domain identifier transfer probe](nl2sql-identifier-cross-domain-transfer-2026-08-09.md)
found asymmetric generalization: Defog→BIRD improved MRR from `.731684` to
`.760996`, while BIRD→Defog fell from `.682284` to `.622864`. Hard-negative
weighting was not portable. Preserve the identifier-aware lane, but train and
validate it with domain-specific collision families rather than assuming one
universal ranker.
The [cross-cohort termhood stability probe](termhood-cross-cohort-stability-2026-08-09.md)
found 217/293 top-term hashes unique to one cohort and only 5 shared by all
four. This supports tenant/project-scoped concept mining and reviewed linking,
not a global alias table or embedding trained from raw frequency.
The [cross-cohort acronym stability probe](acronym-cross-cohort-stability-2026-08-09.md)
found 40 valid acronym hashes and 56 valid acronym/full-form pairs, all local
to one cohort, with no shared valid acronym across the four cohorts. This keeps
the acronym port in a scoped review queue and provides no support for a global
dictionary from public traces alone.
The [cross-corpus SQL artifact signature probe](cross-corpus-sql-artifact-signatures-2026-08-09.md)
found zero shared exact templates, one shared typed schema-agnostic template,
and two shared coarse operator shapes across BIRD and Defog. Every shared
shape had multiple exact variants, so both structural collision rates were
`1.0`. This is a dataset-fit boundary: schema-free retrieval cannot replace
identifiers, authority, compatibility checks, or replay validation.
The [strict DataClaw cross-user artifact transfer probe](dataclaw-cross-user-artifact-transfer-2026-08-09.md)
found zero shared strict artifact identities between Peter and Vaynelee, even
though the earlier permissive overlap audit found 11 shared non-trivial forms.
Broad overlap is therefore a candidate-recall signal, not evidence for
cross-user artifact promotion.
The complementary [same-user support probe](dataclaw-same-user-artifact-support-2026-08-09.md)
found 3,158 Peter candidates repeated across sessions, 518 across projects,
and 460 that were both cross-project and friction-adjacent. This is the first
bounded positive for a scoped personal/project library, still requiring replay
and changed-system gates. Its recurrence/friction relationship reversed in the
small Vaynelee cohort, so recurrence is not a universal friction label.
The [strict Claude tool-artifact miner](claude-history-tool-artifact-miner-2026-08-09.md)
found 2,012 normalized identities recurring across sessions, 1,105 across
projects, 431 mixed-outcome identities, and 3,866 error→success recoveries.
This supplies a much larger candidate/recovery queue, while confirming that
observed tool success is not an independent correctness or safety label.
The [temporal prior-success benchmark](claude-history-tool-artifact-temporal-2026-08-09.md)
then measured `88.7216%` success with no prior identity success versus
`96.8268%` after same-project prior success and `97.1615%` after prior success
in another project, with session-boundary leakage prevented. This supports a
ranked prior feature, not automatic reuse or causal skill improvement.
The parameterized key-shape control was negative: key-only priors reached
`90.5514%` same-project and `90.7613%` cross-project success versus `92.3108%`
with no prior key-shape. Exact parameter bindings and resource identity are
therefore load-bearing; coarse templates remain recall-only until replayed.
The tool-class split is operationally important: same-project exact priors lifted
shell success from `69.7511%` to `93.8326%` and mutation from `94.1272%` to
`99.3243%`, while read/search was near ceiling and slightly lower after prior
reuse. Prior policies must be tool-class-specific and safety-gated.
The stricter [frozen artifact-drift holdout](claude-history-tool-artifact-drift-2026-08-09.md)
used the first 216 sessions only to build priors and scored the later 216
without updating them. Exact same-project priors still reached `97.0973%`
versus `90.7174%` with no early prior (+6.3798 points), and exact
other-project priors reached `96.0253%` (+5.3078 points). The smaller late
period lift supports time-aware expiration/versioning rather than assuming
stationarity. The key-shape negative became stronger: same-project
key-shapes were `92.1738%` versus `98.4278%` with no early key-shape (−6.2541
points), and other-project key-shapes were `89.4219%` (−9.0060). This is
evidence for exact, scoped candidate priors only; it is not semantic or causal
skill evidence.
Same-session recovery calls provide a targeted eval/friction lane: 3,866/4,506
later calls succeeded after an earlier identity error, but shell recovery was
only `33.5766%` and mutation `76.2500%`. Recovery should be sampled for repair
analysis and replay, not treated as automatic skill evidence.
The [DataClaw project adapter probe](dataclaw-project-adapter-2026-08-09.md)
improved Peter's full-cohort combined project-held-out MRR `.769341→.854452`, but left
Vaynelee's combined MRR unchanged at `.978495` because that cohort was near
ceiling. This is scoped adaptation evidence, not a universal custom-embedding
promotion result.

### 5. Older vocabulary ports remain narrow

The TermSuite/Termolator-style port provides interpretable candidate terms:
termhood recall was `.358` when the schema vocabulary was represented but only
`.015` on held-out transfer. The AcronymExpansion-style port passed `8/8`
synthetic ambiguity/NIL probes. Both remain offline review primitives; neither
has shown enterprise alias precision, embedding lift, or skill improvement.
On a separate 432-session, 65-project public Claude history export, 777/2,249
top-term hashes and 36/170 valid acronym hashes crossed project boundaries,
but no candidate appeared in every project. This is the strongest evidence for
scoped candidate mining so far, while still ruling out frequency-only global
alias promotion.
The term-context collision follow-up found 543/778 shared terms with at least
one cross-project pair below `.05` lexical-context Jaccard, so recurrence can
feed a cheap hard-negative queue before identifier and human review. This is a
lexical diagnostic, not a semantic collision label.
The [term-context model probe](claude-history-term-context-model-probe-2026-08-09.md)
then tested whether frontier review needs that context. Term-only Luna calls
abstained `24/24`; term-plus-context calls labeled all six high-overlap pairs
`same_concept`, while the six low-overlap pairs split into five `different`
and seven `related_context` labels across repeats, with only `3/6` pair
agreement. This supports context-bearing review prompts and explicit
`unclear`/related outcomes, but remains a silver calibration study because the
cohorts were selected by the same lexical statistic and lack SME alias/NIL
labels.
The [same-cohort alias cascade audit](nl2sql-alias-cascade-audit-2026-08-09.md)
now makes the retrieval/refusal boundary explicit: on 14 target and 8 NIL
cases, exact structured MRR was `.892857`, dense `.689966`, lexical `.805844`,
and frontier `1.0`; every retrieval arm still proposed a candidate for every
NIL. The frontier decision layer can abstain, but ranking quality and refusal
must be measured separately. This is gold-SQL/synthetic proxy evidence, not
independent corporate alias truth.
The category split is important: explicit surface cases were already perfect
for lexical/exact/frontier (`1.0` MRR), while the eight implicit-target proxy
cases scored lexical `.660227`, exact `.812500`, dense `.603274`, and frontier
`1.0`. Thus frontier review's apparent gain is concentrated in ambiguity, not
routine identifier lookup; it needs independently reviewed aliases and NILs
before any semantic claim.

### 6. Custom embedding evidence is not yet promotion-positive

The fold-local MATM adapter was effectively neutral (`Recall@20 .5301 → .5331`,
MRR `.3315 → .3300`, intervals crossing zero). The database-family-held-out
schema adapter underperformed deterministic structured ranking and had 51.2%
collision-before-target. Finance-specific embeddings performed well on a
finance corpus, but that does not establish corporate trace transfer. The
current evidence supports testing domain adapters in a shadow lane only after
SME-labelled aliases, NILs, wrong-system negatives, and downstream utility
labels exist.
An independent Claude-history project-held-out adapter reproduced a smaller
positive (user-message MRR `.885892→.915765` across 37 folds), so the scoped
lexical adaptation lane is repeatable on two public history corpora. It remains
a silver project-similarity result, not evidence for a deployable corporate
embedding.

### 7. Cross-user insight and skill-gap claims remain unproven

Trace Commons and two-user DataClaw audits show that exact prompt/tool overlap
is low and that harness boilerplate can dominate similarity. Frontier
adjudication can produce a review queue, but there are no independent labels
for business intent, employee capability, satisfaction, collaboration value,
or negative transfer. We cannot yet claim that the system identifies who is
doing the same work or which skills a person is missing.

### 8. Friction mining needs structural review, not keyword labels

The corrected native Codex importer found 47,122 user episodes, 228 adjacent
rephrase pairs, and 273 marker-based error-to-success episodes, but lexical
friction markers had only `.79%` precision against a structured process-exit
proxy. A separate public DataClaw Luna calibration (12 stratified messages,
two calls each) reached 11/12 repeat-label agreement; re-prompt overlap was
friction on 4/6 calls, while lexical markers over-flagged productive work.
This supports a review queue built from event ordering and correction/retry
structure, with independent tool/result outcomes required before eval or skill
promotion. It does not establish satisfaction, intent, or employee skill.

### 9. Dataset fit is a hard gate

The current manifest audit covers 44 pinned public datasets. Only **2/44**
are direct-fit for NL2SQL schema retrieval and **3/44** are direct-fit for
basic trace structure. None are direct-fit for friction recovery, causal skill
improvement, cross-user similarity, or reviewed term/alias quality. The rest
are mechanics or proxy corpora. This is why results from WMH-BIRD, BIRD-Interact,
Trace Commons, DataClaw, CodeTraceBench, and MAGIC must remain separate arms;
pooling them would manufacture labels and invalidate the enterprise claims.

### 10. ToolQP's planning and aggregation effects are separable

The official ToolQP method combines iterative query planning, synthetic-trace
SFT, RLVR/GRPO, and peak-rank aggregation. Our bounded inference-stage replay
held the planner outputs fixed and compared aggregation only: peak rank kept
top-16 coverage at `.750` but scored MRR `.419`, versus `.563` for the simpler
query union. This is not a contradiction of the paper; it shows that Frankengate
must measure planner quality, retriever coverage, and aggregation independently
before adopting a trained planner or claiming enterprise artifact value.

The LRAT exposure audit adds a parallel boundary: 598/624 exposed documents in
the public samples were not browsed, so exposure-aware candidate negatives are
available. They are not independently irrelevant labels. Frankengate must
record refusal/authority/cost reasons and require replay or SME outcomes before
turning exposure gaps into hard-negative training data.

The WMH-BIRD SQL analogue is stronger: 1,993 traces expose 11,707 schema table
identifiers and consume 3,850, leaving 7,857 exposure candidates. This is a
usable bridge from trajectory supervision to SQL artifact mining, but unused
tables still require independent database replay and wrong-system/temporal
negative labels before embedding or reranker training.
The follow-up counterfactual replay selected 149 successful task traces and
tested 1,236 exposed-table substitutions: 1,210 errored, 22 changed the result,
and only 4 preserved it. On 71 held-out table-retrieval cases, the termhood
field raised Recall@5 from `.887` to `.930` while leaving Recall@1 unchanged.
These are compatibility negatives and candidate-recall evidence, not semantic
wrong-system labels or enterprise alias truth.
The replay-negative ranker comparison reached Recall@1 `.704` and Recall@5
`.958` for both naive and replay-filtered training, above lexical `.676/.887`.
Replay filtering added no lift because the training split contained no
result-preserving ambiguities; an enterprise cohort must include those hard
edges before a hard-negative objective or custom embedding can be justified.
The follow-up [exact versus execution-equivalent retrieval](wmh-bird-equivalence-aware-retrieval-2026-08-09.md)
made that boundary explicit: only four of 1,236 substitutions preserved result
rows, and the held-out lexical/termhood metrics were unchanged. Alternate-only
Recall@10 was `.028169`, so this public cohort is too sparse to train or
validate semantic aliasing, but the benchmark now records both exact and
replay-equivalent target sets.
The combined [`embedding/model cascade decision`](embedding-model-cascade-decision-2026-08-09.md)
therefore keeps structured retrieval first, embeddings optional for broad
recall, and frontier models selective for ambiguity/review. It explicitly
rejects hot-path frontier scoring and universal custom-embedding promotion
until a consented enterprise cohort supplies semantic and downstream labels.
The [`WMH-BIRD step-fault audit`](wmh-bird-step-fault-audit-2026-08-09.md)
adds a bounded SkillAdaptor/HASP-style diagnosis substrate: first-fault
categories and later recovery are observable, but reward and replay disagree
on some traces. Targeted revision remains an untested intervention.
The follow-up [`fault-category checklist intervention`](wmh-bird-fault-category-intervention-2026-08-09.md)
is now a verified four-task, family-disjoint Luna factorial: all three arms
scored `0/4` exact. This is an underpowered null and a useful evaluator
diagnostic, not evidence that fault-category procedures cannot help. The next
run must stratify by fault category and include projection, tie, and NULL cases.
The independent SkillLearnBench changed-data proxy adds a complementary hard
edge: on a deterministic product rename, reviewed human guidance preserved
`1.000` precision/recall, the null retained recall but had one false positive,
and a generated composite missed one expected ID. This is one public task, so
it supports testing reviewed guidance before composition, not a causal skill
claim. A two-seed synthesis of that same task is now recorded separately:
reviewed guidance stayed `16/16`, while the composite was `15/16` and the null
was `15/16` with one false positive. Repeated seeds improve stability evidence
but are not independent task evidence.
The broader six-task enterprise-search family is stronger directional evidence:
null/generated/reviewed scored `43/53`, `46/53`, and `49/53` q1 IDs, while a
later reviewed+generated composite scored `53/53`; all q3 answers were exact.
The arms were not randomized in one simultaneous run, all tasks share one
public family, and the composite has a different context footprint, so this
supports a replication hypothesis—not skill promotion.
The [skill/artifact replay synthesis](skill-replay-evidence-synthesis-2026-08-09.md)
keeps the causal evidence in one decision map: typed semantic-ID admission
prevented `2` unsafe accepts in the changed-system fixture; reviewed guidance
was the only stable full-recall arm on the changed-data proxy; validated
subplans produced one stable win and no stable losses across 20 held-out BIRD
tasks; generic trace-mined prose tied no-skill at `8/40`; and the bounded
SkillOpt candidate tied both controls at `0/2` on ALFWorld. These are separate
protocols, so they do not justify a pooled effect estimate. The current
adoption boundary is typed admission plus replay-gated reviewed candidates,
not automatic skill composition or raw-log promotion.

## Architecture decision

Keep the smallest governed architecture:

```text
canonical loss-aware trace DAG
  -> exact identifiers + scope/authority filter
  -> lexical / structured candidate recall
  -> optional domain embedding or query-planning expansion
  -> identifier-aware ranking
  -> selective frontier/human review
  -> independent execution, validator, and replay gate
  -> versioned artifact/eval/skill proposal
```

Do not make a custom embedding, graph database, or automatic memory/skill
writer mandatory. Add each only when a frozen hard-negative cohort shows an
absolute retrieval or downstream-utility lift that survives temporal,
project, principal, and changed-system holdouts.

## Next decisive experiments

1. Build a consented enterprise cohort with repeated intents, validated SQL/tool
   artifacts, same-surface/wrong-system negatives, temporal renames, and
   independent human utility labels.
2. Compare exact/identifier, lexical, dense, query-planning, frontier, and
   combined cascades under fixed cost/latency budgets.
3. Replay candidate skills/evals on changed systems with no-skill, placebo,
   mined-artifact, and teacher arms.
4. Measure user outcomes: correction burden, task completion, time-to-success,
   learning, unwanted recommendations, and negative transfer.
5. Publish content-minimized receipts and a sealed evaluation API with MIT,
   CMU, or Harvard partners rather than releasing raw corporate traces.

## Authoritative receipts

- [SQL artifact reuse](bird-trace-artifact-reuse-2026-08-07.md)
- [SQL query-planning probe](bird-artifact-query-planning-probe-2026-08-09.md)
- [TRAJECT-Bench query planning](traject-bench-query-planning-probe-2026-08-09.md)
- [TRAJECT-Bench field-aware retrieval](traject-bench-field-retrieval-2026-08-09.md)
- [SSL representation crosswalk](ssl-representation-crosswalk-2026-08-02.md)
- [SSL-shaped TRAJECT proxy](traject-bench-ssl-proxy-2026-08-02.md)
- [frontier SSL normalizer probe](traject-bench-ssl-normalizer-probe-2026-08-02.md)
- [multi-tool SSL trajectory probe](traject-bench-ssl-trace-normalizer-probe-2026-08-02.md)
- [real cctrace SSL normalization probe](cctrace-ssl-normalizer-probe-2026-08-02.md)
- [cctrace normalized-output quality audit](cctrace-ssl-normalizer-quality-audit-2026-08-02.md)
- [cctrace artifact-capsule probe](cctrace-artifact-capsule-probe-2026-08-02.md)
- [deterministic cctrace capsule round-trip](cctrace-deterministic-capsule-roundtrip-2026-08-02.md)
- [LRAT trajectory audit](lrat-trajectory-audit-2026-08-09.md)
- [Cursor historical retrieval supervision](cursor-historical-retrieval-supervision-2026-08-09.md)
- [FastContext withdrawn-method audit](fastcontext-withdrawn-method-audit-2026-08-09.md)
- [TRAJECT-Bench separate explorer](traject-bench-separate-explorer-probe-2026-08-09.md)
- [WMH-BIRD SQL separate explorer](wmh-bird-sql-separate-explorer-probe-2026-08-09.md)
- [WMH-BIRD SQL explorer cohort](wmh-bird-sql-explorer-cohort-2026-08-09.md)
- [fault-category checklist intervention](wmh-bird-fault-category-intervention-2026-08-09.md)
- [SkillLearnBench changed-data frontier](skilllearnbench-changed-data-frontier-2026-08-06.md)
- [SkillLearnBench changed-data multi-seed synthesis](skilllearnbench-changed-data-multiseed-2026-08-09.md)
- [SkillLearnBench three-arm family replay](skilllearnbench-frontier-three-arm-2026-08-01.md)
- [SkillLearnBench composite six-task replay](skilllearnbench-frontier-composite-six-task-2026-08-06.md)
- [Older-tool modernization audit](older-tool-modernization-value-audit-2026-08-05.md)
- [Public DataClaw friction calibration](dataclaw-friction-luna-calibration-2026-08-09.md)
- [Dataset-fit audit](../results/dataset-fit-audit-2026-08-04.json)
- [ToolQP peak-rank reproduction](traject-bench-toolqp-peak-rank-2026-08-09.md)
- [LRAT exposure-negative audit](lrat-exposure-negative-audit-2026-08-09.md)
- [WMH-BIRD schema exposure audit](wmh-bird-schema-exposure-audit-2026-08-09.md)
- [WMH-BIRD exposure counterfactual](wmh-bird-exposure-counterfactual-2026-08-09.md)
- [WMH-BIRD replay-negative reranker](wmh-bird-replay-negative-reranker-2026-08-09.md)
- [WMH-BIRD exact versus execution-equivalent retrieval](wmh-bird-equivalence-aware-retrieval-2026-08-09.md)
- [Claude command-artifact normalization audit](claude-command-artifact-normalization-2026-08-09.md)
- [Claude cross-cohort command transfer](claude-cross-cohort-command-transfer-2026-08-09.md)
- [Acronym cross-cohort stability](acronym-cross-cohort-stability-2026-08-09.md)
- [Cross-corpus SQL artifact signatures](cross-corpus-sql-artifact-signatures-2026-08-09.md)
- [DataClaw cross-user artifact transfer](dataclaw-cross-user-artifact-transfer-2026-08-09.md)
- [DataClaw same-user artifact support](dataclaw-same-user-artifact-support-2026-08-09.md)
- [DataClaw project adapter](dataclaw-project-adapter-2026-08-09.md)
- [NL2SQL identifier cross-domain transfer](nl2sql-identifier-cross-domain-transfer-2026-08-09.md)
- [Termhood cross-cohort stability](termhood-cross-cohort-stability-2026-08-09.md)
- [Embedding/model cascade decision](embedding-model-cascade-decision-2026-08-09.md)
- [WMH-BIRD step-fault audit](wmh-bird-step-fault-audit-2026-08-09.md)
- [Current evidence matrix](current-evidence-matrix-2026-08-06.md)
