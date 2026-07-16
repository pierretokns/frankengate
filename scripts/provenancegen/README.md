# provenancegen

This first provenance-generator slice converts one npm `package-lock.json`
(`lockfileVersion: 3`) into a deterministic dependency inventory and SPDX 2.3
JSON document. It performs no network access.

Every non-link root or dependency `name`/`version` pair must have one matching
entry in the evidence input. Extra, missing, duplicate, unhashed, `NONE`, or
`NOASSERTION` evidence fails generation.

`licenseDeclared` is optional and defaults to SPDX `NOASSERTION`; it is never
inferred from `licenseConcluded`. `Generate` validates only supplied bytes and
is intended for structural unit tests. The CLI and `GenerateFiles` are the
trusted file boundary: they open every evidence path below `--evidence-root`
(default: the evidence JSON directory), reject traversal and symlink escapes,
compute SHA-256, and require an exact declared-hash match.

```json
{
  "schemaVersion": 1,
  "packages": [
    {
      "name": "example",
      "version": "1.2.3",
      "licenseConcluded": "MIT",
      "licenseDeclared": "MIT",
      "evidence": [
        {
          "path": "LICENSE",
          "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        }
      ]
    }
  ]
}
```

Run with the parent workspace disabled because this deliberately isolated tool
is not part of `go.work`:

```sh
GOWORK=off go run . \
  --package-json package.json \
  --package-lock package-lock.json \
  --evidence evidence.json \
  --evidence-root license-evidence \
  --inventory-out inventory.tsv \
  --spdx-out sbom.spdx.json \
  --created 2026-07-15T00:00:00Z
```
