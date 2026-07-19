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

## Offline Go module closure

Go generation consumes a prehydrated JSON lock; generation never invokes
`go list`, `go mod download`, or the network. Use `--ecosystem go` with
`--go-lock`, `--manifest`, `--go-sum`, `--source-root`, and `--evidence-root`.
The lock binds the exact manifest and go.sum hashes and contains a versioned
root plus every selected module, Go Sum/GoModSum, directness, optional original
to effective replacement, source archive path/SHA-256, licenses, and evidence.
`GenerateGoFiles` verifies every bounded file; `GenerateGo` is structural-only.

```json
{
  "schemaVersion": 1,
  "moduleCount": 2,
  "selectedModulesSha256": "<canonical-closure-sha256>",
  "manifest": {"path": "go.mod", "sha256": "<sha256>"},
  "goSum": {"path": "go.sum", "sha256": "<sha256>"},
  "root": {
    "path": "example.com/root",
    "version": "v1.0.0",
    "sourceArchive": {"path": "root.zip", "sha256": "<sha256>"},
    "licenseDeclared": "Apache-2.0",
    "licenseConcluded": "Apache-2.0",
    "evidence": [{"path": "root-LICENSE", "sha256": "<sha256>"}]
  },
  "modules": [{
    "path": "example.com/original",
    "version": "v1.2.0",
    "indirect": false,
    "sum": "h1:<base64-sha256>",
    "goModSum": "h1:<base64-sha256>",
    "replacement": {"path": "example.com/fork", "version": "v1.2.1"},
    "sourceArchive": {"path": "fork-v1.2.1.zip", "sha256": "<sha256>"},
    "licenseDeclared": "MIT",
    "licenseConcluded": "MIT",
    "evidence": [{"path": "fork-LICENSE", "sha256": "<sha256>"}]
  }]
}
```
