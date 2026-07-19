# Provenance and Redistribution Policy

Status: launch gate policy for `bif-kyy.1.3`.

This repository is an Apache-2.0 fork derived from Bifrost AI Gateway. Redistribution must retain the Apache-2.0 license, retained notices, and clear modification notices. The Apache-2.0 trademark clause does not grant permission to use protected names or marks except as needed to describe origin and reproduce NOTICE content.

## Required Release Gate Behavior

The provenance gate in `scripts/verify-provenance.sh` is the required no-secret check for pull requests and release candidates. It must fail when:

- `LICENSE` or `NOTICE` is missing.
- `NOTICE` does not retain Bifrost attribution and fork/non-affiliation language.
- A mechanically discovered distribution, build, package, CI, or release input is missing from `provenance/file-ledger.tsv`.
- A ledger entry lacks origin, license, attribution, or a required modification notice location.
- A protected mark appears in a distribution surface without a record in `provenance/protected-marks.tsv`.
- A protected mark record requires approval but has no approval reference.
- A competitor import is declared without explicit human approval.
- Bundled notice inventory entries are incomplete.
- Dependency manifests or lockfiles are missing from `provenance/dependency-license-sources.tsv`.
- A dependency row lacks an offline closure inventory artifact or SBOM artifact.
- A dependency closure artifact records `unresolved` or `denied` status.
- A dependency closure artifact uses `go.sum` as license evidence.
- Artifact bundle rows are missing machine-checkable NOTICE, license text, SBOM, or dependency inventory inputs.

The gate is intentionally deterministic shell. It does not need secrets, external package downloads, or network calls.

## Prominent Modification Notices

Files that materially change upstream user-visible identity, legal attribution, packaging metadata, or release behavior must set `modification_notice_required=yes` in `provenance/file-ledger.tsv` and point at the notice location. For now, `NOTICE` is the canonical repository-level modification notice. If a future artifact has a separate notice file, add that file to this directory and reference it in the ledger.

Examples requiring a prominent notice:

- README or package metadata that changes public identity.
- NOTICE/license files.
- Release packaging that changes image names, chart names, binary names, or public artifact coordinates.
- Any imported file not directly derived from Apache-2.0 Bifrost source.

## Protected Marks

`Bifrost`, `Maxim`, `Maxim HQ`, Maxim domains, and related names must only be used for attribution, origin description, compatibility, or retained upstream notices unless a human approval reference is recorded. Do not present the fork as affiliated with or endorsed by Maxim AI or Bifrost maintainers.

## Competitor Imports

Do not import, transliterate, or mechanically port competitor source, examples, schemas, screenshots, docs prose, tests, or generated artifacts without file-level provenance review and a human approval reference in `provenance/competitor-imports.tsv`. Public documentation and competitor behavior may inform clean-room requirements only.

## Bundled Notices

Release artifacts must include or preserve notices for bundled source and package surfaces. `provenance/bundled-notices.tsv` records the current required notice inventory. New bundled third-party source, base images with required notices, or generated artifacts must be added before release.

## SBOM and Dependency License Scanning

`provenance/dependency-license-sources.tsv` lists dependency manifests, lockfiles when present, the required offline closure inventory artifact, and the required SBOM artifact. A checksum file such as `go.sum` is never license evidence; it is only a pinned module input. Each closure artifact must use this header:

```text
dependency	version	license	status	evidence	approval_ref
```

`status` is one of `resolved`, `unresolved`, or `denied`. Only `resolved` passes the release gate. If license resolution needs a separate tool, network access, or human review, record `unresolved`, name the exact missing artifact in `provenance/dependency-license-sources.tsv`, and keep release closed until the artifact exists.

`provenance/artifact-bundles.tsv` records release artifact bundle inputs. Every artifact row must point at an existing NOTICE file, license text, SBOM, and dependency inventory before publication.
