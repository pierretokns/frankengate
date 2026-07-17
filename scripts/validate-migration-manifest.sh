#!/usr/bin/env bash
set -euo pipefail

# Structural linter for the migration compatibility contract.  This is
# intentionally dependency-free: it validates the contract that release and
# deployment tooling can rely on, without pretending that prose is a live
# migration executor.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${1:-$ROOT/docs/roadmap/architecture/migration-compatibility-manifest.md}"

[[ -f "$MANIFEST" ]] || { echo "missing migration manifest: $MANIFEST" >&2; exit 2; }

required_headings=(
  "Current Source Facts"
  "Migration ID Namespace"
  "Module Dependency Manifest"
  "Compatibility Classes"
  "N/N+1/Rollback Matrix"
  "Predeploy Kubernetes Migration Job"
  "Mixed-Version Compatibility"
  "Startup Failure Oracles"
  "Rollback Failure Oracles"
  "Validation Gates"
  "Assumptions"
  "Open Questions"
)

for heading in "${required_headings[@]}"; do
  if ! grep -Fqx "## $heading" "$MANIFEST"; then
    echo "missing required heading: $heading" >&2
    exit 1
  fi
done

# New IDs must use the documented namespace/timestamp shape.  Ignore examples
# explicitly marked as legacy; bare IDs are only permitted in the legacy table.
if grep -nE '^\s*[-*] id: "[^"]+"' "$MANIFEST" | grep -vE '/[0-9]{14}-[a-z0-9][a-z0-9-]*"' >/tmp/migration-manifest-invalid.$$; then
  cat /tmp/migration-manifest-invalid.$$ >&2
  rm -f /tmp/migration-manifest-invalid.$$
  exit 1
fi
rm -f /tmp/migration-manifest-invalid.$$

echo "migration compatibility manifest valid: $MANIFEST"
