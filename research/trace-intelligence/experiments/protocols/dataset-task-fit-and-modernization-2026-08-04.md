# Dataset-task fit and modernized reimplementation protocol

**Protocol ID:** `dataset-task-fit-modernization-v1`
**Status:** required gate for new empirical claims

## Core rule

An experiment may support only claims whose required observations exist in the
dataset. A dataset with questions and gold SQL can test schema grounding and
execution; it cannot, by itself, test user friction, skill transfer, or
cross-user collaboration. A trajectory without a task outcome can test
structural detectors; it cannot establish that a mined skill improved work.

Every receipt must record:

- the exact task claim and the observation required to score it;
- dataset ID, revision, license, provenance, and schema hash;
- whether rows contain users, sessions, tool calls, environment state,
  intermediate failures, corrections, outcomes, and time;
- train/validation/test boundaries by user, team, project, task family, and
  time as applicable;
- source/target overlap, synthetic fields, silver labels, and any proxy
  authority;
- the strongest claim allowed by the dataset and the claims explicitly out of
  scope.

## Current fit map

| Dataset family | Good evidence for | Not evidence for |
|---|---|---|
| Defog/NL2SQL and similar gold-SQL corpora | Identifier/scope retrieval, schema/table/column hard negatives, SQL semantic execution, validated-artifact replay, abstention on constructed NILs | User friction, agent tool trajectories, skill transfer, cross-user similarity, enterprise aliases, changed-system utility |
| BIRD/Spider/FinanceBench-style benchmarks | Schema generalization, SQL execution, domain retrieval, family-held-out adapter tests | Longitudinal user behavior, correction chains, memory consolidation, human outcomes |
| Wisp/Claude/Codex histories | Prompt correction signals, tool/trajectory structure, term candidates, procedure/eval proposal mechanics | Enterprise truth, causal skill improvement, multi-user collaboration, reliable intent labels; current Wisp slice is single-contributor |
| Agent trajectory datasets (SWE/Browser/OS/MCP) | Replay, tool-call ordering, failure localization, trajectory-level evals, skill/tool reuse | Corporate vocabulary, real user capability gaps, team-level outcomes unless identities and outcomes are present |
| Synthetic fixtures | Contract mechanics, NIL/ambiguity behavior, authorization invariants, metamorphic tests | Real-world prevalence, enterprise relevance, causal utility, model quality at production scale |

The prior NL2SQL results remain valid only under the first two rows. They must
not be cited as evidence for the broader enterprise trace questions.

## Modernization rule

Old software is treated as a source of a concept, not as a production
dependency or a definitive result. For each older system, create two receipts:

1. **Concept receipt:** the method, inputs, outputs, assumptions, and original
   evaluation protocol, with its known limitations.
2. **Modern implementation receipt:** a clean implementation on the current
   Python/Go/retrieval stack, pinned dependencies, deterministic seed, and a
   comparison against a current baseline on the fit-for-purpose dataset.

Do not call a concept disproven when the original code cannot run. Record
legacy setup blockers separately, as done for TermSuite and AcronymExpansion.
Do not call a modern reimplementation validated merely because it reproduces a
toy fixture; it still needs the correct dataset and sealed holdout.

## Required controls by research question

- **Term/alias mining:** contextual traces containing known terms, reviewed
  span/alias/NIL labels, same-surface/different-system negatives, and temporal
  replacement cases. Measure boundary precision, cluster purity, wrong-system
  rate, and retrieval lift.
- **Friction and eval mining:** complete sessions with prompts, corrections,
  tool calls, failures, terminal outcome, and independent human or verified
  task labels. Hold out users and time; do not infer skill gaps from retries
  alone.
- **Skill improvement:** replayable tasks with a changed environment and
  outcomes, no-skill/neutral/placebo/mined/teacher arms, multiple seeds, and
  family/user/time holdouts. Measure success, cost, latency, and negative
  transfer.
- **Cross-user similarity:** consent-stable user/team identity, task-family
  labels or adjudication, minimum cohort size, and authorization-aware
  clustering. A public single-user corpus cannot answer this question.
- **Embedding adaptation:** hard negatives and aliases from the target domain,
  entity/time/project holdouts, frozen baseline, and an absolute downstream
  utility gate. Retrieval metrics alone are insufficient.

## Dataset admission gate

Before running a model or tool, the dataset manifest must pass `fit_for_claim`:

```text
required_observations ⊆ observed_fields
and split_policy covers every claimed generalization axis
and authority_level is explicit for every label
and overlap_audit == passed
```

If the gate fails, the run may be retained as a mechanics or feasibility
probe, but its receipt must set `claim_level` to `mechanics_only` or
`proxy_only` and list the missing observations. This prevents an NL2SQL result
from being promoted into an enterprise trace-learning claim.
