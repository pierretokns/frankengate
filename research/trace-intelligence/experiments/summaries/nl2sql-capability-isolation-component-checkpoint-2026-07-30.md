# NL2SQL capability-isolation component checkpoint

**Run date:** 2026-07-30
**Beads:** `bif-kyy.17.13.4.4.1.1.2`, children `.1`–`.6`
**Decision:** component boundary passes; P1 and hidden remain sealed.

## What now works together

The component implementation follows the minimum topology in
[`nl2sql-capability-isolation-design-2026-07-30.md`](../../../../docs/roadmap/research/nl2sql-capability-isolation-design-2026-07-30.md)
without adding another database, queue, cache, or resident service:

1. A strict solver DTO exposes only question, official instructions, one
   opaque database capability, one frozen procedure artifact, and limits.
2. Length-prefixed canonical IPC accepts only `describe_schema`,
   `execute_sql`, `submit_sql`, and `abstain`, with one-use nonces and
   operation-specific closed request/response forms.
3. The governed broker revalidates exact current principal, database, handle,
   epoch, snapshot, expiry, and operation authority before every request.
4. Its SQL policy is in a source-neutral module. A clean isolated import test
   proves the broker image imports no Defog task loader, `RuntimeTask`,
   `gold_sql`, evaluator, replay executor, PostgreSQL client, or database
   credential implementation.
5. Each admitted candidate runs once through an abstract read-only database
   adapter. The broker seals the complete typed result in a create-exclusive,
   no-follow, fsynced, content-addressed attempt chain before returning an
   opaque attempt capability.
6. `submit_sql(attempt_id)` selects durable evidence and performs no database
   call. Unknown, denied, failed, replayed, cross-episode, expired, revoked,
   over-budget, and post-terminal operations fail closed.
7. The evaluator core imports no SQL/database/socket/process capability. It
   consumes verified full candidate and gold evidence, applies gold-controlled
   order semantics and numeric tolerances, checks current authority and the
   candidate execution counter before and after comparison, and emits a
   content-minimized receipt.
8. Evidence, visible-selection, and hidden stage manifests can be separately
   canonicalized and signed. The hidden manifest is recipient-encrypted.
   Decryption requires a separately signed pass-only authorization that binds
   the exact envelope, stage commitment, selection receipt, every candidate
   artifact signature, and all frozen model/prompt/tool/policy/comparator/
   database/authority hashes.

The hidden envelope uses pinned `cryptography==46.0.6` primitives:
Ed25519, X25519, HKDF-SHA256, and ChaCha20-Poly1305. It is a research envelope,
not `age` wire format. Production should select `age` or a managed KMS envelope
instead of treating this prototype as a key-management system.

## Combined executable result

The capability suite passes **48/48** tests. The decisive composition test:

- executes one three-row candidate through the broker;
- gives the model a deliberately empty, truncated preview;
- seals the complete typed three-row result;
- submits by opaque attempt capability with zero additional database calls;
- evaluates the sealed full result rather than the preview; and
- observes candidate execution count `1` both before and after evaluation.

The pinned native-tool pilot separately passed 18/18 synthetic episodes across
three availability variants. That pilot proves model/runtime compatibility,
not causal benefit. The isolation suite proves component contracts, not the
Linux process boundary or PostgreSQL audit identity.

## Release-gate accounting

The 27 gates in the design are not represented as one green boolean:

| Gates | Component status | Missing proof |
| --- | --- | --- |
| 1, 10 | pass | strict recursive DTO and HMAC episode-reference tests |
| 8, 9 | pass | exact signed unseal inputs, domain separation, tamper and replay checks |
| 11, 13–15 | pass | current authority, episode-scoped attempts, immutable chain, zero-call terminal submission |
| 18, 20, 22 | component pass | evaluator import closure, full-blob use, and gold-controlled ordering |
| 12, 16, 19, 21, 23, 25 | partial | mechanisms pass locally; require same-run signed receipts, real PostgreSQL roles/audit rows, broader property corpus, and snapshot mutation |
| 2–7, 17, 24, 26, 27 | open | solver canary capture, resolver peer methods, OCI mount/network isolation, crash injection, content-minimized OTel, and canonical round trip |

The macOS Seatbelt tests pass outside the outer Codex sandbox. Inside that
outer sandbox, nested `sandbox-exec` returns exit `71`; the same eight tests
pass when allowed to exercise Seatbelt directly. This is an execution
environment constraint, not evidence for the required Linux OCI profile.

## Why P1 remains blocked

The current code proves that the contracts can be composed safely in one test
process. It does **not** yet prove that:

- a solver process cannot open source, stage, gold, credential, or attempt
  paths;
- TCP/DNS are absent while inherited broker/model Unix descriptors work;
- resolver method capability and peer credentials separate supervisor from
  evaluator;
- candidate and gold executions use distinct constrained PostgreSQL roles and
  audit identities;
- process crashes cannot replay a non-durable attempt;
- unseal replay state survives process or host failure;
- signed evaluation and OTel receipts preserve every required binding without
  restricted content; or
- the same OCI image/profile used for the experiment passes all 27 gates.

Therefore the earlier P0 failure still controls. The 23-task P1 screen and
hidden family remain sealed until the process/OCI/PostgreSQL gates pass and a
fresh complete P0 passes under new code, model, prompt, tool, policy, authority,
database, broker, evaluator, and stage-manifest hashes.

## Reproduction

From `research/trace-intelligence`:

```sh
uv sync --python 3.9 --frozen
uv run python -m unittest discover \
  -s nl2sql_capabilities/tests -p 'test_*.py' -v
uv run python reproducibility.py
```

At this checkpoint the repository audit reports 31 aggregate results, 37
dataset manifests, 12 governed fixtures, and zero committed raw corpus files.
Raw prompts, SQL, database results, model messages, identities, and capability
tokens remain outside Git.
