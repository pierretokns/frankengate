# DataClaw MRiabov export integrity audit

## Dataset inventory

The pinned `MRiabov/dataclaw-march-26` card claims an MIT-licensed,
environment-scrubbed export of 775 Codex/Gemini sessions across eight projects.
The file was downloaded locally at revision
`3fcd9d92ca9eaf2d5b8377a7c505626880249171` and was never committed or sent to
an external model.

## Integrity result

| Check | Result |
|---|---:|
| Physical JSONL rows | 775 |
| Raw-valid JSON rows | 9 |
| Raw-valid rows with `session_id` | 9 |
| `[REDACTED_ENV_VALUE]` occurrences | 14,239,183 |
| Rows parseable after deleting the token | 104 |
| Salvaged rows with required top-level fields | 104 |

The scrubber inserts its marker into JSON numbers, timestamps, UUIDs, and
tool/code strings. For example, numeric fields can become syntactically empty
or partially redacted, and timestamps and code snippets lose characters. Merely
deleting the marker restores syntax for a minority of rows but cannot recover
the missing values or establish that the repaired row means what the original
trace meant.

## Decision

This export is **inventory-only**, not an empirical trace corpus. Do not use it
for embeddings, alias mining, hard-negative construction, skill discovery,
cross-user retrieval, or outcome benchmarking. Request a parseable export or a
loss-aware structured format from the publisher first. The correct adapter
should reject the file at ingestion and emit a content-free integrity receipt,
not silently coerce the damaged rows.

Receipt: [`dataclaw-mriabov-export-integrity-2026-08-02.json`](../results/dataclaw-mriabov-export-integrity-2026-08-02.json)

Audit implementation: [`dataclaw_export_integrity_audit.rb`](../../dataclaw_export_integrity_audit.rb)
