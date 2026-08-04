"""Pinned authority-epoch resolution for governed Defog experiments.

Presence of an epoch reference is insufficient: the reference must equal the
current epoch for the exact database/scope/subject binding. This local store is
a reproducibility and fail-closed conformance mechanism, not a production
authorization service or cryptographic signer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-static-authority-epoch-v1"


class AuthorityEpochError(RuntimeError):
    """An authority binding is absent, ambiguous, incomplete, or stale."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class AuthorityBinding:
    database: str
    governance_scope: str
    user_id: str
    team_id: str
    virtual_key_id: str


@dataclass(frozen=True)
class AuthorityReceipt:
    binding_sha256: str
    epoch_ref_sha256: str
    authority_snapshot_sha256: str
    authority_valid: bool = True


class StaticAuthorityEpochStore:
    """Resolve the current epoch for one exact governed identity binding."""

    def __init__(
        self,
        *,
        records: dict[AuthorityBinding, str],
        snapshot_sha256: str,
    ) -> None:
        self._records = records
        self.snapshot_sha256 = snapshot_sha256

    @classmethod
    def from_path(cls, path: Path) -> "StaticAuthorityEpochStore":
        raw = path.read_bytes()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AuthorityEpochError(
                "authority snapshot is invalid JSON"
            ) from exc
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise AuthorityEpochError("unexpected authority snapshot schema")
        records: dict[AuthorityBinding, str] = {}
        for item in payload.get("bindings", []):
            required = (
                "database",
                "governance_scope",
                "user_id",
                "team_id",
                "virtual_key_id",
                "current_authorization_epoch_ref",
            )
            if any(
                not isinstance(item.get(field), str) or not item[field]
                for field in required
            ):
                raise AuthorityEpochError(
                    "authority binding has missing or empty fields"
                )
            binding = AuthorityBinding(
                database=item["database"],
                governance_scope=item["governance_scope"],
                user_id=item["user_id"],
                team_id=item["team_id"],
                virtual_key_id=item["virtual_key_id"],
            )
            if binding in records:
                raise AuthorityEpochError(
                    f"duplicate authority binding: {binding}"
                )
            records[binding] = item["current_authorization_epoch_ref"]
        if not records:
            raise AuthorityEpochError("authority snapshot has no bindings")
        return cls(records=records, snapshot_sha256=sha256_bytes(raw))

    def validate(
        self,
        *,
        database: str,
        governance_scope: str | None,
        authorization_epoch_ref: str | None,
        user_id: str | None,
        team_id: str | None,
        virtual_key_id: str | None,
    ) -> AuthorityReceipt:
        supplied = (
            governance_scope,
            authorization_epoch_ref,
            user_id,
            team_id,
            virtual_key_id,
        )
        if any(not isinstance(value, str) or not value for value in supplied):
            raise AuthorityEpochError(
                "governed request has incomplete authority context"
            )
        binding = AuthorityBinding(
            database=database,
            governance_scope=governance_scope,
            user_id=user_id,
            team_id=team_id,
            virtual_key_id=virtual_key_id,
        )
        current = self._records.get(binding)
        if current is None:
            raise AuthorityEpochError(
                "authority binding is not present in the current snapshot"
            )
        if authorization_epoch_ref != current:
            raise AuthorityEpochError(
                "authorization epoch reference is stale or unknown"
            )
        return AuthorityReceipt(
            binding_sha256=sha256_bytes(canonical_json_bytes(asdict(binding))),
            epoch_ref_sha256=sha256_bytes(current.encode("utf-8")),
            authority_snapshot_sha256=self.snapshot_sha256,
        )
