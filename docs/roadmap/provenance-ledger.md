# Provenance Ledger

This ledger is a release gate for the fork. Add one row before importing or closely
adapting any external code, schema, test vector, algorithm expression, documentation,
asset, or generated artifact. "Inspired by" is not a substitute for file-level review.

| Component | Origin and revision | Exact source paths | License/file headers | Use in fork | Modifications | Reviewer/date | Status |
|---|---|---|---|---|---|---|---|
| Bifrost OSS baseline | `https://github.com/maximhq/bifrost` at `596679bc03b54a64838f01e7e8ad094ee6b9bd5e` | Entire initial tree | Apache-2.0 `LICENSE`; audit `NOTICE` before release | Fork baseline | Pending | Pending | Baseline |

Allowed statuses: `candidate`, `approved`, `rejected`, `clean-room-requirement`, and
`baseline`. An approved row must identify exact paths and a pinned revision. A
clean-room requirement row may cite a public protocol or behavioral page but must not
copy protected prose, screenshots, or unavailable implementation.

## Release checklist

- [ ] Every non-baseline imported/adapted component has an approved ledger row.
- [ ] Applicable upstream notices and modification notices are present.
- [ ] Dependency license scan reviewed, with exceptions resolved.
- [ ] SBOM matches each binary/image/chart artifact.
- [ ] Source and binary license bundles verified.
- [ ] Project naming and compatibility claims passed trademark review.
