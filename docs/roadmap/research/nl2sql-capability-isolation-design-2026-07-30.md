# NL2SQL capability split: minimum enforceable architecture

Status: design audit for `bif-kyy.17.13.4.4.1.1.2`
Scope reviewed: `defog_sql_factorial.py`, `defog_governed_sql_replay.py`,
`defog_factorial_authority.py`, the frozen factorial contract/design manifest,
their tests, and the canonical trajectory schema in
`research/trace-intelligence`.

## Decision

Do not run P1 or unseal a hidden stage with the current monolithic runner.

The current harness has an important property worth preserving:
`submit_sql(attempt_id)` selects an already executed `QueryResult`, and
`_evaluate_submitted_attempt` compares that in-memory result to independently
executed gold alternatives. It does **not** re-execute the candidate. However,
this is an in-process convention rather than a capability boundary:

- `RuntimeTask` contains `task_id`, database name, category, question,
  instructions, and `gold_sql` in one object
  (`defog_governed_sql_replay.py:212-219`).
- `run_factorial` reads the complete design—including evidence, selection, and
  hidden task IDs—resolves the full task, constructs the database executor,
  and passes everything to `run_agent` in one process
  (`defog_sql_factorial.py:1082-1223`).
- `run_agent` directly calls `executor.catalog()` and
  `executor.execute_candidate()`, retains raw SQL and full `QueryResult`
  objects, and invokes the evaluator itself
  (`defog_sql_factorial.py:461-977`).
- Attempts are mutable in-memory dictionary entries. Their deterministic IDs
  depend only on task seed and attempt index, so the same task's arms reuse the
  same IDs (`defog_sql_factorial.py:296-303,342-351`).
- Runner and executor append different security domains to one mutable JSONL
  file. Its final hash is tamper-evident only at the instant it is calculated;
  the file can still be appended or replaced.
- Exact-current authority is checked by `StaticAuthorityEpochStore` before the
  episode, but `_authority_valid` inside the tool loop checks only that required
  strings are present. Revocation between episode creation, execution, and
  submission is therefore not detected.
- The single design manifest contains raw task IDs and all stage memberships.
  It is hash-pinned but not signed, encrypted, or capability-mounted.
- Plain SHA-256 of a public task ID is dictionary-reversible; it is not a
  hidden identifier.

The minimum correction is one offline sealer, five small runtime processes,
one existing PostgreSQL system, and one local content-addressed directory.
There is no need for Redis, Kafka, another SQL database, or a general workflow
engine.

## Required invariants

1. The solver receives only the official question, official instructions, one
   opaque current-authority database capability, one frozen artifact, and
   limits. It never receives task/source IDs, database names, fold/stage roles,
   gold SQL, gold results, adjudications, stage membership, or outcome labels.
2. The solver has no source checkout, stage manifest, database credential,
   evaluator executable/socket, persistent home/cache, general filesystem, or
   `AF_INET`/`AF_INET6` network capability.
3. The solver can communicate only over two inherited Unix-domain socket file
   descriptors: fixed-model completion and governed database tools.
4. The database broker is the only candidate-query executor and the only
   writer to the attempt store. It revalidates the exact current authorization
   epoch before every schema observation, candidate execution, and submission.
5. Each admitted SQL attempt is executed at most once. Submission selects a
   durable attempt capability; submission and evaluation cannot execute its
   SQL.
6. The evaluator reads the submitted attempt's stored full `QueryResult`,
   resolves gold/adjudication through an evaluator-only resolver channel,
   executes only gold alternatives, and compares results under a versioned
   comparator.
7. Evidence, visible-selection, and hidden-test membership are separate signed
   manifests. The solver mounts none of them. The hidden manifest remains
   encrypted until candidate artifacts and the selection-gate receipt are
   signed.
8. Every result is bound to stage, model, prompt/artifact, tool contract,
   evaluator/comparator, database snapshot, SQL policy, authority snapshot and
   epoch, broker build, attempt ledger, and raw audit hashes.
9. Every fold/episode has a fresh solver process, empty tmpfs, fresh capability
   tokens, and no reusable model/retrieval/memory namespace.

## Smallest concrete process topology

```text
offline stage_sealer.py
  source/cohort + master design
       -> signed evidence.manifest
       -> signed selection.manifest
       -> signed+encrypted hidden.manifest envelope

runtime supervisor/model proxy (no source or gold)
  |-- one-episode SolverEpisodeDTO ----------> isolated solverd
  |                                               | inherited FD 3
  |                                               v
  |                                         brokerd -> governed PostgreSQL
  |                                               |
  |                                               v
  |                                      append-once attempt store
  |                                               |
  |-- inherited FD 4 fixed-model proxy <----------+
  |
  +--> resolverd -- evaluator-only gold DTO --> evaluatord
                                               | reads submitted blob
                                               | executes gold only
                                               v
                                         EvaluationReceipt
```

Runtime processes:

1. **`supervisor.py` / fixed-model proxy** verifies signatures, starts a fresh
   episode sandbox, forwards only the frozen model request to the pinned local
   model, and aggregates content-free receipts. It has no source checkout or
   gold API.
2. **`resolverd.py`** is the only process with the source checkout and decrypted
   current-stage manifest. It has two distinct methods and sockets:
   `issue_solver_episode` returns the redacted solver DTO; `resolve_gold` is
   accessible only to the evaluator UID.
3. **`solverd.py`** owns the model/tool loop. It has a read-only rootfs, empty
   tmpfs, no network namespace, no database credential, and only inherited
   Unix socket FDs 3 (broker) and 4 (fixed-model proxy).
4. **`brokerd.py`** owns the governed candidate database credential, live
   authority client/snapshot, SQL policy, frozen catalog receipt, attempt
   budget, and append-once store writer. It never receives gold.
5. **`evaluatord.py`** owns an evaluator database credential constrained to the
   same authorized view and immutable fixture snapshot. It can call
   `resolverd.resolve_gold` and read submitted attempt blobs. It has no model
   or solver socket and cannot ask the broker to execute candidate SQL.

The **attempt store is a directory, not another daemon**. `brokerd` is its only
writer; `evaluatord` has read-only access. This is the smallest design that
separates all requested capabilities.

`stage_sealer.py` is an offline command, not a resident service. Its Ed25519
private key and hidden-manifest encryption identity are absent from runtime.

The research implementation uses a closed signed JSON envelope built from
Ed25519, ephemeral X25519, HKDF-SHA256, and ChaCha20-Poly1305 via pinned
`cryptography==46.0.6`. It is not `age` wire format and does not provide a
managed key lifecycle. Production may replace this envelope with `age` or a
managed KMS envelope without changing the signed manifest or pass-only unseal
authorization contracts.

## Exact DTOs

All IPC uses length-prefixed UTF-8 JSON, a 16 MiB hard frame limit, JSON Schema
2020-12, `additionalProperties: false` at every object, no floats in signed
objects, and deterministic RFC 8785/JCS encoding. Binary values use unpadded
base64url. Every request includes a one-use `request_nonce`; every response
echoes it. Unix peer credentials and capability tokens are both checked.

### 1. Solver episode

This is the only benchmark DTO available to `solverd`:

```json
{
  "schema_version": "fg-solver-episode-v1",
  "question": "official question bytes",
  "official_instructions": "official instruction bytes, possibly empty",
  "authorized_database_handle": {
    "handle": "base64url(random 256 bits)",
    "broker_protocol_version": "fg-governed-sql-tool-v1",
    "authorization_epoch_ref_sha256": "64 hex",
    "authority_snapshot_sha256": "64 hex",
    "expires_at_unix_ms": 1780000000000
  },
  "artifact_exposure": {
    "artifact_id": "opaque arm artifact label",
    "artifact_sha256": "64 hex",
    "content": "exact frozen procedure_artifact bytes"
  },
  "limits": {
    "max_model_turns": 6,
    "max_schema_calls": 2,
    "max_sql_attempts": 3,
    "max_generated_tokens_per_call": 1024,
    "max_generated_tokens_per_episode": 4096,
    "model_wall_ms": 60000,
    "model_result_max_rows": 50,
    "model_result_max_bytes": 32768
  }
}
```

The handle is a random episode-scoped bearer capability stored server-side
against the hidden `stage_episode_ref`, authority binding, database DSN,
catalog/policy receipt, budgets, and expiry. It reveals none of those values.
It is destroyed when the episode ends. `task_id`, `database`, `query_category`,
`fold`, `stage`, `source_file`, `source_row`, `gold_sql`, adjudications, seed
derivation inputs, and hidden IDs are forbidden schema properties.

The supervisor supplies model seed and fixed-model configuration outside this
benchmark DTO. The model itself sees question, instructions, artifact, tool
schemas, and bounded tool observations—not the database capability token.

### 2. Governed broker requests and responses

```json
{
  "schema_version": "fg-tool-request-v1",
  "request_nonce": "base64url(random 128 bits)",
  "database_handle": "opaque 256-bit handle",
  "operation": "describe_schema",
  "arguments": {}
}
```

```json
{
  "schema_version": "fg-tool-request-v1",
  "request_nonce": "base64url(random 128 bits)",
  "database_handle": "opaque 256-bit handle",
  "operation": "execute_sql",
  "arguments": {"sql": "one candidate SELECT/CTE"}
}
```

```json
{
  "schema_version": "fg-tool-request-v1",
  "request_nonce": "base64url(random 128 bits)",
  "database_handle": "opaque 256-bit handle",
  "operation": "submit_sql",
  "arguments": {"attempt_id": "base64url(random 192 bits)"}
}
```

`describe_schema` returns:

```json
{
  "schema_version": "fg-tool-response-v1",
  "request_nonce": "...",
  "status": "ok",
  "observation": {
    "tables": {"public.orders": ["amount", "id"]},
    "catalog_sha256": "64 hex"
  },
  "authority_receipt_sha256": "64 hex",
  "remaining": {"schema_calls": 1, "sql_attempts": 3, "model_turns": 5}
}
```

`execute_sql` returns only bounded model evidence:

```json
{
  "schema_version": "fg-tool-response-v1",
  "request_nonce": "...",
  "status": "ok",
  "attempt_id": "opaque random 192-bit capability",
  "observation": {
    "columns": ["n"],
    "rows": [[{"kind": "int", "value": "2"}]],
    "row_count": 1,
    "preview_truncated": false,
    "result_sha256": "64 hex"
  },
  "authority_receipt_sha256": "64 hex",
  "policy_receipt_sha256": "64 hex",
  "remaining": {"schema_calls": 1, "sql_attempts": 2, "model_turns": 4}
}
```

Denials use a fixed enum (`authority_denied`, `policy_denied`,
`database_error`, `resource_limit`, `invalid_arguments`) plus a stable code and
message hash. They never reveal gold/evaluator information. Attempt IDs are
random and scoped to one database handle; an ID from another arm, task, fold,
or expired episode is rejected.

`submit_sql` performs **no SQL call**. It atomically closes the ledger and
returns:

```json
{
  "schema_version": "fg-tool-response-v1",
  "request_nonce": "...",
  "status": "accepted",
  "terminal": true,
  "submission_receipt_sha256": "64 hex"
}
```

The full signed `SubmissionReceipt` goes to the supervisor/evaluator, not the
model.

### 3. Canonical full query result

The broker stores the complete evaluator result separately from the bounded
model preview:

```json
{
  "schema_version": "fg-query-result-v1",
  "columns": [
    {"name": "n", "pg_type_oid": 20, "format": "text"}
  ],
  "rows": [
    [{"kind": "int", "value": "2"}]
  ],
  "row_count": 1,
  "result_bytes": 102,
  "result_content_sha256": "64 hex"
}
```

`result_content_sha256` hashes the JCS encoding of `columns` and `rows` only.
Row order and duplicate rows are preserved. `result_bytes` is descriptive and
not part of semantic equality.

Allowed cell encodings are exact and versioned:

| PostgreSQL class | `kind` | `value` |
| --- | --- | --- |
| NULL | `null` | `null` |
| boolean | `bool` | JSON boolean |
| int2/int4/int8 | `int` | canonical base-10 string |
| numeric/decimal | `decimal` | canonical non-exponent decimal string |
| float4/float8 | `float` | IEEE-754 hexadecimal string; explicit `nan`, `inf`, `-inf` |
| text/varchar/char/enum | `text` | JSON string |
| date/time/timestamp/timestamptz | corresponding kind | ISO-8601 string; timezone required for timestamptz |
| bytea | `bytes` | unpadded base64url |
| uuid | `uuid` | lowercase canonical UUID |
| json/jsonb | `json` | JCS JSON string |
| one-dimensional supported arrays | `array` | ordered array of typed cells |

Unknown/composite/range types fail with `unsupported_result_type`; they are
never coerced to Python `str()`. This is necessary because the current
`_canonical_cell` fallback hashes class names and string renderings, which is
not a portable evaluation contract.

### 4. Stored attempt evidence

Each SQL request produces exactly one append-once `AttemptEvidence`:

```json
{
  "schema_version": "fg-attempt-evidence-v1",
  "stage_episode_ref": "opaque HMAC identifier",
  "attempt_id": "opaque random 192-bit capability",
  "attempt_index": 0,
  "previous_attempt_blob_sha256": null,
  "candidate_sql_sha256": "64 hex",
  "status": "executed",
  "validation": {
    "policy_accepted": true,
    "policy_version_sha256": "64 hex",
    "catalog_sha256": "64 hex",
    "validated_ast_sha256": "64 hex",
    "referenced_tables_sha256": "64 hex",
    "referenced_columns_sha256": "64 hex",
    "referenced_functions_sha256": "64 hex"
  },
  "execution": {
    "execution_kind": "candidate",
    "candidate_execution_count": 1,
    "postgres_role_sha256": "64 hex",
    "database_snapshot_sha256": "64 hex",
    "statement_timeout_ms": 5000,
    "row_count": 1,
    "column_count": 1,
    "result_bytes": 102,
    "result_content_sha256": "64 hex"
  },
  "authority": {
    "binding_sha256": "64 hex",
    "epoch_ref_sha256": "64 hex",
    "authority_snapshot_sha256": "64 hex",
    "checked_at_unix_ms": 1780000000000
  },
  "query_result": {"schema_version": "fg-query-result-v1"},
  "error": null,
  "broker_build_sha256": "64 hex",
  "tool_contract_sha256": "64 hex",
  "created_at_unix_ms": 1780000000000
}
```

For denied/failed attempts, `query_result` and execution result fields are null,
`candidate_execution_count` is zero when PostgreSQL was never called, and
`error` is exactly
`{"class": "...", "code": "...", "message_sha256": "..."}`.

Raw SQL belongs in a separately encrypted broker audit record keyed by the
attempt blob hash. The evaluator does not need it and should not receive it.

The broker writes JCS bytes to
`attempts/blobs/sha256/<attempt_blob_sha256>` using
`O_CREAT|O_EXCL|O_NOFOLLOW`, mode `0440`, then `fsync`s the file and parent
directory. The directory is mode `0750`, owned by `broker:evaluator`; the
solver is not in that group. A temporary partial file is mode `0600` in a
broker-only directory and is never considered evidence. Existing targets are
verified byte-for-byte and never overwritten.

This is append-once and cryptographically tamper-evident under the process
threat model, not hardware WORM. Production may replace the directory with
versioned object storage/Object Lock without changing DTOs.

### 5. Submission receipt

```json
{
  "payload": {
    "schema_version": "fg-submission-receipt-v1",
    "stage_episode_ref": "opaque HMAC identifier",
    "attempt_id": "opaque random 192-bit capability",
    "attempt_blob_sha256": "64 hex",
    "attempt_ledger_root_sha256": "64 hex",
    "attempt_count": 3,
    "submitted_attempt_index": 1,
    "candidate_execution_count": 1,
    "result_content_sha256": "64 hex",
    "authority_at_execution_sha256": "64 hex",
    "authority_at_submission_sha256": "64 hex",
    "database_snapshot_sha256": "64 hex",
    "policy_version_sha256": "64 hex",
    "catalog_sha256": "64 hex",
    "broker_build_sha256": "64 hex",
    "tool_contract_sha256": "64 hex",
    "submitted_at_unix_ms": 1780000000000
  },
  "signature": {
    "algorithm": "Ed25519",
    "key_id": "defog-broker-research-v1",
    "payload_sha256": "64 hex",
    "signature_base64url": "..."
  }
}
```

The ledger root hashes the ordered attempt blob hashes and terminal action.
The broker first revalidates the current epoch, verifies that the attempt
belongs to this live handle and is durable/successful, closes the ledger, and
signs. Subsequent tool calls and repeated submissions fail. There is no SQL or
database executor call in the submission code path.

### 6. Gold resolver DTO (evaluator only)

`evaluatord` calls `resolverd.resolve_gold(stage_episode_ref,
evaluator_capability)` over an evaluator-only socket:

```json
{
  "payload": {
    "schema_version": "fg-evaluator-gold-v1",
    "stage_episode_ref": "opaque HMAC identifier",
    "source_task_id": "trusted raw source ID",
    "source_locator": {
      "source_file_sha256": "64 hex",
      "source_row_0based": 24
    },
    "question_sha256": "64 hex",
    "official_instructions_sha256": "64 hex",
    "gold_sql_alternatives": ["SELECT ..."],
    "gold_sql_sha256": "64 hex",
    "database_snapshot_sha256": "64 hex",
    "evaluator_database_handle": "opaque evaluator-only handle",
    "adjudication": {
      "classification": "primary_quality_eligible",
      "primary_quality_eligible": true,
      "required_sensitive_entitlements": []
    },
    "cohort_manifest_sha256": "64 hex",
    "dataset_manifest_sha256": "64 hex",
    "stage_manifest_sha256": "64 hex"
  },
  "resolver_signature": {
    "algorithm": "Ed25519",
    "key_id": "defog-resolver-research-v1",
    "payload_sha256": "64 hex",
    "signature_base64url": "..."
  }
}
```

Only this DTO contains raw task/source IDs or gold. The evaluator socket
directory and peer-credential allowlist exclude supervisor, broker, and solver.

### 7. Evaluation receipt

```json
{
  "payload": {
    "schema_version": "fg-evaluation-receipt-v1",
    "stage_episode_ref": "opaque HMAC identifier",
    "submission_receipt_sha256": "64 hex",
    "attempt_blob_sha256": "64 hex",
    "candidate_result_sha256": "64 hex",
    "gold_result_sha256": ["64 hex"],
    "matched_gold_alternative": 0,
    "semantic_correct": true,
    "strict_answer_shape_correct": true,
    "security_authorized": true,
    "authority_current_at_evaluation": true,
    "candidate_execution_count_before_evaluation": 1,
    "candidate_execution_count_after_evaluation": 1,
    "gold_execution_count": 1,
    "comparator": {
      "name": "defog-result-equivalence",
      "version_sha256": "64 hex",
      "numeric_relative_tolerance": "1e-9",
      "numeric_absolute_tolerance": "1e-12",
      "order_rule": "gold-query-order-by"
    },
    "model_manifest_sha256": "64 hex",
    "prompt_contract_sha256": "64 hex",
    "artifact_sha256": "64 hex",
    "tool_contract_sha256": "64 hex",
    "evaluator_build_sha256": "64 hex",
    "broker_build_sha256": "64 hex",
    "database_snapshot_sha256": "64 hex",
    "policy_version_sha256": "64 hex",
    "authority_snapshot_sha256": "64 hex",
    "stage_manifest_sha256": "64 hex",
    "raw_audit_chain_sha256": "64 hex"
  },
  "signature": {
    "algorithm": "Ed25519",
    "key_id": "defog-evaluator-research-v1",
    "payload_sha256": "64 hex",
    "signature_base64url": "..."
  }
}
```

## Evaluation without candidate re-execution

The evaluator algorithm is deliberately unable to re-run a candidate:

1. Verify stage, resolver, broker, submission, and attempt signatures/hashes.
2. Verify the submitted blob is in the signed closed ledger and has
   `status=executed`, `candidate_execution_count=1`, current authority, matching
   database snapshot, admitted policy, and a full `fg-query-result-v1`.
3. Deserialize the stored typed candidate `QueryResult`. Do not load raw SQL.
4. Resolve evaluator-only gold and adjudication data.
5. Execute gold alternatives with `application_name=fg_gold_evaluator` and an
   evaluator PostgreSQL role constrained to the same authorized RLS view and
   immutable fixture snapshot. The evaluator role has no candidate-execution
   API.
6. Determine order sensitivity from each gold AST. Compare the stored candidate
   result to each gold result using the pinned comparator.
7. Read the broker/DB candidate execution counter again and assert it remains
   one. Sign the evaluation receipt.

Candidate and gold queries use different PostgreSQL roles/application names so
statement audits can distinguish them even when their SQL text is identical.
The fixture database must be immutable for the experiment. Its dump/snapshot
hash is checked at handle issuance, candidate execution, and gold execution.
If it changes, evaluation is infrastructure-invalid rather than incorrect.

If the broker crashes after PostgreSQL returns but before durable attempt
evidence is sealed, the attempt is an infrastructure failure and cannot be
submitted. It must not be silently re-executed under the same attempt ID.

## Stage-sealed manifests

### Signed payload

Generate one trusted manifest per `(experiment, fold, stage_role)`, where
`stage_role` is exactly `evidence`, `visible_selection`, or `hidden_test`.

```json
{
  "payload": {
    "schema_version": "fg-stage-manifest-v1",
    "experiment_id": "defog-sql-factorial-v3",
    "fold_id": "fold-0",
    "stage_role": "hidden_test",
    "manifest_sequence": 3,
    "created_at_unix_ms": 1780000000000,
    "parent_design_sha256": "64 hex",
    "cohort_manifest_sha256": "64 hex",
    "dataset_manifest_sha256": "64 hex",
    "prompt_contract_sha256": "64 hex",
    "tool_contract_sha256": "64 hex",
    "model_manifest_sha256": "64 hex",
    "authority_snapshot_sha256": "64 hex",
    "policy_version_sha256": "64 hex",
    "comparator_version_sha256": "64 hex",
    "database_snapshots": [
      {"database_ref": "broker", "snapshot_sha256": "64 hex"}
    ],
    "artifact_set_sha256": "64 hex",
    "selection_gate_contract_sha256": "64 hex",
    "episode_count": 24,
    "ordered_episode_commitment_sha256": "64 hex",
    "episodes": [
      {
        "stage_episode_ref": "HMAC-SHA256 stage-opaque ID",
        "source_task_id": "trusted raw task ID",
        "source_file_sha256": "64 hex",
        "source_row_0based": 11,
        "question_sha256": "64 hex",
        "official_instructions_sha256": "64 hex",
        "gold_sql_sha256": "64 hex",
        "database_ref": "broker",
        "query_category": "advanced",
        "primary_quality_eligible": true,
        "adjudication_ref": null,
        "paired_seed": 123456,
        "arm_order": ["expert", "placebo", "baseline"]
      }
    ],
    "allowed_runtime_roles": ["resolver", "evaluator"]
  },
  "signature": {
    "algorithm": "Ed25519",
    "key_id": "defog-stage-sealer-v1",
    "payload_sha256": "64 hex",
    "signature_base64url": "..."
  }
}
```

`stage_episode_ref` is
`HMAC-SHA256(stage_id_key, experiment_id || NUL || fold_id || NUL ||
stage_role || NUL || source_task_id)`. The HMAC key exists only in the offline
sealer and resolver. Unlike the current unsalted task hash, this cannot be
dictionary-matched against public task IDs.

### Derivation and sealing

`stage_sealer.py` must:

1. Verify the pinned dataset/cohort/design/prompt/tool/model/authority/policy/
   comparator/database hashes.
2. Recompute all task content hashes from the pinned source checkout.
3. Derive the three stage sets from the master rotation; assert pairwise
   disjointness, expected counts, policy adjudications, and that each family is
   evidence twice, selection once, and hidden once across folds.
4. Generate opaque HMAC episode references and preregistered paired seeds/arm
   order.
5. Emit JCS payloads using create-exclusive, fsync, atomic-finalize writes.
6. Sign domain-separated bytes:
   `b"FG-STAGE-MANIFEST-V1\\0" || JCS(payload)` with Ed25519.
7. Emit a public content-free `StageCommitmentReceipt` containing only stage
   role, count, all input hashes, payload hash, ordered episode commitment,
   signer/key ID, and signature. The solver receives neither artifact.
8. Encrypt the already signed hidden manifest to the evaluator
   unseal identity, then sign an outer envelope containing ciphertext SHA-256.
   Keep only ciphertext mounted before the gate.

Hidden unsealing requires a signed `HiddenUnsealAuthorization` binding:

- all frozen candidate artifact hashes for every fold;
- their proposer signatures and evidence-manifest hashes;
- the signed visible-selection result/gate receipt;
- the preregistered gate decision;
- exact model/tool/policy/comparator/database/authority hashes; and
- the hidden ciphertext hash.

Any artifact edit, missing fold signature, failed selection gate, hash drift,
or prior hidden-unseal receipt rejects unsealing. Selection may choose among
already signed candidates but cannot rewrite them. Runtime has verification
public keys only; no stage signing private key.

The solver never mounts a stage manifest. `resolverd` reads only the current
stage manifest. Before unseal, no process has both the hidden decryption key
and a valid authorization. Evidence proposers mount only the evidence
manifest; visible selection evaluators mount only the selection manifest.

## IPC, identities, mounts, and permissions

Use a rootless OCI/Podman or Docker Compose profile for the isolation tests and
real experiment. Unix socket calls remain local even with `--network=none`.

| Resource | Owner / mode | Readers | Writer | Solver visibility |
| --- | --- | --- | --- | --- |
| Pinned source checkout | `resolver:resolver`, dirs `0550`, files `0440` | resolver | none at runtime | absent mount |
| Current decrypted stage manifest | `resolver:resolver`, `0400` | resolver | offline sealer | absent |
| Hidden ciphertext before gate | `supervisor:sealer`, `0400` | supervisor | offline sealer | absent |
| Sealer private key | offline host, `0400` | sealer only | sealer only | absent from runtime |
| Verification public keys | `root:root`, `0444` | relevant processes | none | public keys are harmless |
| Broker DSN/credential | `broker:broker`, `0400` secret FD | broker | deployment | absent |
| Evaluator DSN/credential | `evaluator:evaluator`, `0400` secret FD | evaluator | deployment | absent |
| Attempt blob directory | `broker:evaluator`, `0750`; blobs `0440` | broker/evaluator | broker only | absent |
| Raw SQL/model audit | `audit:audit`, `0700`; encrypted blobs `0400` | authorized audit role | role-specific writer | absent |
| Solver rootfs/code | read-only, code `0555` | solver | none | present |
| Solver `/tmp` | per-episode tmpfs `0700`, max 16 MiB, `nodev,nosuid,noexec` | solver | solver | destroyed after episode |
| Solver home/cache | none (`HOME=/nonexistent`) | none | none | unavailable |

Socket layout uses parent directories rather than relying only on socket mode:

- `/run/fg-exp/solver/<episode>/broker.sock`: directory `0710`
  `broker:solver_<episode>`, socket `0660`; `SO_PEERCRED` must match the unique
  episode UID.
- model proxy is passed as inherited FD 4 and has no filesystem path in the
  solver namespace.
- `/run/fg-exp/resolver/evaluator.sock`: directory `0710`
  `resolver:evaluator`, socket `0660`; only evaluator UID accepted.
- `/run/fg-exp/resolver/supervisor.sock`: separate method surface that can issue
  redacted solver DTOs but cannot resolve gold.

Run `solverd` with:

- read-only root filesystem;
- `--network=none` (no `AF_INET`/`AF_INET6`);
- all Linux capabilities dropped, `no-new-privileges`, seccomp denying
  `mount`, `ptrace`, namespace creation, raw sockets, and keyring calls;
- per-episode UID/GID and PID namespace;
- `/proc` hidden or mounted with `hidepid=2`;
- only code and an empty tmpfs mounted;
- `close_fds=True`, then explicitly pass broker FD 3 and model FD 4;
- an environment allowlist containing locale and deterministic runtime values,
  never paths, DSNs, task IDs, stages, or API tokens.

Broker egress is restricted to PostgreSQL and the authority service/snapshot.
Evaluator egress is restricted to PostgreSQL and its resolver Unix socket.
Resolver has no network. Supervisor/model proxy can reach only the pinned local
model endpoint. All RPCs have deadlines, request-size limits, schema
validation, one-use nonces, per-handle budgets, and peer-credential checks.

## Tests that prove the boundary

These are release gates, not merely unit conveniences.

### DTO and source/gold isolation

1. `test_solver_dto_exact_allowlist`: recursively reject `task_id`, `database`,
   `db_name`, `query_category`, `fold`, `stage`, `source`, `locator`, `gold`,
   `answer`, `adjudication`, `outcome`, `label`, and all unknown fields.
2. `test_solver_prompt_contains_no_trusted_tokens`: plant unique canaries in
   source task ID, gold SQL, hidden manifest, adjudication, DSN, and signing
   key; capture every solver/model/broker byte and assert no canary appears.
3. `test_solver_mount_namespace_has_no_source_or_manifests`: attempts to open
   known source, design, evidence, selection, hidden, evaluator, credential,
   and attempt-store paths return `ENOENT`/`EACCES`.
4. `test_solver_has_no_tcp_or_dns`: socket creation/connect to loopback,
   PostgreSQL, model port, DNS, and internet fail; inherited Unix FDs work.
5. `test_resolver_method_capabilities`: supervisor peer can issue redacted DTO
   but cannot resolve gold; evaluator peer can resolve gold; broker/solver
   peers are rejected before a response body.

### Stage isolation and sealing

6. `test_stage_sets_are_pairwise_disjoint_and_complete`: recompute rotations
   from pinned source; match counts and commitments.
7. `test_hidden_manifest_is_ciphertext_before_gate`: no raw task ID, question
   hash, gold hash, database family, or stage episode ref is discoverable in
   runtime mounts or process arguments.
8. `test_hidden_unseal_requires_all_signed_artifacts`: independently mutate or
   omit every artifact/gate/model/tool/policy/database/authority hash and assert
   fail-closed.
9. `test_manifest_signature_and_domain_separation`: corrupted payload,
   signature, key ID, sequence, fold, or role fails; signatures cannot be
   replayed as another receipt type.
10. `test_public_task_hash_cannot_link_episode_ref`: public task ID SHA does not
    equal or derive the HMAC episode reference; the HMAC key is absent from
    runtime except resolver secret memory.

### Broker, authority, and immutable attempts

11. `test_stale_epoch_denies_before_observation`: stale/missing/wrong-subject
    epoch causes describe, execute, and submit to fail before catalog/result
    bytes are returned.
12. `test_revocation_between_execute_and_submit_fails_closed`: change current
    epoch after a durable result; submission is denied and evaluator refuses a
    success verdict.
13. `test_attempt_capability_is_episode_scoped`: unknown, guessed, cross-arm,
    cross-task, cross-fold, expired, denied, and failed attempt IDs cannot be
    submitted.
14. `test_attempt_blob_create_exclusive_and_hash_verified`: overwrite, symlink,
    truncation, post-seal append, blob substitution, ledger reorder, and partial
    temp files are rejected.
15. `test_submit_is_terminal_and_has_zero_db_calls`: instrument the candidate
    executor; DB call count is unchanged by submit, repeated submit, and all
    post-terminal calls.
16. `test_frozen_catalog_and_policy_binding`: catalog or policy drift after
    handle issue invalidates the handle instead of silently changing
    validation.
17. `test_cross_episode_state_is_absent`: episode B cannot read episode A's
    tmpfs, messages, attempt IDs, broker handle, model cache, retrieval/memory
    namespace, or environment.

### Non-reexecution and result fidelity

18. `test_evaluator_cannot_call_candidate_executor`: do not link/import a
    candidate execution client in evaluator; seccomp/network/credential checks
    additionally prevent access.
19. `test_candidate_execution_count_remains_one`: PostgreSQL audit rows tagged
    `fg_candidate_broker` remain exactly one before and after evaluation,
    including when candidate SQL text equals gold SQL. Gold rows are tagged
    separately as `fg_gold_evaluator`.
20. `test_evaluator_uses_full_blob_not_model_preview`: truncate the preview to
    zero/one row while retaining a full stored result; verdict must use the
    full blob.
21. `test_query_result_round_trip_property`: property-test nulls, duplicate and
    reordered rows, unicode, bytes, timestamps/timezones, decimals, signed
    zero, finite/infinite/NaN floats, UUID/JSON/arrays, and unsupported types.
22. `test_gold_order_controls_order_sensitivity`: candidate order never
    overrides the gold query's order rule.
23. `test_database_snapshot_drift_is_infrastructure_invalid`: modify fixture
    state between candidate and gold; evaluator refuses a semantic verdict.
24. `test_broker_crash_after_execute_does_not_retry_same_attempt`: a non-durable
    execution is an infrastructure failure and cannot be submitted or silently
    rerun.

### Complete receipts and observability

25. `test_evaluation_receipt_has_all_bindings`: require non-null hashes for
    stage, cohort/dataset, model, prompt, artifact, tool, evaluator/comparator,
    broker, DB snapshot, policy, authority snapshot/epoch/binding, attempt
    ledger/blob/result, and raw audit chain.
26. `test_otel_export_contains_no_restricted_content`: exported attributes and
    baggage contain no question, instructions, SQL, rows, raw task ID, source
    path, gold, DSN, capability token, or identity; approved hashes and opaque
    refs remain.
27. `test_canonical_projection_preserves_tool_order_and_links`: exact ordered
    model/tool/submit/evaluation events, parent IDs, observation status, source
    role, attempt link, and loss receipt survive projection and OTel roundtrip.

P1 remains blocked until all tests pass in the same OCI profile used for the
experiment and a fresh complete P0 passes under the resulting code/config
hashes. Hidden remains blocked until P1's signed gate permits unseal.

## Frankengate OTel and canonical-event mapping

Keep solver execution and evaluation as separate traces joined with OTel
`Link`s; do not pretend evaluation is a synchronous child span of the original
model request.

| Capability event | OTel span/event | Canonical event |
| --- | --- | --- |
| Redacted episode issue | `frankengate.experiment.task.resolve` | `episode.input.resolved` |
| Authority epoch check | event on tool span `governance.authority.check` | `governance.check` |
| Model request/response | OpenInference/GenAI client span | `model.request`, `model.response` |
| Schema request/result | `frankengate.tool.describe_schema` | `tool.request`, `tool.result` |
| Candidate policy | event on candidate span | `db.query.policy` |
| Candidate execution | `frankengate.tool.execute_sql` | `db.query.request`, `db.query.result` |
| Terminal selection | `frankengate.agent.submit_sql` linked to execute span | `agent.submission` |
| Attempt store seal | `frankengate.attempt.seal` | `attempt.sealed` |
| Gold resolution | evaluator trace `frankengate.eval.gold.resolve` | `evaluation.gold.resolved` |
| Gold execution | `frankengate.eval.gold.execute` | `evaluation.gold.result` |
| Comparator verdict | `frankengate.eval.compare` | `evaluation.verdict` |

Common safe attributes:

- `frankengate.experiment.id`
- `frankengate.fold.id`
- `frankengate.stage.manifest.sha256`
- `frankengate.episode.ref` (opaque HMAC reference)
- `frankengate.arm.artifact.sha256`
- `frankengate.attempt.id` (opaque, access-controlled)
- `frankengate.attempt.blob.sha256`
- `frankengate.result.sha256`
- `frankengate.authority.{binding,epoch,snapshot}.sha256`
- `frankengate.database.snapshot.sha256`
- `frankengate.policy.sha256`
- `frankengate.tool_contract.sha256`
- `gen_ai.provider.name`, `gen_ai.request.model`, token/latency counts

Question, instructions, prompt text, SQL, tool arguments, rows, gold,
capability tokens, subject IDs, and DSNs are not OTel attributes or baggage.
If retained, they live only in encrypted role-specific raw audit storage with
classification and RLS metadata. Full query results never enter OTel.

For `canonical-trajectory-v1`, use:

- stable `event_id` from episode ref + monotonic sequence + event kind;
- `source_role` of `resolver`, `solver`, `model`, `broker`, or `evaluator`;
- `observation_status=observed` for exact tool/model records and
  `reconstructed`/`inferred` only when genuinely derived;
- `parent_event_id` to link tool results to calls and submission to the exact
  stored execution;
- an evaluator trace link and receipt hash rather than flattening gold into the
  solver trajectory;
- a loss receipt that explicitly declares restricted content omitted from the
  export and whether exact tool arguments/results remain in the authorized raw
  tier.

Frankengate production mapping is direct: virtual key/user/team and current
authorization epoch stay in the broker's authority binding; only their hashes
enter research receipts. Per-request growing messages/results remain in the
external attempt/trace manager keyed by request/episode ID, never in
`BifrostContext`, consistent with the repository's context-size rule.

## Specific code changes

Preserve:

- SQL parser/policy checks and read-only/RLS role verification in
  `defog_governed_sql_replay.py`;
- source content hash verification in `PinnedTaskResolver`;
- explicit `submit_sql`/`abstain` terminal tools and bounded model previews;
- Defog benchmark and strict answer-shape comparators;
- exact-current static authority fixture as a local test double; and
- the preregistered arm/tool/limit contract and current P0 null/mechanics
  result.

Replace/split:

1. Replace `RuntimeTask` with private `ResolvedTaskSecret`, public
   `SolverEpisodeDTO`, and evaluator-only `GoldResolutionDTO`.
2. Move task resolution to `resolverd.py`; remove source paths and
   `PinnedTaskResolver` from `defog_sql_factorial.py`.
3. Change `run_agent(task, executor, ...)` to
   `run_agent(SolverEpisodeDTO, ToolBrokerClient, FixedModelClient, ...)`.
   It must not import evaluator, replay executor, resolver, `psycopg2`, or
   source modules.
4. Move `_evaluate_submitted_attempt` into `evaluatord.py`. Keep its current
   stored-result comparison behavior, but load the durable typed result through
   a read-only `AttemptStoreReader`.
5. Split `GovernedPostgresExecutor` into candidate `brokerd` and gold-only
   evaluator execution. Freeze the catalog at handle issuance instead of
   calling `catalog()` implicitly for every candidate.
6. Replace `AttemptRecord` and the shared `attempt_records` dict with
   append-once `AttemptEvidence` blobs and a signed ledger. Replace
   deterministic `_attempt_id(seed,index)` with random episode-scoped
   capabilities.
7. Replace the shared mutable JSONL with independent solver, broker, resolver,
   and evaluator audit chains. Each record contains `sequence`,
   `previous_record_sha256`, and `record_sha256`; finalize each chain with a
   signed root and create-exclusive file.
8. Revalidate the exact current authority store/service on every broker
   operation and at evaluation, not only once before `run_agent`.
9. Derive three stage manifests from the existing all-stage design. Never mount
   the existing combined manifest into solver or proposer containers. Sign all
   stage payloads and encrypt hidden.
10. Replace raw `sha256(task_id)` public receipts with opaque HMAC episode refs.
11. Make outputs canonical and signed; retain content-free committed aggregates
    and keep restricted raw material external.
12. Add the isolation integration suite before another factorial run. After
    this changes code/tool/evaluator/manifest hashes, rerun all 12 P0 episodes;
    do not reuse the existing P0 as a gate.

Suggested minimal module layout:

```text
research/trace-intelligence/nl2sql_capabilities/
  dto.py                 # strict schemas/dataclasses/JCS
  stage_sealer.py        # offline split/sign/encrypt
  resolverd.py           # source + two capability-specific APIs
  solverd.py             # model/tool loop only
  brokerd.py             # governed candidate tools + live epoch checks
  attempt_store.py       # create-exclusive blobs, ledgers, reader
  evaluatord.py          # gold-only execution + stored-result compare
  supervisor.py          # sandbox lifecycle + fixed-model proxy
  otel_adapter.py        # safe spans and canonical events
  schemas/*.json
  tests/
```

## Acceptance decision

### Implementation evidence — 2026-07-30 checkpoint

The first implementation now includes the strict solver/broker DTOs,
append-once attempt chain, source-neutral broker, full-result evaluator,
separate supervisor/evaluator resolver methods, signed/encrypted stage
artifacts, a fresh-process inherited-FD solver harness, and a frozen OCI
profile. The capability suite passes 61/61 tests.

The frozen OCI profile also passed 21 real enforcement/protocol gates on
Colima Linux `6.8.0-47-generic`/aarch64 with `runc 1.1.14`. That run found two
defects missed by the config-shape tests:

- preserved-FD startup requires the read-only `fstatfs` syscall; and
- `RLIMIT_NPROC` is counted across all host threads sharing the real UID, so a
  common container UID collided with CoreDNS. The profile now relies on the
  scoped pids cgroup plus seccomp's process-creation denial instead.

A separate real PostgreSQL 16 slice passed distinct constrained candidate and
evaluator roles/application names, write denial, three calls per lane, actual
database snapshot stability, deliberate mismatch detection, and cleanup.

These results do **not** close this design. The tested Python rootfs is not
minimal, UID 65532 is not episode-specific, only one OCI episode/kernel/runtime
was exercised, resolver peer roles are abstract rather than `SO_PEERCRED`,
PostgreSQL counts are coordinator receipts rather than signed independent
server/broker evidence, and crash/OTel/complete 27-gate proofs remain open.

This design meets the bead only after it is implemented and verified. The
present code still does not meet the full capability-isolation acceptance
criteria, despite correctly avoiding candidate re-execution and passing the
bounded component/runtime slices above.

The minimum credible release gate is:

1. signed split stage manifests and hidden ciphertext;
2. OCI-isolated solver with only the redacted DTO and two inherited Unix FDs;
3. broker-owned append-once full-result evidence and signed submission;
4. evaluator-only gold resolution and gold execution;
5. all 27 isolation/conformance tests passing;
6. a fresh 12/12 P0 under final hashes with zero unauthorized observations and
   proof that candidate execution count remains one through evaluation; and
7. a signed aggregate binding every required component hash.

Until then, P1 and hidden tests should remain sealed.
