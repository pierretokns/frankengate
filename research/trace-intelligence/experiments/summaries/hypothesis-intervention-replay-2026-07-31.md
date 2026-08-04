# Hypothesis intervention replay checkpoint (2026-07-31)

The first controlled intervention replay used a deterministic sealed fixture
with family-disjoint training (`alpha`) and holdout (`beta`) tasks. Each arm
reset a stateful system before every one of the three holdout tasks (three
resets per arm). The evidence-derived policy reached 2/3 holdout successes
(0.667), while no proposal and an unrelated placebo reached 0/3.

This is protocol evidence only. The task world is synthetic, the procedure is
hand-defined, there is no human adjudication, and no real trace outcome is
measured. It demonstrates that the harness can separate an evidence policy
from a placebo under a family-disjoint split; it is not evidence that trace
mining improves enterprise work. The next gate must replace the hand-defined
world with a resettable changed system and independently adjudicated outcomes.
