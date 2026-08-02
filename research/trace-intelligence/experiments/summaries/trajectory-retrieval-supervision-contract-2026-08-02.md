# Exposure-aware trajectory retrieval supervision contract

## Purpose

This contract turns the Cursor-style historical-retrieval method into a
machine-checkable Frankengate study arm. It is a study-design artifact, not a
claim that public traces already contain the required labels.

The central rule is **exposure is not relevance**:

- a candidate not shown to the agent is missing data, not a negative;
- an exposed candidate that was skipped needs a typed reason;
- same-surface/wrong-system, temporal replacement, stale authority, and
  result-preserving alternatives are separate strata;
- model-generated relevance is silver until replay, human adjudication, or a
  prospective outcome validates it.

## Required protocol

Each episode freezes its candidate set before any model or human labels are
collected. The manifest records principal/team/project/system/time holdouts,
source and changed environments, authority epochs, complete tool-result edges,
exposure completeness, candidate-pool hashes, deletion/retention receipts, and
two independent labels. The required arms are:

1. structured scope and authority;
2. lexical/identifier retrieval;
3. frozen dense retrieval;
4. trajectory-distilled ranker;
5. selective frontier review; and
6. frontier regeneration when no compatible artifact is present.

Promotion requires at least 100 target episodes, 50 hard negatives, and 25
NIL/unclear episodes, with project, system, principal, team, and effective-time
holdouts. These thresholds are deliberately larger than the public probes so a
small silver sample cannot become a model or artifact release.

## Validator evidence

The contract and validator are:

- [`trajectory-retrieval-supervision-v1.json`](../../configs/studies/trajectory-retrieval-supervision-v1.json)
- [`trajectory_retrieval_supervision_validator.rb`](../../trajectory_retrieval_supervision_validator.rb)

The valid example is structurally accepted but promotion-blocked because it has
only one target and no negative/NIL cohort. The invalid example fails closed on
candidate-pool freezing, incomplete exposure logging, missing holdouts, missing
arms, and missing episodes. Receipts:

- [`valid example result`](../results/trajectory-retrieval-supervision-contract-valid-2026-08-02.json)
- [`invalid example result`](../results/trajectory-retrieval-supervision-contract-invalid-2026-08-02.json)

This distinction is important: **structural validity is not promotion
readiness**.

## Metrics

Report Recall@1/5/20, MRR, candidate-pool recall, wrong-system-before-target,
NIL/refusal precision, exposure-conditioned precision, replay success on source
and changed systems, stale/unsafe acceptance, correction burden, latency, and
frontier cost. Also report model/human disagreement and the fraction of
episodes with no compatible artifact, so a retrieval failure is not confused
with a library-coverage failure.

## Claim boundary

This contract makes the next experiment reproducible; it does not supply the
enterprise cohort. The public BIRD traces lack complete candidate exposure
sets, stable principals, authority labels, and natural repeated work, so they
cannot be used to claim a Cursor-equivalent retriever or enterprise skill
learning without an additional exposure reconstruction and independent replay
study.
