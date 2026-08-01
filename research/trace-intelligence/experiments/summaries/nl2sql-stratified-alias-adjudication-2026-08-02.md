# Stratified alias, collision, NIL, and ambiguity adjudication

## Why this gate exists

The prior 22-case frontier adjudication contained no NIL or unclear examples.
It could measure wrong-system recognition in an easy sample, but not whether a
model abstains instead of inventing an alias. This follow-up adds the missing
negative classes.

## Protocol

The fixture contains 23 public synthetic cases:

- 6 exact aliases;
- 6 semantic aliases;
- 5 same-surface cross-database collisions;
- 4 NIL questions with no listed identifier answering the question;
- 2 ambiguous in-scope cases requiring `unclear`.

Two independently prompted `gpt-5.6-luna` roles adjudicated the same cases.
The prompt exposed only the question, stated database scope, and candidate
identifiers; construction-time labels were withheld. Raw prompts/responses
remain external. The committed result contains hashes and aggregates only.

Receipts:

- [`../results/nl2sql-stratified-alias-adjudication-luna-2026-08-02.json`](../results/nl2sql-stratified-alias-adjudication-luna-2026-08-02.json)
- [`../results/nl2sql-stratified-alias-adjudication-luna-verification-2026-08-02.json`](../results/nl2sql-stratified-alias-adjudication-luna-verification-2026-08-02.json)

## Result

Both independent arms achieved:

| Metric | Result |
| --- | ---: |
| Surface accuracy | 1.000 |
| Candidate-label accuracy | 1.000 |
| Wrong-system accuracy | 1.000 |
| NIL/unclear abstention | 1.000 |
| Inter-judge surface agreement | 1.000 |
| Inter-judge candidate agreement | 1.000 |

## Interpretation and boundary

This validates that the adjudication protocol can represent and abstain on
the required classes in a small constructed fixture. It does **not** validate
corporate semantic aliases, undocumented system names, SME agreement, model
calibration, retrieval quality, or downstream SQL/tool artifact utility. The
construction-time labels make this a capability gate, not an enterprise
quality estimate.

The next credible gate is the same stratification over authorized enterprise
cases with at least two independent SME judgments, a NIL/unclear policy,
user/project/time holdouts, and changed-database/tool replay. A model that
improves alias recall while increasing wrong-system or NIL false positives is
not promotable.
