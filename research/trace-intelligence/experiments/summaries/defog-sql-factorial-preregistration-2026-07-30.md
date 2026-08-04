# Governed Defog SQL factorial preregistration

## Question

Can a frozen, generic SQL procedure change an agent's governed task outcomes,
beyond the effect of adding similarly structured but semantically irrelevant
prompt text? This first factorial deliberately does **not** test a trace-mined
skill. It qualifies the native-tool harness and tests intervention sensitivity
before BIRD/MAGIC evidence is allowed to generate an artifact.

The frozen machine-readable contract is
`experiments/manifests/defog-sql-factorial-design-2026-07-30.json`. It contains
no benchmark questions, SQL, instructions, results, or outcome labels.

## Design

The 96-task Defog cohort has four PostgreSQL database families with 24 tasks
each. Two tasks requiring sensitive-field entitlement and one invalid upstream
PostgreSQL task are adjudicated before model execution and excluded from the
primary quality denominator. The primary denominator is 93 tasks.

| Fold | Evidence only | Visible selection | Hidden test | Eligible evidence / selection / test |
| --- | --- | --- | --- | ---: |
| F0 | dermatology + e-wallet | car dealership | broker | 46 / 23 / 24 |
| F1 | broker + e-wallet | dermatology | car dealership | 46 / 24 / 23 |
| F2 | broker + car dealership | e-wallet | dermatology | 47 / 22 / 24 |
| F3 | car dealership + dermatology | broker | e-wallet | 47 / 24 / 22 |

Every family is hidden once, selected on once, and evidence twice. Each fold
requires a fresh artifact namespace, stateless proposer, solver conversation,
memory, retrieval index, and cache. Selection may choose among frozen
candidates but may not rewrite them. All fold artifacts must be signed before
hidden results are opened.

The solver and any future artifact proposer have no source-checkout, evaluator,
gold, hidden-manifest, shell, filesystem, network, memory, cache, or
cross-episode access. The evaluator alone resolves gold and adjudication
metadata. Public-source pretraining contamination remains possible and is a
reported limitation.

## Arms

All arms share the exact base prompt, task input, tools, decoding, model,
database snapshot, authority, and stopping limits. Only the bytes inside the
frozen `<procedure_artifact>` differ:

- `no_skill`: an empty artifact block.
- `unrelated_formatting_placebo`: six SQL presentation rules that add no
  schema, metric, relationship, filter, or business semantics.
- `expert_schema_navigation_seed`: six generic rules about grain, schema
  inspection, joins, projection, filters, aggregation, execution, and repair.

The expert seed is authored expert guidance, not trace learning. Artifact bytes
and SHA-256 receipts are in the design manifest and imported from
`defog_sql_factorial_contract.py` by both generator and runner.

## Tool protocol

The native-tool loop exposes only:

1. `describe_schema`, returning authorized schema metadata;
2. `execute_sql`, returning an opaque attempt ID and bounded evidence;
3. `submit_sql(attempt_id)`, selecting an already executed attempt without
   executing it again; and
4. `abstain(reason_code)`, terminating without SQL.

There is no implicit last-query submission. A text answer without one terminal
tool is a protocol failure. The model never receives semantic correctness,
gold output, or verifier feedback.

Limits are two schema calls, three SQL attempts, six model turns, 4,096
generated tokens per episode, 60 seconds model wall time, five seconds per
statement, 500 ms lock timeout, and five seconds idle-transaction timeout.
Model-facing result evidence is capped at 50 rows and 32 KiB; evaluator
evidence is capped at 10,000 rows and 8 MiB.

## Governance contract

Every episode must resolve an exact current authority binding over database,
governance scope, user, team, and virtual key. Merely supplying an epoch string
is insufficient. Missing, stale, unknown, or cross-subject epochs fail closed.
The local pinned authority snapshot is a reproducibility mechanism; it is not a
cryptographically signed production authority service and proves nothing about
distributed revocation or Aurora behavior.

Sensitive-column authorization applies to use, not only projection: predicates,
joins, grouping, `HAVING`, ordering, windows, functions, and correlated
subqueries must all be checked. Semantic correctness, authority validity,
policy acceptance, execution completion, and unauthorized observation are
separate result axes.

## Stages and stopping

### P0: mechanics smoke

Four stratified F0 selection tasks—one general, one basic, and two advanced—are
crossed with all three arms for 12 episodes. A one-task subset may be used only
to check transport and database wiring. P0 tests receipts, native tools,
terminal submission, arm scheduling, authority, policy, and offline
evaluation. It cannot estimate a procedure effect.

Any harness change invalidates P0 and requires a rerun under the final hashes.

### P1: visible effect screen

Run all 23 eligible F0 car-dealership tasks under all three arms: 69 paired
episodes. Six hash-selected sentinel tasks receive two additional repeats per
arm to estimate runtime nondeterminism; repeats are never independent units.

The frozen gate requires:

- complete task/arm receipts under an arm-blind infrastructure rerun rule;
- zero unauthorized observations;
- no arm above 10% protocol failures; and
- at least two more expert-only than placebo-only joint passes.

If the gate fails, publish the null/mechanics result and do not unseal hidden
tests. If it passes, run the untouched 24-task broker hidden family under all
three arms and publish the result regardless of sign.

### Confirmatory study

Repeat all four isolated rotations. This produces one out-of-fold hidden
prediction for each of 93 eligible tasks. If sentinel nondeterminism exceeds
5%, preregister three common seeds per task-arm and keep task—not seed—as the
independent unit.

## Outcomes

The primary endpoint is:

`semantic_correct AND policy_accepted AND NOT unauthorized_observation`

The primary contrast is expert seed versus formatting placebo. Report paired
risk difference with a task-bootstrap 95% interval, exact two-sided McNemar
test, and expert-only/placebo-only/both/neither counts. Secondary contrasts
against no-skill use Holm adjustment. The analysis is intention-to-treat:
abstentions, protocol failures, and wrong submissions stay in the denominator.

Secondary outcomes include first and final correctness, repair/degradation,
schema and SQL calls, repeated queries, loops, parse/policy/database errors,
tokens, latency, execution time, result bytes, unsafe proposals, denial codes,
and deterministic failure categories. LLM or AgentRx diagnoses are candidate
annotations, not authoritative root-cause labels.

## Claim boundaries

P0 may show only that the frozen harness exercised native tools and security
controls. P1 may show an arm effect on one visible database family. A gated F0
hidden run may support transfer for this exact model/runtime/tool/policy on one
untouched database family. Four-fold completion may support an out-of-fold
paired effect across these 93 tasks.

None of these stages alone establishes natural enterprise prevalence, a human
skill deficit, employee educational benefit, long-term memory benefit, custom
embedding value, production RLS safety, Aurora performance, or general NL2SQL
superiority.

## P0 disposition

P0 subsequently completed all 12 episodes under the final cache-disabled
runtime. Every arm achieved 2/4 semantic and strict-shape passes, with zero
paired pass discordances and zero unauthorized observations. Terminal-protocol
failure was 25% for no-skill, 50% for placebo, and 25% for the expert seed.
The preregistered protocol and paired-win gates therefore failed. P1 and hidden
testing remain sealed pending an arm-independent protocol remediation and a
new complete P0 under new hashes. See
`defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md`.
