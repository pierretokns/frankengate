# Changelog

All notable FrankenGate changes are recorded here from the fork's git history.
Version entries describe compatibility risk explicitly; release automation must
attach the matching immutable tag and artifact digests.

## Unreleased

### Fixed

- `/readyz` now fails closed until the VK invalidation and principal-authority
  consumers have completed bootstrap and remain fresh; `/livez` remains process-only.
- Release vulnerability checks compile `govulncheck` once per job instead of
  recompiling it for every Go module.

### Known limitations

- Governance request admission still uses pod-local budget counters; atomic
  cross-replica PostgreSQL reservations are not shipped yet.
- Synchronization metrics and a complete external Redis contract remain planned.

## 0.3.9

This tag contains the release candidate at `0fb398454364426a23fb643f78c4bb101c069aaf`.

### Compatibility

- Patch-level release candidate. No config schema migration is claimed by this
  entry; verify the chart and image digests before promotion.
- The Helm replacement proof exercises three replicas, upgrade, rollback, and
  re-upgrade with a retained virtual key. Publication evidence is authoritative
  only when the corresponding GitHub Actions run is successful.

### Verification scope

- Provenance and redistribution-policy self-tests.
- Multi-module compile, race, vet, vulnerability, chart, SBOM, and attestation
  gates as defined by the fork-owned workflows.

