# Governed skill-release lifecycle conformance

**Run date:** 2026-07-30  
**Result:** [`governed-skill-release-lifecycle-2026-07-30.json`](../results/governed-skill-release-lifecycle-2026-07-30.json)

## Result

All 18 transaction-scoped assertions passed in the disposable PostgreSQL
16.12 + pgvector 0.8.1 fixture: eight visibility/state assertions and ten
expected-denial assertions.

The first execution exposed a missing runtime grant on the security-definer
provenance check. The migration was corrected and the complete suite then
passed. That failure is part of the engineering finding: policies and helper
functions must be tested through each non-owner runtime role.

## What the suite proves

- a proposer sees a candidate only when every source trajectory remains
  authorized;
- a proposer cannot see or create hidden test manifests and cannot read
  independent evaluation outcomes;
- an evaluation result cannot be attached to a different candidate than its
  frozen manifest;
- release requires a selected candidate, a passing selection result, and a
  passing proposer-hidden test result;
- any recorded security violation vetoes release even when task accuracy
  passes;
- release scope can narrow but cannot broaden the candidate's purposes;
- candidate content and signed release fields cannot be changed through the
  runtime roles;
- exposure and influence records compose with trajectory/release RLS;
- only the releaser can write release audit events;
- withdrawal immediately removes the release and exposure from runtime
  selection; and
- a stale authorization epoch returns zero candidates.

## What it does not prove

This is lifecycle and authorization conformance, not evidence that a mined
skill improves SQL work. It does not emulate Aurora failover, reader lag,
RDS Proxy behavior, control-plane operations, workload scale, or concurrency.
The next empirical gate is a family-held-out NL2SQL intervention with executable
answers and explicit unauthorized-row/column checks.

## Reproduction

Apply
[`005_skill_release_lifecycle.sql`](../../sql/005_skill_release_lifecycle.sql)
and then execute
[`006_skill_release_assertions.sql`](../../sql/006_skill_release_assertions.sql)
against a disposable database that already has `001`–`004`.
