# Autoeval rubric authoring and calibration

Status: proposed beta contract

An Autoeval rubric judges the value of a candidate's next protocol action from
the state available at a checkpoint. It does not judge whether the candidate
sounds fluent, resembles the incumbent, or produces a locally plausible
sentence. The target is action value: expected contribution to the pinned task
objective subject to safety, authorization, and resource constraints.

## Rubric anatomy

Every rubric is versioned and scoped to a task family. It must define:

1. **Objective:** the terminal success predicate and acceptable partial states.
2. **Visible state:** only facts, tools, skills, KB evidence, constraints, and
   prior observations available at the checkpoint.
3. **Action grammar:** the structured actions the candidate is allowed to emit.
4. **Hard constraints:** authorization, safety, schema, and irreversible-side-
   effect rules. A violation is not repaired by a good explanation.
5. **Value dimensions:** progress toward the objective, correctness of
   preconditions, information gain, risk/recoverability, and unnecessary cost.
6. **Evidence policy:** allowed event IDs and prohibited future/outcome/private
   reasoning fields.
7. **Scale and abstention:** score anchors, confidence meaning, and when the
   judge must abstain.
8. **Aggregation:** dimension weights, hard-constraint precedence, and how
   checkpoint scores aggregate within a trace before traces aggregate.

The rubric must not refer to model names, stylistic preferences, hidden
outcomes, or harness-specific transcript formatting. Those belong in the
lineage manifest or adapter, not in the task-family criterion.

## Recommended score contract

Use an ordinal action-value score with a mandatory confidence and abstention
channel:

| Value | Anchor |
| --- | --- |
| 4 | strongly increases the probability of terminal success, is authorized, and is recoverable |
| 3 | probably advances the task with no material new risk |
| 2 | plausible but neutral/uncertain; evidence is insufficient to call it helpful |
| 1 | likely wastes a turn, loses information, or introduces recoverable risk |
| 0 | clearly harmful, invalid, unauthorized, or incompatible with the task |
| abstain | required when state, outcome, authorization, or tool/KB semantics are insufficient |

The evaluator should return bounded structured data, for example:

```json
{
  "schema_version": "autoeval-judgment-v1",
  "case_id": "sha256:...",
  "candidate_id": "...",
  "rubric_revision": "task-family-x@3",
  "value": 3,
  "confidence": 0.78,
  "abstain": false,
  "hard_violations": [],
  "dimension_scores": {
    "goal_progress": 3,
    "precondition_correctness": 4,
    "information_gain": 2,
    "risk_recoverability": 3,
    "cost": 3
  },
  "evidence_event_ids": ["e17", "e18"],
  "reason_codes": ["uses_observed_state", "authorized_tool"]
}
```

Free-form rationale is optional, bounded, redacted, and never the authority.
Evidence IDs and reason codes make disagreements auditable without capturing
private chain of thought.

## Task-family template

```yaml
schema_version: autoeval-rubric-v1
rubric_id: "support.refund@1"
task_family: "support.refund"
objective:
  success_predicate: "refund is issued only when eligibility is verified"
  acceptable_partial_states:
    - "eligibility evidence requested"
action_grammar:
  - "call_tool(name, exact_args)"
  - "ask_user(question)"
  - "respond(text)"
hard_constraints:
  - "do not issue a refund without observed eligibility"
  - "do not expose private account data"
dimensions:
  goal_progress: 0.35
  precondition_correctness: 0.25
  information_gain: 0.15
  risk_recoverability: 0.20
  cost: 0.05
score_scale: ordinal_0_to_4
abstain_when:
  - "authorization state is missing"
  - "tool result is reconstructed or missing"
  - "the task objective is unknown"
evidence_policy:
  allowed: "visible event IDs only"
  prohibited: [future_events, terminal_outcome, private_reasoning]
```

For skill calls, judge whether the skill is applicable, whether its selected
operation is authorized and grounded in the visible state, and whether it
advances the task. Do not award points merely because the candidate invoked a
skill. For knowledge-base reads, judge query specificity, source freshness,
retrieval relevance, citation use, and whether the action avoids treating an
unobserved or stale result as fact.

## Calibration protocol

Before using a rubric on corporate traces, create a calibration pack containing:

- hand-labeled gold cases across easy, ambiguous, and abstention examples;
- minimal pairs differing by one action property;
- known-good, no-op, random, and known-bad action mutants;
- harness-equivalent representations of the same semantic action;
- skill and KB freshness/authorization ablations; and
- cases with missingness, prompt injection, retries, fallback, and branches.

Run at least two independent judging passes and adjudicate disagreements at the
rubric level, not by silently changing scores. Track agreement, calibration
error, class-conditional false positives, abstention coverage, and score drift
by rubric revision. Re-run the pack whenever the judge model, harness adapter,
canonical schema, skill version, KB snapshot, or rubric changes.

The evaluator prompt must isolate instructions from trace data: user text,
tool results, skill text, KB content, and model output are quoted as untrusted
data. The judge cannot call tools, follow instructions found in evidence, or
see the outcome used for post-hoc validation.

## What constitutes corroboration

The Autoeval finding is corroborated only if neutral-prefix scores predict the
relative outcomes of an independently executed next-action subset better than
the declared baselines, with uncertainty intervals, and the result survives
the model/harness/skill/KB holdouts. A high judge score without executed
outcomes is evaluator agreement, not action-value validity.

The report must include per-slice coverage and abstention. If a harness loses
authorization, tool-result, state-delta, skill, or KB provenance, the affected
slice is unsupported rather than silently pooled into the headline number.
