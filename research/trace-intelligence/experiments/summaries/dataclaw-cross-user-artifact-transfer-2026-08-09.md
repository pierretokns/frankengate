# DataClaw cross-user artifact transfer

## Question

Does broad cross-user tool overlap imply that the same reusable artifact can be
transferred between real-user trace collections?

## Protocol

The Peter (549 sessions) and Vaynelee (38 sessions) MIT-licensed DataClaw
exports were mined with the existing content-free candidate miner. A strict
artifact identity is the hash of a non-trivial normalized tool plus its
normalized input; generic shell/status calls and management tools are excluded.
The miner was run without a candidate cap. Only hashes, counts, and source
hashes are committed.

## Result

Peter produced 34,036 strict candidate identities and Vaynelee produced 971.
There were **zero shared strict identities** across the two users (union
35,007; Jaccard `0.0`). Peter had 518 candidates spanning multiple projects;
Vaynelee had 4. The strict result is much narrower than the earlier broad audit,
which found 11 shared non-trivial tool-call forms after a more permissive
normalization.

This means tool-name or loose-form overlap is not sufficient evidence for
cross-user artifact reuse. The useful cross-user pipeline is: broad overlap for
candidate recall, strict identity and scope filtering, then human/SME intent
review and independent replay. Automatic cross-user promotion is not justified
by these public traces.

## Claim boundary

The study does not establish shared task intent, correctness, authority
compatibility, user benefit, or negative transfer. DataClaw lacks independent
terminal outcomes and stable enterprise identity semantics; strict non-overlap
may also reflect parameter/path variation rather than different work.

Receipts:

- [content-free result](../results/dataclaw-cross-user-artifact-transfer-2026-08-09.json)
- [independent verification](../results/dataclaw-cross-user-artifact-transfer-verification-2026-08-09.json)
- [`dataclaw_cross_user_artifact_transfer.py`](../../dataclaw_cross_user_artifact_transfer.py)
