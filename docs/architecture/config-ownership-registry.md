# Configuration Ownership Registry

This registry pins the target control-plane contract for the PostgreSQL-authoritative configuration program:

- `target_source_of_truth` is `database`.
- Every `ConfigData` JSON field, every `transports/config.schema.json` leaf, and every `helm-charts/bifrost/values.schema.json` leaf resolves to exactly one authority class.
- The expanded snapshot records schema/default/nil/secret/identity semantics for each field.

## Authority Classes

| Class | Contract |
| --- | --- |
| `bootstrap_only` | Deployment, environment, or process bootstrap owns the field. It is not mutable control-plane state and is read before or outside the database authority path. |
| `db_authoritative_hot_reload` | PostgreSQL is durable authority. Running pods must converge through an API reload path or the config changefeed without a process restart. |
| `db_authoritative_restart_required` | PostgreSQL is durable authority, but the field changes process wiring or external store/client construction and takes effect only after pod restart. |

## Files

| File | Purpose |
| --- | --- |
| `config-ownership-registry.rules.json` | Compact source registry. Rules are intentionally broad by owning section, with explicit exceptions for client fields that currently set restart-required flags. |
| `config-ownership-registry.snapshot.json` | Generated expanded registry. Do not hand edit. |
| `scripts/verify-config-ownership-registry.mjs` | Expands Go `ConfigData`, the transport config schema, and the Helm values schema; verifies every field matches exactly one rule; verifies the snapshot is current. |

## Current Coverage

| Surface | Fields | Bootstrap-only | DB hot reload | DB restart-required |
| --- | ---: | ---: | ---: | ---: |
| `ConfigData` | 19 | 5 | 10 | 4 |
| `transports/config.schema.json` | 3,668 | 68 | 3,474 | 126 |
| `helm-charts/bifrost/values.schema.json` | 979 | 358 | 615 | 6 |

## Evidence Boundary

The registry uses the current source as evidence:

- `transports/bifrost-http/lib/config.go` for `ConfigData`, startup reconciliation, store initialization, provider/MCP/governance/plugin loading, framework sync config, feature flags, and alerting sync.
- `transports/bifrost-http/handlers/config.go` for the concrete client settings that are currently restart-required.
- `transports/bifrost-http/handlers/providers.go`, `mcp.go`, `governance.go`, `plugins.go`, and `alerting.go` for DB-backed live mutation paths.
- `helm-charts/bifrost/templates/_helpers.tpl` and `helm-charts/bifrost/values.schema.json` for the chart field surface and rendered config mapping.

WP0 established the existing split-brain behavior and the program goal: PostgreSQL must become the sole durable control-plane authority. This registry is the handoff contract for later work packages. It does not implement the changefeed or remove config.json serving reads by itself.

## Verification

Run:

```bash
node scripts/verify-config-ownership-registry.mjs
```

Regenerate after schema or Helm field changes:

```bash
node scripts/verify-config-ownership-registry.mjs --write
```
