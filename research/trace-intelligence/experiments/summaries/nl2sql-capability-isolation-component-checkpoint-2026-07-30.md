# NL2SQL capability-isolation component checkpoint

**Run date:** 2026-07-30
**Beads:** `bif-kyy.17.13.4.4.1.1.2`, children `.1`–`.6`
**Decision:** component plus one real Linux boundary pass; P1 and hidden remain
sealed because this is not yet the final minimal image or complete 27-gate run.

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
9. A fresh-process solver harness accepts only the strict solver DTO, starts
   with empty home/cwd/cache directories, closes unlisted descriptors, and
   communicates through explicitly inherited Unix broker/model sockets. It
   captures every exercised wire byte and detects raw, hexadecimal, Base64,
   Base64url, and SHA-256 canary representations.
10. The resolver exposes separate supervisor-only `issue_solver_episode` and
    evaluator-only `resolve_gold` methods with different 256-bit capabilities.
    Role, method token, nonce, experiment, fold, stage, episode, stage manifest,
    database snapshot, and expiry are checked before protected factories run.
    Gold is returned in a closed, domain-separated Ed25519 envelope.
11. A fail-closed OCI configuration contract requires a non-root user,
    read-only root, a fresh network namespace, no Linux capabilities,
    `no-new-privileges`, exact rlimits/cgroup limits, default-deny seccomp, no
    socket/connect/clone/namespace syscalls, and owner-correct hardened tmpfs
    mounts.

The hidden envelope uses pinned `cryptography==46.0.6` primitives:
Ed25519, X25519, HKDF-SHA256, and ChaCha20-Poly1305. It is a research envelope,
not `age` wire format. Production should select `age` or a managed KMS envelope
instead of treating this prototype as a key-management system.

## Combined executable result

The capability suite passes **61/61** tests. The decisive composition test:

- executes one three-row candidate through the broker;
- gives the model a deliberately empty, truncated preview;
- seals the complete typed three-row result;
- submits by opaque attempt capability with zero additional database calls;
- evaluates the sealed full result rather than the preview; and
- observes candidate execution count `1` both before and after evaluation.

The same frozen profile then ran under Linux `6.8.0-47-generic`/aarch64 and
`runc 1.1.14`. All 21 enforcement/protocol gates passed: read-only root,
three owned `0700` tmpfs mounts, zero capabilities, `NoNewPrivs=1`, active
seccomp, `AF_INET`/`AF_INET6` socket denial, exact descriptors 0–4, working
inherited broker/model sockets, exact staged application files, named sensitive
paths absent, sanitized environment, no canary disclosure, and runtime cleanup.

That run found two defects before passing:

1. `runc` needs read-only `fstatfs` to validate `/proc/self/fd` when preserving
   descriptors. The original seccomp allowlist denied it.
2. `RLIMIT_NPROC` counts threads for a real UID across the host. UID 65532 was
   already shared by CoreDNS with 17 threads, so even a limit of 16 caused
   `execve` to return `EAGAIN`. The correct scoped controls are the solver
   cgroup's `pids.limit=16` plus seccomp denial of `clone`, `clone3`, `fork`,
   and `vfork`; the host-global rlimit was removed.

The bounded real PostgreSQL 16 role audit separately passed three candidate
executions and three evaluator-only gold executions through different
constrained roles and application names. Both identities were verified, writes
were denied, the actual authorized-relation snapshot stayed unchanged, and
all transient roles and schemas were removed.

The pinned native-tool pilot separately passed 18/18 synthetic episodes across
three availability variants. That pilot proves model/runtime compatibility,
not causal benefit. The Linux run proves one kernel/runtime boundary, not the
final minimal image, production portability, or an independently signed
PostgreSQL server audit.

## Release-gate accounting

The 27 gates in the design are not represented as one green boolean:

| Gates | Component status | Missing proof |
| --- | --- | --- |
| 1, 10 | pass | strict recursive DTO and HMAC episode-reference tests |
| 2–4 | one-profile pass | canary capture, absent named source/secret paths, no Internet socket creation, and inherited Unix peers pass on one Colima/runc profile; final minimal image and portability remain |
| 5, 17 | component partial | method-specific resolver capabilities and fresh local processes pass; still need Linux peer credentials, episode-specific UID/GID, and two-episode OCI state isolation |
| 8, 9 | pass | exact signed unseal inputs, domain separation, tamper and replay checks |
| 11, 13–15 | pass | current authority, episode-scoped attempts, immutable chain, zero-call terminal submission |
| 18, 20, 22 | component pass | evaluator import closure, full-blob use, and gold-controlled ordering |
| 19, 23 | real component partial | distinct PostgreSQL roles, lane identities, write denial, live snapshot stability, and adversarial drift rejection pass; independent server execution receipts and same-profile mutation remain |
| 12, 16, 21, 25 | partial | mechanisms pass locally; require same-run signed receipts and a broader typed-result property corpus |
| 6, 7, 24, 26, 27 | open | complete stage isolation, crash injection, content-minimized OTel, and canonical round trip |

The macOS Seatbelt tests pass outside the outer Codex sandbox. Inside that
outer sandbox, nested `sandbox-exec` returns exit `71`; the same eight tests
pass when allowed to exercise Seatbelt directly. This is an execution
environment constraint, not evidence for the required Linux OCI profile.

## Why P1 remains blocked

The current code proves that the contracts can be composed safely in one test
process. It does **not** yet prove that:

- the final minimal production rootfs has no alternate shell, interpreter,
  package manager, or executable surface (`execve` is needed for startup);
- two OCI episodes use different UIDs, handles, model namespaces, and state;
- OS peer credentials enforce the resolver's abstract supervisor/evaluator
  role assertions;
- PostgreSQL candidate and gold execution counts are independently bound to
  server identity, broker/attempt receipts, and evaluation rather than only
  coordinator receipts;
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

The real Linux command, frozen image digest, failure history, exact raw-evidence
policy, and limitations are in
[`nl2sql-linux-oci-conformance-runbook-2026-07-30.md`](nl2sql-linux-oci-conformance-runbook-2026-07-30.md).

At this checkpoint the repository audit reports 33 aggregate results, 37
dataset manifests, 12 governed fixtures, and zero committed raw corpus files.
Raw prompts, SQL, database results, model messages, identities, and capability
tokens remain outside Git.
