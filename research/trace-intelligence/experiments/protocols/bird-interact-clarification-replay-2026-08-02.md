# BIRD-Interact clarification replay protocol

**Status:** protocol-only; evaluator/test bundle required before causal claims
**Dataset pin:** `birdsql/bird-interact-full`, 600 tasks, 22 database domains

## Question

Does a trace-mined clarification procedure improve execution and reduce repair
burden on ambiguous NL2SQL tasks, or does it merely add turns and cost? The
experiment is separate from the terminology, embedding, and artifact-reuse
lanes. A clarification decision is not evidence that an alias or SQL artifact
is correct.

## Cohort and split

Use the pinned 600-task file as the sampling frame. Stratify by:

1. ambiguity family: knowledge-linking, intent, semantic, schema-linking,
   lexical, syntactic;
2. follow-up type: result-based, aggregation, attribute-change, topic-pivot,
   constraint-change; and
3. database domain.

Create a deterministic task-disjoint split: 60% development, 20% calibration,
and 20% held-out evaluation. No schema, database, or task text from the held-
out fold may be used to write the procedure or tune a threshold. If domain
counts are too small, report domain-held-out and task-held-out results
separately rather than pooling them.

## Randomized arms

Run the same model, tool budget, temperature, and evaluator version in each
arm. Randomize task order and use paired seeds where the harness permits:

1. **No procedure:** the base agent receives the task and authorized tools.
2. **Clarification procedure:** before execution, classify ambiguity and ask at
   most one targeted question only when a critical ambiguity is unresolved.
3. **Over-questioning placebo:** ask one generic clarification on every task,
   including unambiguous controls. This isolates turn/cost effects.
4. **Reviewed procedure:** use a human-reviewed, frozen rule set derived only
   from the development fold.
5. **Frontier regeneration:** permit a frontier model to regenerate the next
   action, but do not expose hidden labels or evaluator outcomes.

The placebo is essential: a procedure that improves outcome only by spending
more turns must not be called a clarification or skill benefit.

## Required trace fields

Every episode must record an append-only receipt containing:

- task hash, dataset revision, domain and ambiguity strata;
- arm, seed, model/provider identity, prompt/procedure revision;
- each user-facing clarification and whether it targets a labeled critical
  ambiguity;
- every schema/tool call, SQL proposal, execution result, retry, and stop;
- terminal evaluator/test result and correction class;
- turns, tool calls, tokens, wall time, database time, and output bytes; and
- receipt hash plus evaluator version.

Do not store raw task or result content in the research repository. Keep it in
the local evaluator workspace and publish only hashes, aggregates, and
redacted examples.

## Primary outcomes

Pre-register these before running the held-out fold:

- terminal execution/test success;
- premature-execution rate on critical ambiguity tasks;
- semantic correction rate after the first execution;
- clarification precision: targeted critical clarification / all
  clarifications;
- unnecessary-question rate on non-critical or unambiguous tasks; and
- repair burden: user-simulator turns plus retries before terminal success.

Report paired differences and bootstrap 95% intervals by ambiguity family and
database domain. A positive result requires improved terminal success or lower
repair burden at a fixed or lower tool/cost budget, not merely more questions.

## Safety and interpretation gates

- Never treat the public follow-up label as a human satisfaction label.
- Do not infer employee friction, missing skills, or collaboration value from
  simulator behavior.
- Do not promote a clarification into a Frankengate skill until a second
  evaluator or human review confirms the terminal outcome.
- Keep authority, schema version, and authorization epoch checks outside the
  model; clarification cannot authorize an otherwise invalid SQL/tool action.
- If the evaluator bundle is unavailable, stop at cohort profiling and report
  the intervention as unrun—not as a null result.

## Promotion gate

Promotion requires a held-out improvement over **both** no-procedure and the
over-questioning placebo, no increase in unsafe execution, and no material
regression in tokens, latency, or correction burden. A reviewed procedure may
enter a shadow lane with rollback; a generated procedure remains proposal-only
until it passes the same gate.

This protocol complements [the public cohort profile](../summaries/bird-interact-ambiguity-profile-2026-08-06.md)
and [the broader next-experiment plan](../summaries/corporate-trace-artifact-learning-next-experiments-2026-08-06.md).
