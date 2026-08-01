# DataClaw cross-user task-equivalence adjudication pilot (2026-08-04)

This pilot sampled eight candidate pairs across two MIT-licensed DataClaw
exports. A frontier Luna call independently labeled each pair twice as
`same_task`, `related_task`, `different`, or `unclear`, using only the first
three user prompts and tool categories. Session identifiers were hashed and
model rationales were intentionally omitted from the receipt.

All 16 calls returned schema-valid labels. Seven of eight pairs had repeat
agreement. The lexical candidate generator deliberately included both high
overlap and near-negative pairs. Luna labeled the high-overlap pairs mostly
`different` or `unclear`, showing that shared vocabulary/tool names are not
enough to establish task equivalence.

This is a silver-label calibration probe, not ground truth: it has no
independent task labels, outcome labels, identity claim, or user-skill claim.
It therefore does not establish cross-user retrieval quality or justify
sharing an artifact. The next gate is a larger principal/project/time-held-out
set with blinded human or SME labels, explicit same-task/related/NIL classes,
and changed-system replay outcomes.

Receipt: [`dataclaw-cross-user-luna-adjudication-2026-08-04.json`](../results/dataclaw-cross-user-luna-adjudication-2026-08-04.json)

Verifier: [`verify_dataclaw_cross_user_luna_adjudication.py`](../../verify_dataclaw_cross_user_luna_adjudication.py)
