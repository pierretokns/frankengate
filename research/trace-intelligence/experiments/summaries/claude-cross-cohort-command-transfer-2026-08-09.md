# Claude cross-cohort command-artifact transfer

## Question

Do command artifacts observed in one public Claude trace cohort recur with
successful outcomes in other cohorts, and does parameterized identity increase
that overlap enough to justify cross-user reuse?

## Protocol

The study applies the native Claude parser to four downloaded cohorts: Alin,
Fable-5, Jobseek, and Wisp. It pairs Bash tool uses with native tool results,
then compares exact command hashes with conservative parameterized hashes.
Cross-cohort transfer is counted only when the same artifact has at least one
successful observation in a different cohort. No command is executed and the
receipt contains no command text, outputs, paths, or identifiers.

## Result

The four cohorts contributed 4,332 paired outcomes across 246 JSONL files.
Exact identity overlapped across cohorts in only **1** artifact, covering 3
eligible occurrences, all successful. Parameterized identity overlapped in
**9** artifacts covering 72 occurrences: 71 successes and 1 failure
(`98.61%`).

The Jobseek cohort provides the clearest negative-transfer warning. Its exact
cross-scope success rate was `64.29%` and normalized cross-scope success was
`72.22%`, versus `96.15%` and `96.67%` respectively for same-scope repeats.
Normalization increases discoverability, but it does not make an artifact
portable across projects or users.

## Interpretation gate

Cross-cohort overlap is an operational prior, not proof of shared intent or
safe reuse. The relevant promotion test remains scope, authority, side-effect
contract, semantic intent, and changed-environment replay. Parameterized keys
are candidate-recall features only when their collision rate and mixed-outcome
behavior are reported alongside immutable identity.

## Claim boundary

These public cohorts do not provide consent-stable identities, human intent
labels, or authorization labels. The result cannot establish enterprise
cross-user learning or causal productivity improvement.

Receipts:

- [content-free result](../results/claude-cross-cohort-command-transfer-2026-08-09.json)
- [independent verification](../results/claude-cross-cohort-command-transfer-verification-2026-08-09.json)
- [`claude_cross_cohort_command_artifact_transfer.py`](../../claude_cross_cohort_command_artifact_transfer.py)
