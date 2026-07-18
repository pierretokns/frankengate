#!/usr/bin/env bash
set -euo pipefail

# Produce a deterministic, reviewable inventory of upstream identity references.
# This intentionally does not rewrite files: legal attribution, compatibility
# identifiers, and historical references need separate human decisions.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
usage() {
  cat <<'EOF'
usage: scripts/branding-inventory.sh [OUTPUT.tsv]

Generate a deterministic, non-mutating inventory of upstream identity
references. The default output is branding-inventory.tsv at the repository
root.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ "$#" -gt 1 ]]; then
  echo "error: expected at most one output path" >&2
  usage >&2
  exit 2
fi
OUT="${1:-$ROOT/branding-inventory.tsv}"
mkdir -p "$(dirname "$OUT")"
printf 'path\tline\tmatch\tclassification\towner\tdestination\n' >"$OUT"

git -C "$ROOT" grep -n -I -i -E 'bifrost|maximhq/bifrost|ghcr.io/.*/bifrost|npmjs.com/.*/bifrost' -- \
  ':!branding-inventory.tsv' ':!*.lock' 2>/dev/null |
awk -F: '
  function classify(path, text) {
    low=tolower(path " " text)
    if (low ~ /notice|license|copyright|attribution|bundled-notices/) return "retain-attribution"
    if (low ~ /compat|migration|upstream|bifrostcontext|module|import/) return "retain-compatibility"
    if (low ~ /changelog|history|roadmap|archive|historical/) return "historical-only"
    if (low ~ /readme|docs|helm|workflow|ui|website|marketing/) return "migrate"
    return "review"
  }
  {
    path=$1; line=$2; text=$0
    sub(/^[^:]*:[^:]*:/, "", text)
    gsub(/\t/, " ", text); gsub(/\r/, "", text)
    printf "%s\t%s\t%s\t%s\tbranding-review\t%s\n", path, line, text, classify(path,text), (classify(path,text)=="migrate" ? "Frankengate-owned name/URL" : "human decision")
  }
' | LC_ALL=C sort -t $'\t' -k1,1 -k2,2n -k3,3 >>"$OUT"

test -s "$OUT"
printf 'wrote %s (%s rows)\n' "$OUT" "$(($(wc -l <"$OUT") - 1))"
