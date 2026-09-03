#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

echo "[1/4] branding audit"
scripts/audit-fork-branding.sh >/tmp/frankengate-branding-audit.txt
# Compatibility references are expected, but direct upstream product URLs in
# fork-owned UI/docs are not. Historical Helm index entries are reviewed by
# the branding bead and are excluded from this hard gate for now.
if rg -n -i 'getbifrost\.ai|docs\.getbifrost\.ai' README.md CHANGELOG.md docs/pricing-sync.md docs/models-catalog/pricing-loader.js ui/README.md helm-charts/bifrost/README.md helm-charts/bifrost/templates; then
  echo "fork-owned surfaces still contain upstream product URLs" >&2
  exit 1
fi

echo "[2/4] Helm rendering"
helm template frankengate helm-charts/bifrost >/tmp/frankengate-helm.yaml
rg -q 'raw\.githubusercontent\.com/pierretokns/frankengate/.*/transports/config\.schema\.json' /tmp/frankengate-helm.yaml

echo "[3/4] Go analytics contract"
(cd analytics-go && GOWORK=off go test ./...)
(cd analytics-go && GOWORK=off go run ./cmd/frankengate-analytics --check)

echo "[4/4] pricing mirror contract"
(cd scripts/pricing-sync && GOWORK=off CGO_ENABLED=0 GOCACHE="${GOCACHE:-/tmp/frankengate-go-cache}" go test ./...)

echo "FrankenGate local release gates passed"
