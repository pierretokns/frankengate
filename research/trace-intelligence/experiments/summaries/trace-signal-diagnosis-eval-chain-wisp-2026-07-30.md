# Signals → diagnosis → eval-promotion Wisp experiment

**Run date:** 2026-07-30

**Result SHA-256:** `dd984adde9af67ff644c61f7ea46425dc0704d746166bb356f6ad4d84353f1f2`

## Claim boundary

This is a dependency-light, concept-inspired experiment. It is not a
replication or execution of the Signals paper, AgentRx, or AgentEvals.

The final replay section is deterministic assertion mutation testing, **not
changed-system replay**. There were zero actual changed-system executions and
zero upstream AgentEvals runs.

## Full-fidelity internal corpus

The experiment inspected the complete authorized local Wisp content in memory.
The credential-only capture gate transformed five DSN passwords while
preserving names, email addresses, paths, prompts, source code, tool arguments,
tool results, and other ordinary internal content. No trace content, path,
identifier, fingerprint, or per-trace result is committed.

- Files / source records: 104 / 10,700
- Canonical analysis events: 5,742
- Malformed records excluded from content analysis: 2
- Credential transformations: 5

## Chain result

The label-blind selector found 11 signal-positive traces within a 21-trace
budget. It did not use trace length for ranking. Across the whole corpus it
observed:

- 103 exporter-typed tool errors;
- 16 repeated normalized user requests;
- seven repeated failure signatures;
- seven repeated tool-action signatures; and
- two dangling tool proposals.

The deterministic invariant pass produced 11 contestable hypotheses and zero
root-cause claims:

- nine explicit tool failures;
- one repeated tool failure; and
- one orphan tool result whose source evidence could not support a safe generic
  regression assertion.

Ten diagnoses promoted into distinct stored-trace audit and prospective replay
assertion specifications. All ten stored audits passed their source trace. All
ten failed after the decisive evidence was removed, while appending an
irrelevant allowed event caused zero false positives.

The prospective assertion lane behaved as intended on mutations: all ten
unchanged traces retained the failure and failed; all ten failure-removed
mutants passed; and all ten irrelevant-tail mutants still failed. These are
mechanical mutation controls, not changed-agent outcomes.

## Interpretation

This chain is worth carrying forward. It demonstrates that Frankengate can run
cheap full-content selectors, attach evidence to constrained diagnostic
hypotheses, and turn supported hypotheses into separate audit and prospective
replay specifications without sending PII to a third party.

It does not establish diagnostic accuracy, task recovery, causal benefit,
future-system behavior, skill gaps, employee productivity, or collaboration
fit. The next experiment must execute these ten prospective assertions against
baseline and changed agents in a resettable environment with an independent
outcome verifier.

