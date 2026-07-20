#!/usr/bin/env bash
set -euo pipefail

# Fork-owned branding audit. Compatibility identifiers are reported separately
# so a future breaking-version rename can reduce them deliberately.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

scope=(README.md CHANGELOG.md docs ui .github helm-charts)
upstream='getbifrost\.ai|docs\.getbifrost\.ai|github\.com/maximhq/bifrost|maximhq/bifrost-benchmarking|www\.getmaxim\.ai/bifrost'
compat='github\.com/maximhq/bifrost/|transports/bifrost-http|BIFROST_|x-bf-|sk-bf-|bifrost\.'

echo "Fork-facing upstream references:"
if ! rg -n -i "$upstream" "${scope[@]}" --glob '!**/SKILL.md'; then
  echo "  none"
fi

echo
echo "Inherited compatibility references (review, do not blindly remove):"
if ! rg -n -i "$compat" "${scope[@]}" --glob '!**/SKILL.md'; then
  echo "  none"
fi
