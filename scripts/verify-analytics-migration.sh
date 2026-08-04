#!/usr/bin/env bash
set -euo pipefail

# Apply and verify the Rust analytics schema against the local Kubernetes
# PostgreSQL/Aurora emulator. This intentionally uses kubectl exec so the
# verifier exercises the same database boundary as the runtime harness.
NAMESPACE="${NAMESPACE:-frankengate-test}"
POD="${POD:-postgres-0}"
DB_USER="${DB_USER:-frankengate}"
DB_NAME="${DB_NAME:-frankengate}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATION="$ROOT/analytics-rs/migrations/001_analytics_contract.sql"

[[ -r "$MIGRATION" ]] || { echo "migration not found: $MIGRATION" >&2; exit 2; }
command -v kubectl >/dev/null || { echo "kubectl is required" >&2; exit 2; }

kubectl -n "$NAMESPACE" exec -i "$POD" -- psql \
  -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$MIGRATION" >/dev/null

constraints="$(kubectl -n "$NAMESPACE" exec "$POD" -- psql -At \
  -U "$DB_USER" -d "$DB_NAME" -c "
    select conname
    from pg_constraint
    where conrelid = 'frankengate_analytics.jobs'::regclass
      and conname in ('jobs_lease_projection_consistency', 'jobs_terminal_error_consistency')
    order by conname;")"

expected=$'jobs_lease_projection_consistency\njobs_terminal_error_consistency'
if [[ "$constraints" != "$expected" ]]; then
  printf 'unexpected analytics job constraints:\n%s\n' "$constraints" >&2
  exit 1
fi

view_exists="$(kubectl -n "$NAMESPACE" exec "$POD" -- psql -At \
  -U "$DB_USER" -d "$DB_NAME" -c "
    select count(*)
    from pg_views
    where schemaname = 'frankengate_analytics'
      and viewname = 'job_queue_stats';")"
if [[ "$view_exists" != "1" ]]; then
  echo "analytics queue stats view is missing" >&2
  exit 1
fi

echo "analytics migration and lease invariants verified in $NAMESPACE/$POD"
