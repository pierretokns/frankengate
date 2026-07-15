# ADR: Virtual Key Fingerprint And Pepper Rotation

Status: Accepted for bif-kyy.3.4 implementation

Date: 2026-07-15

Scope: Internal enterprise Bifrost deployment on Kubernetes with Aurora PostgreSQL as the durable control-plane authority.

## Decision

Virtual keys are identified by a tenant-scoped indexed HMAC fingerprint and verified by a separate tenant-scoped HMAC verification digest. Bifrost must never store raw virtual keys and must never derive an indexed lookup value from an unkeyed hash such as `sha256(raw_key)`.

The launch record shape is:

- `tenant_id`
- `algorithm`, initially `hmac-sha256.v1`
- `fingerprint`, an indexed HMAC-SHA256 value for lookup
- `fingerprint_pepper_version`
- `verification_digest`, a non-indexed HMAC-SHA256 value for constant-time verification
- `verification_pepper_version`

The HMAC input is domain separated, length-prefixed, and includes tenant id, purpose, and raw key material. The purposes are separate: `fingerprint` for indexed lookup and `verification` for key verification. Pepper material is resolved by tenant, purpose, and version from KMS or the enterprise secret authority. Pepper versions are persisted; pepper material is not.

Resolved pepper material must be at least 32 bytes. When a specific pepper version is requested, the resolver-returned version must exactly match the requested version. A mismatch is a fail-closed resolver contract error, not an instruction to silently use the returned version.

## Rationale

An indexed value is needed for fast virtual-key lookup across pods and Aurora rows, but an indexed value that is either raw key material or an unkeyed digest is a credential-equivalent secret. Tenant-scoped HMAC keeps lookup deterministic for one tenant while preventing cross-tenant correlation and offline lookup if Aurora is copied without peppers.

The verification digest is deliberately separate from the indexed fingerprint. This prevents the database index from also being the verifier and allows independent rotation policy for lookup and verification peppers.

## Verification

Verification is:

1. Validate the stored record: supported algorithm, non-empty tenant, pepper versions, and well-formed HMAC values.
2. Resolve the stored fingerprint pepper by tenant, purpose `fingerprint`, and stored fingerprint version.
3. Resolve the stored verification pepper by tenant, purpose `verification`, and stored verification version.
4. Recompute both the indexed fingerprint and the verification digest over the presented raw key.
5. Compare both stored values with the recomputed values using constant-time comparison.
6. If both comparisons succeed, resolve active peppers and report whether the record needs rotation.

Failed verification is not a KMS fallback signal. It is an authentication miss.

## Rotation

Rotation uses dual-read single-write semantics.

- Lookup probes the active fingerprint pepper first.
- During a rotation window, lookup may also probe explicitly configured legacy fingerprint pepper versions.
- New records always write only active fingerprint and verification pepper versions.
- Existing records verify with their stored verification pepper version.
- If an old record verifies successfully and active versions differ, the caller receives a replacement record using active versions.
- The old record is not mutated in memory. Aurora update must be conditional on the previous record version or row revision.

This makes the active write path simple and limits legacy pepper use to the read window.

## KMS Degradation

KMS or pepper-resolution degradation fails closed.

- No new record is created.
- No lookup fingerprint is produced.
- No unkeyed lookup hash is computed.
- Verification cannot succeed unless the required stored pepper version is available.
- Callers should treat the package-level degraded error as an authentication-control failure, not as a cache miss.

The gateway response policy can be tenant-specific, but it must not convert pepper unavailability into fail-open key admission.

## Backup Restore

Aurora backups must preserve `tenant_id`, `algorithm`, both HMAC values, and both pepper version fields. KMS backup and restore procedures must preserve historical pepper versions for the retention period of any virtual-key records that reference them.

Restore procedure:

1. Restore Aurora rows and KMS historical pepper versions for the same tenant boundary.
2. Validate records before serving traffic.
3. For any virtual key reissued by an operator or customer, recompute the record with the explicit stored pepper versions to confirm the restored row.
4. After successful verification, rotate the row forward to active peppers with the normal single-write path.
5. If a historical pepper version cannot be restored, records that depend on it are unrecoverable and must be reissued. Do not recompute them with active peppers and pretend the old indexed value is valid.

Backups must never contain raw virtual keys or exported pepper material in the same trust domain as Aurora data.

## Emergency Pepper Compromise

If a fingerprint or verification pepper is suspected compromised:

1. Mark the compromised pepper version disabled for new writes immediately.
2. Create new active fingerprint and verification pepper versions in KMS.
3. Freeze virtual-key creation if the active write pepper is compromised and new peppers are not yet available.
4. For fingerprint pepper compromise, keep any dual-read legacy window as short as incident command allows; prefer user/customer key re-entry or forced reissue for high-risk tenants.
5. For verification pepper compromise, treat records using that version as suspect. Require reissue or successful re-verification under an approved incident workflow before rotating them forward.
6. Add an emergency deny overlay for affected tenants or key ids when the compromised version cannot be safely read.
7. Audit all lookup and verification attempts involving compromised versions.
8. Close the legacy read window and destroy or quarantine compromised material after migration or reissue.

Rollback must use higher-version peppers. Do not reactivate a compromised pepper as an active write version.

## Operational Requirements

- Unique index: `(tenant_id, algorithm, fingerprint_pepper_version, fingerprint)`.
- Store pepper version fields as immutable audit-relevant metadata.
- Alert on any KMS-degraded key-admission path.
- Alert on records that still reference legacy pepper versions after the approved rotation window.
- Rotation workers must be idempotent and must not require provider traffic to complete migration.
- Logs, traces, and evals may record record ids, versions, and counts, but never raw virtual keys or pepper material.

## Acceptance Tests

- Same raw key under different tenants produces different fingerprint and verification values.
- Fingerprint and verification digest differ for the same tenant/key.
- Old records verify using stored pepper versions and return active-version replacements.
- Lookup emits active fingerprint first and only configured legacy fingerprint versions after that.
- Wrong verification pepper and wrong raw key do not verify.
- Tampered stored fingerprint does not verify, even when the verification digest is intact.
- A resolver-returned pepper version that differs from the requested version fails closed.
- Pepper material shorter than 32 bytes is rejected.
- KMS degradation returns an explicit degraded error and produces no fallback lookup value.
- Malformed records fail validation before admission.

## Consequences

This design preserves a low-overhead lookup path while making key material recovery from Aurora alone impractical. It adds a KMS availability dependency to virtual-key admission; that dependency is intentional and must fail closed because a degraded unkeyed lookup path would become a permanent credential bypass.
