# Trace Commons metadata audit (2026-08-04)

## Result

The downloaded Trace Commons export is useful for a **session/project-proxy** study, but it is not evidence for a cross-user clustering result. The 28 JSONL files contain 28 session IDs, 17,991 events, 4,675 user-message events, and 4,262 tool-result events. Events expose `cwd` and `gitBranch`, so repository/project and workstream proxies are available. They do not expose an explicit user, author, tenant, organization, account, or email identity field.

The content-free receipt is `experiments/results/trace-commons-metadata-audit-2026-08-04.json`; its verifier passes. No prompt, tool argument, response, or transcript text is emitted by the audit.

## What this permits

- Measure session-level friction, tool usage, rephrasing, and workstream recurrence.
- Construct a **project/session proxy** benchmark with repository-held-out and session-held-out splits.
- Use repeated project paths as a controlled leakage probe, while explicitly treating them as project labels, not user labels.

## What this does not permit

- Claim that traces from different people were clustered together.
- Infer identity from a path, branch name, or session UUID.
- Evaluate enterprise-wide skill gaps or cross-user knowledge transfer.

The correct next dataset requirement is an admission manifest containing a stable pseudonymous principal (user or team), task/work-item label, repository or system identifier, and consent/partition metadata. Until then, a cross-user benchmark would be an unsupported inference. This is a dataset-readiness boundary, not a failure of embedding, memory, or skill-mining methods.
