# NL2SQL as an enterprise skill-improvement domain

## Decision

Frankengate should make governed NL2SQL one of its first deep skill-learning
domains. It is substantially more useful than a spreadsheet-first domain for
the questions this program is trying to answer because SQL work exposes typed
decisions, tool calls, database errors, authorization outcomes, retries, and
executable results. Those observations make it possible to distinguish a
missing skill from a bad model, missing business context, ambiguous intent, or
an unsafe execution policy.

This is not a recommendation to train on every public SQL pair or to judge users
by benchmark accuracy. The product value comes from:

1. decomposing SQL work into observable sub-skills;
2. mining repeated failure-to-repair paths;
3. retrieving successful procedures from authorized peers;
4. testing candidate guidance causally on held-out database families; and
5. showing users evidence-backed suggestions without exposing another user's
   trace content.

The existing Aurora/PostgreSQL, OpenTelemetry, canonical trajectory, governance,
and eval lifecycle remain the smallest sufficient architecture. No new
database, vector engine, or fine-tuned embedding model is required for the
first NL2SQL study.

## What the current evidence can and cannot prove

| Evidence | What it contributes | What it cannot prove |
| --- | --- | --- |
| [WMH BIRD-SQL traces](https://huggingface.co/datasets/experiential-labs/wmh-bird-sql-traces) | 1,993 real agent runs and 4,168 ordered tool/environment transitions over 222 traced tasks and 11 databases; procedure and failure mining | Natural employee behavior, wall-clock latency, full OTel causality, or a causal skill effect |
| [WMH CRMArena traces](https://huggingface.co/datasets/experiential-labs/wmh-crmarena-traces) | 80 enterprise-analytics runs and 553 transitions; a non-SQL control for tool routing, entity disambiguation, policy, and case handling | Commercial training, cross-organization transfer, or SQL competence |
| [Microsoft MAGIC](https://huggingface.co/datasets/microsoft/MAGIC) | 48,124 feedback/correction/manager rows, including success and five-iteration exhaustion; candidate repair-guideline mining | Independent replay or correctness because database snapshots and raw environment transitions are absent |
| PT-BR distilled trajectories | 7,442 multilingual tool conversations with schema lookup, execution, clarification, and unanswerable cases | Natural behavior, independent correctness, or English enterprise transfer |
| [Analyst Buddy](https://huggingface.co/datasets/hjerpe/analyst-buddy-traces) | Six paired base/fine-tuned traces with DESCRIBE, SAMPLE, QUERY, and ANSWER; useful qualitative recovery examples | Statistics, cross-schema transfer, or causal attribution to fine-tuning |
| Defog SQL-Eval | Reproducible PostgreSQL questions, gold SQL, and databases for governed causal replay | Natural trajectories or enterprise prevalence |
| [Spider 2.0](https://github.com/xlang-ai/Spider2) | Enterprise-scale schemas, dialects, codebase navigation, DBT, and external documentation | A trustworthy outcome oracle without the Frankengate verifier hardening already identified |
| [BIRD-Interact](https://huggingface.co/datasets/birdsql/bird-interact-full) | 600 interactive PostgreSQL tasks with ambiguity, follow-ups, user simulation, hierarchical knowledge, and executable tests | A corpus of natural human histories; public files omit evaluator ground truth |
| [FINCH](https://huggingface.co/datasets/domyn/FINCH) | 75,725 finance SQL pairs and 33 executable SQLite databases spanning banking, insurance, funds, stocks, and accounting | Agent traces, private business knowledge, or commercial-training rights |
| StateBench finance retrieval/SQL | A governed local control with role refusal, stale-data refusal, retrieval, and SQL trace capture | A statistically adequate SQL-learning study; only four tasks are gold SQL |

The current BIRD and CRMArena structural audit is recorded in
`hf-nl2sql-trace-audit-2026-07-30.md`. It establishes that the WMH artifacts are
real ordered action/observation traces, but not complete OTLP exports. Defog is
therefore the immediate causal environment, while WMH and MAGIC are candidate
procedure sources.

## What the prior State of AI work adds

The earlier research should be adopted as constraints on the experiment, not
as an extra catalog of frameworks.

### Diagnose modules, not one SQL score

[NL2SQLBench](https://github.com/neurodb/NL2SQLBench) separates schema
selection, candidate generation, and query revision. Its reported gold-schema
ablation improves execution accuracy by roughly 15–20%, and it finds semantic
mismatch more common than syntax failure. Frankengate should preserve at least:

- tables and columns considered versus selected;
- retrieved DDL, documentation, metric definitions, example queries, and
  dialect rules;
- candidate SQL attempts and immutable execution receipts;
- revision cause and whether a correction repaired or degraded the result; and
- latency, model calls, tokens, result bytes, and database execution cost.

This decomposition is directly useful for user education. “Learn SQL” is not a
responsible suggestion; “you repeatedly select the right tables but use the
wrong grain after a one-to-many join” is.

### Enterprise SQL is grounded in private business knowledge

[EntSQL](https://arxiv.org/abs/2606.03363) contains 1,066 bilingual examples
based on enterprise BI logs and tests SQL grounded in internal metric
definitions, fiscal conventions, organization mappings, and reporting rules.
The best reported English system reaches 15.9% with the long-form documents.
This is the strongest argument for mining authorized enterprise traces and
memory artifacts: schema text alone cannot reveal proprietary business
semantics.

Frankengate must therefore distinguish:

- technical SQL procedure memories, which may transfer broadly;
- database-family schema knowledge, which may transfer within an authorized
  team;
- business definitions and metric policies, which require provenance,
  validity intervals, and classification-aware access; and
- user-specific preferences, which should remain private unless deliberately
  promoted.

### Public gold data needs adversarial audit

The [CIDR 2026 benchmark audit](https://www.cidrdb.org/cidr2026/papers/p5-jin.pdf)
reports annotation error rates above 50% in BIRD and Spider 2.0-Snow and shows
that corrections can move system results and rankings materially. The current
Frankengate Spider2 audit independently found invalid or non-reflexive
comparators, missing gold, ignored timeouts, row-destroying comparison, and
double execution.

Consequently:

- no public benchmark label is a release oracle by itself;
- candidate and gold execution must use separate capabilities and identities;
- distinguishing rows must make wrong joins and filters observably wrong;
- equivalent SQL should be compared by typed result semantics, not string
  equality; and
- disputed or invalid tasks must be adjudicated before a model run.

### Correctness, materiality, authorization, and cost are separate

The State of AI finance work and Text-to-Big-SQL analysis show that a wrong join
or missing predicate is more consequential than an extra display column, and
that retrying a warehouse-scale query can dominate model cost. Frankengate
should report:

- semantic result correctness;
- clause-level materiality of the error;
- authorization and classification compliance;
- execution bytes, rows, time, and estimated warehouse cost;
- attempts until valid answer or abstention; and
- expected cost per valid governed answer.

FINCH is useful as a finance-domain screen, but its public pairs are not traces.
It should generate new governed trajectories and test materiality-aware scoring,
not seed a claim about real users.

## Skill graph to infer from traces

The first taxonomy should remain explicit and auditable:

| Skill family | Observable evidence | Candidate intervention |
| --- | --- | --- |
| Intent and ambiguity | clarification request, changed question, premature execution, over-questioning | ask one targeted question before execution |
| Schema discovery | table/column recall and precision, DDL calls, sample-data calls, unused retrieved context | schema-navigation checklist or authorized similar example |
| Grain and joins | fan-out, duplicate rows, missing relationship, incorrect join key | verify grain and relationship cardinality before aggregation |
| Business semantics | wrong metric, fiscal period, status definition, organizational mapping | retrieve cited, time-valid business definition |
| Filters and time | omitted entitlement/status/as-of/restatement predicate | policy-aware filter checklist |
| Aggregation and numerical logic | wrong denominator, grouping, null handling, unit/currency mismatch | domain formula and validation example |
| Dialect and platform | invalid function, quoting, nested type, warehouse-specific construct | dialect-specific procedure |
| Revision and recovery | repeated identical query, error-to-correct, correct-to-incorrect, loop, exhausted attempts | failure-specific repair rule |
| Safety and governance | forbidden table/column use, cross-scope retrieval, write attempt, missing authority | deny, explain, or route to approval |
| Cost and efficiency | excessive schema calls, broad scans, bytes, latency, repeated execution | cost gate, query plan, narrower projection/filter |
| Verification and communication | no result check, unsupported explanation, missing provenance | verify invariants and cite source/definition |

These labels are hypotheses derived from deterministic trace evidence. An LLM or
AgentRx-style diagnosis may propose a label and decisive step, but cannot be the
sole ground truth.

## Enterprise questions this domain can answer

### Individual

- Which failure families recur for this user after controlling for database
  difficulty?
- Does the user recover after schema or execution feedback, or repeat the same
  action?
- Which targeted procedure reduces attempts, unsafe proposals, and time without
  increasing over-questioning?
- Which business definitions has the user learned or repeatedly needs to
  retrieve?
- Is a suggested skill still beneficial on a later, untouched task family?

### Team

- Which users perform similar authorized SQL work and have complementary
  strengths?
- Which successful procedure transfers across team members without transferring
  query text or classified results?
- Which schema or metric definitions cause repeated friction across the team?
- Where should a semantic-layer owner fix documentation instead of teaching
  every user a workaround?
- Which tasks should become regression evals because multiple people encounter
  the same failure?

### Enterprise

- Which task and skill families consume the most retries, latency, and database
  cost?
- Which business rules are undocumented, contradictory, stale, or only known
  through repeated human correction?
- Where does a model, prompt, retrieval policy, semantic layer, or employee
  skill explain more variance than task difficulty?
- Which successful procedures are safe to promote as enterprise skills, and
  which remain team- or user-scoped?
- Which recurring workflows provide sufficiently clean, consented examples for
  future retrieval-model or embedding adaptation?

Aggregate answers require a minimum cohort, suppression of unique identifiers,
classification-compatible grouping, and evidence links that resolve only for a
viewer authorized to see the underlying trace.

## Smallest falsifiable experiment

The existing Defog preregistration remains the harness qualification gate. Its
P0 failed the terminal-protocol gate, so P1 and hidden stages remain sealed.
After arm-independent protocol remediation and a new passing P0, use this
sequence:

### Phase A: label reliability

1. Sample held-out WMH BIRD trajectories stratified by database family and
   outcome.
2. Run cheap deterministic signals over every trace: repeated query, no schema
   inspection, excessive schema calls, parse/database error, loop, no terminal
   submission, repair, and degradation.
3. Blindly double-label decisive failure steps using the modular taxonomy.
4. Measure inter-rater agreement and the precision/recall of deterministic and
   AgentRx-style diagnoses.

Stop if the decisive failure family cannot be labeled reliably.

### Phase B: candidate procedure mining

Mine the first candidate only from:

- successful versus failed WMH BIRD traces on evidence-only database families.

Candidate artifacts may contain only generalized procedures. They may not
contain task text, schema identifiers, SQL literals, gold results, trace IDs, or
hidden-family information. Keep MAGIC, PT-BR, and pooled multi-source extraction
out of the first causal test. They become incremental ablations only if a
BIRD-mined artifact demonstrates value.

### Phase C: causal replay

Use the existing family-disjoint Defog design. The minimum credible arms are:

1. no artifact;
2. unrelated formatting placebo;
3. one frozen, reviewed WMH BIRD contrast-mined procedure.

Keep model, prompt wrapper, tools, limits, authority, database snapshot, and
decoding fixed. Select candidates only on visible families. Evaluate once on
an untouched database family after signed gate approval.

Primary outcome:

`semantic_correct AND policy_accepted AND NOT unauthorized_observation`

Report paired task effects, protocol failures, repair/degradation, attempts,
clarifications, tokens, latency, database time, result bytes, unsafe proposals,
and expected cost per valid governed answer.

Stop if the mined arm does not beat both no-artifact and placebo, if any
security violation occurs, or if gains disappear on the held-out family.

Only after that pass should a second preregistered study compare the winning
BIRD procedure with MAGIC repair mining, an expert modular seed, or a combined
Signals plus failure-localization method. This sequencing keeps the initial
claim attributable and avoids an expensive factorial before the core premise
has evidence.

### Phase D: interactive friction

Only after static causal value is shown, generate new governed traces on
BIRD-Interact. Test whether clarification guidance reduces premature execution
without causing excessive questions. Its simulator provides controlled
ambiguity, but results may support benchmark transfer only—not natural employee
prevalence.

### Phase E: enterprise and finance external validity

Curate:

- the already audited Spider2 cohort for large schemas, dialects, DBT, and
  documentation navigation;
- EntSQL-style internal tasks in which SQL depends on versioned proprietary
  definitions;
- FINCH tasks for finance clauses and materiality-aware scoring; and
- StateBench refusal and stale-data controls.

Keep database/schema families disjoint across evidence, selection, and test.
Never mix an employee's historical trace into both the procedure source and
their outcome evaluation.

## Storage and retrieval requirements

PostgreSQL JSONB should hold canonical tool payloads, normalized error details,
query-plan summaries, classification labels, and source-specific fields.
Relational columns should hold tenant/user/team, authority epoch, timestamps,
task/session/trace/span IDs, database family, outcome, skill label, and cost
metrics. Full SQL, database results, and classified business definitions remain
protected content with RLS and classification predicates.

Start retrieval with:

1. exact identifiers and lexical search for table, column, metric, error, and
   dialect terms;
2. structured filters for tenant, user/team, task family, time, authority, and
   classification;
3. deterministic trajectory features and failure labels; and
4. embeddings only for residual paraphrase or procedure similarity.

A custom embedding model is not a prerequisite. It becomes justified only if a
frozen labeled retrieval set shows that exact, structured, and current generic
embedding retrieval miss valuable authorized peers. Fine-tuning then uses
consented query/procedure positives, hard negatives from semantically similar
but wrong business definitions, and database-family-disjoint evaluation.

## Product behavior

For a user, Frankengate should show:

- a private prompt and trace history;
- repeated friction patterns with evidence from their own authorized traces;
- one specific suggested eval or procedure;
- an explanation of why it was suggested and what evidence was used;
- an interactive path to edit, approve, scope, and test it; and
- measured before/after outcomes.

Team or enterprise suggestions should expose aggregate pattern descriptions and
approved reusable procedures, not another person's raw prompts, SQL, results, or
identity. A user can be told that “an approved team procedure reduced incorrect
one-to-many joins on similar tasks,” while the source trace remains protected.

## Immediate backlog

1. Remediate the Defog terminal protocol and rerun P0 under new hashes.
2. Build the WMH BIRD deterministic-signal and blinded-label reliability set.
3. Implement generalized-procedure extraction for WMH and MAGIC with a
   canary-based content-leakage test.
4. Add BIRD-Interact and FINCH acquisition adapters; keep both inventory-only
   until hashes, rights, and evaluator boundaries are verified.
5. Curate EntSQL-style internal tasks with versioned business definitions and
   classification labels; the public benchmark is external-validity evidence,
   not a source of enterprise-private semantics.
6. Run the family-disjoint factorial only after the capability and protocol
   gates close.
7. Add the user-facing “suggested eval” flow only after one candidate
   intervention demonstrates held-out causal value.
