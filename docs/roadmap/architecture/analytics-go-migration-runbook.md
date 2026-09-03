# FrankenGate Analytics Go migration runbook

Status: beta implementation contract

## Repository and deployment decision

The Go analytics binary lives in this repository under `analytics-go/` because
it must evolve with FrankenGate's canonical trajectory, privacy receipts,
evidence envelope, ClickHouse projection, and rubric contracts. It is a
separate Go module and deployable artifact, not a package linked into
`bifrost-http`.

All Autoeval features land in Go. The analytics service is a separate deployable
artifact and is not linked into `bifrost-http` or the inference availability
path.

## Tonight's publishable slice

The beta binary provides:

- `--check`, which validates that the binary and contract code start without
  ClickHouse;
- `/healthz` and `/readyz`;
- `POST /v1/traces`, which admits canonical traces after privacy, authorization,
  source revision/digest, deletion, provenance, silent-loss, parent-edge, and
  secret checks;
- `POST /v1/evaluations`, which validates task-family rubric weights and emits
  structured action-value judgments, hard violations, or abstention;
- `GET /v1/reports/evaluations`, which returns tenant-scoped counts, mean value,
  abstention/violation counts, and a value histogram; and
- ClickHouse migrations and append-only fact insertion for runs, events, and
  judgments.

This is enough to test a sanitized enterprise cohort. The release is labelled
`beta-trace-eval`; it is the direct replacement for the never-adopted Rust
runtime, not a dual-run migration.

## Start a local beta

```bash
make analytics-test
make analytics-build
./tmp/frankengate-analytics --check
make analytics-image-verify # requires Docker access to the configured registry
make analytics-package
make analytics-package-matrix

# ClickHouse is required for service mode.
CLICKHOUSE_ADDR=127.0.0.1:8123 \
CLICKHOUSE_DATABASE=frankengate_analytics \
ANALYTICS_WORKER_TOKEN=local-only-token \
./tmp/frankengate-analytics
```

`analytics-package` produces a platform-named tarball under `dist/` with the
binary, fixture, example rubric, request, README, and a SHA-256 checksum.
`analytics-package-matrix` produces macOS arm64, Linux amd64, and Linux arm64
tarballs plus one aggregate SHA-256 manifest. The tarballs are the beta release
artifacts; the manual GHCR workflow publishes the matching container image
when credentials and a tag are supplied.

`analytics-image-verify` builds `analytics-go/Dockerfile`, runs the binary's
dependency-free contract check and version command, and verifies that the
distroless image runs as `nonroot:nonroot`. The ClickHouse-backed service smoke
test remains in `analytics-integration`, where a disposable database is
available; the image check deliberately does not bake a database into the
container contract.

For each request, send `Authorization: Bearer $ANALYTICS_WORKER_TOKEN` and
`X-Tenant-ID`. The request body tenant must match the header. Never point the
beta at raw production tables: export an authorized canonical cohort with
source, privacy, deletion, and loss receipts first.

The checked-in fixture at
`analytics-go/examples/fixtures/enterprise-sanitized-trace.json` demonstrates
the accepted shape. It contains bounded placeholder content only and is not a
claim that regex redaction is sufficient for a corporate privacy boundary.

## Trace admission and sanitization

Durable rows contain metadata, event lineage, and digests. They do not contain
raw user prompts, tool arguments, tool results, KB text, skill text, model prose,
secrets, or private chain-of-thought. The adapter must retain:

- tool proposal/authorization/execution/result lifecycle;
- skill lookup/load/application/version;
- KB query, retrieved-item/citation, snapshot, and freshness;
- retries, fallback attempts, branches, joins, delegation, and cancellation;
- model, harness, skill, and KB revisions; and
- observed state deltas and terminal outcomes.

Missing or reconstructed facts are explicit. Silent projection loss rejects
admission. A secret-like value rejects admission. An email-like value is
redacted before its digest is computed. This implementation is a defense in
depth check, not a replacement for an enterprise DLP/redaction service; the
upstream source adapter must perform classification and provide the privacy
receipt.

## Rubric and scoring contract

Rubrics are task-family-specific. Each rubric defines the terminal success
predicate, permitted action grammar, hard safety/authorization constraints,
weighted dimensions, evidence policy, and abstention rules. The default action
value dimensions are:

- goal progress;
- precondition correctness;
- information gain;
- risk and recoverability; and
- unnecessary cost.

The score is ordinal 0–4. Hard violations force 0. Insufficient state forces
abstention. The evaluator records confidence, evidence event IDs, and bounded
reason codes. It never scores prose resemblance to the incumbent.

Skill scoring asks whether a skill is applicable, authorized, grounded in
visible state, and task-progressing. Invocation alone earns no credit.
Retrieval/KB scoring asks whether the query is specific, the result is relevant
and fresh, citations support the action, and stale/unobserved evidence is not
treated as fact.

Use the calibration pack before a corporate run: gold cases, minimal pairs,
known-good/no-op/random/bad mutants, missingness, prompt injection, skill
ablations, KB snapshot changes, and equivalent actions encoded by different
harnesses. Publish coverage, abstention, calibration, executed-reference
agreement, ranking correlation, regret, and cost per slice.

## Beta release gates

1. Go accepts/rejects canonical fixtures with explicit privacy, deletion, and
   loss receipts.
2. ClickHouse fact rows have source, privacy, loss, case-pack, and deletion
   lineage keys.
3. Enterprise users can reproduce the report from the published binary/image
   and versioned fixture/rubric contracts.
4. The enterprise campaign reports model/harness/skill/KB holdouts, executed
   references, calibration, abstention, leakage, and cost.
