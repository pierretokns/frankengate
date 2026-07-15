# Provenance and Redistribution Policy

Status: launch gate policy for `bif-kyy.1.3`.

This repository is an Apache-2.0 fork derived from Bifrost AI Gateway. Redistribution must retain the Apache-2.0 license, retained notices, and clear modification notices. The Apache-2.0 trademark clause does not grant permission to use protected names or marks except as needed to describe origin and reproduce NOTICE content.

## Required Release Gate Behavior

The provenance gate in `scripts/verify-provenance.sh` is the required no-secret check for pull requests and release candidates. It must fail when:

- `LICENSE` or `NOTICE` is missing.
- `NOTICE` does not retain Bifrost attribution and fork/non-affiliation language.
- A declared distribution surface is missing from `provenance/file-ledger.tsv`.
- A ledger entry lacks origin, license, attribution, or a required modification notice location.
- A protected mark appears in a distribution surface without a record in `provenance/protected-marks.tsv`.
- A protected mark record requires approval but has no approval reference.
- A competitor import is declared without explicit human approval.
- Bundled notice inventory entries are incomplete.
- Dependency/SBOM source manifests are missing or lockfiles contain denied license patterns without approval.

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

`provenance/dependency-license-sources.tsv` lists manifests and lockfiles that seed SBOM generation and deterministic dependency-license checks. The current gate validates that every listed manifest exists and scans text lockfiles for denied license patterns. Future release gates may add richer SBOM generation, but they must stay secret-free and must not bypass this baseline inventory.
