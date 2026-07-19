#!/usr/bin/env bash
set -u

ROOT="."
SELF_TEST=0

usage() {
  cat <<'USAGE'
Usage: scripts/verify-provenance.sh [--root DIR] [--self-test]

Validates provenance ledger coverage, Apache attribution, protected marks,
competitor import approvals, bundled notice inventory, and deterministic
dependency-license scan sources. Runs without secrets or network access.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      [ "$#" -ge 2 ] || { echo "missing value for --root" >&2; exit 2; }
      ROOT="$2"
      shift 2
      ;;
    --self-test)
      SELF_TEST=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_PATH="$0"
FAILURES=0

fail() {
  echo "FAIL: $*" >&2
  FAILURES=$((FAILURES + 1))
}

pass_msg() {
  echo "PASS: $*"
}

sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    return 127
  fi
}

is_data_line() {
  case "$1" in
    ""|\#*) return 1 ;;
    *) return 0 ;;
  esac
}

require_file() {
  local path="$1"
  if [ ! -f "$ROOT/$path" ]; then
    fail "missing required file: $path"
  fi
}

validate_rel_path() {
  local path="$1"
  case "$path" in
    ""|/*|../*|*/../*|*"/.."|"."|"..")
      fail "unsafe or empty relative path: $path"
      return 1
      ;;
  esac
  return 0
}

check_header() {
  local file="$1"
  local expected="$2"
  local actual
  if [ ! -f "$file" ]; then
    fail "missing TSV: ${file#"$ROOT"/}"
    return
  fi
  actual="$(sed -n '1p' "$file")"
  if [ "$actual" != "$expected" ]; then
    fail "bad header in ${file#"$ROOT"/}: expected '$expected', got '$actual'"
  fi
}

check_field_count() {
  local file="$1"
  local expected="$2"
  local label="$3"
  awk -F '\t' -v expected="$expected" -v label="$label" '
    NR == 1 { next }
    $0 == "" || $0 ~ /^#/ { next }
    NF != expected {
      printf("FAIL: %s line %d has %d fields, expected %d\n", label, NR, NF, expected) > "/dev/stderr"
      bad = 1
    }
    END { exit bad ? 1 : 0 }
  ' "$file" || FAILURES=$((FAILURES + 1))
}

row_exists_in_tsv() {
  local file="$1"
  local value="$2"
  awk -F '\t' -v value="$value" '
    NR == 1 { next }
    $0 == "" || $0 ~ /^#/ { next }
    $1 == value { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$file"
}

list_repo_files() {
  local repo_top root_abs
  repo_top="$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
  root_abs="$(cd "$ROOT" && pwd -P)"
  if [ -n "$repo_top" ] && [ "$repo_top" = "$root_abs" ]; then
    git -C "$ROOT" ls-files --cached --others --exclude-standard
  else
    (cd "$ROOT" && find . -type f | sed 's#^\./##' | sort)
  fi | grep -Ev '^(\.git/|provenance/fixtures/)'
}

is_distribution_candidate() {
  local path="$1"
  case "$path" in
    LICENSE|NOTICE|README.md|Makefile) return 0 ;;
    .github/workflows/configs/*) return 0 ;;
    .github/workflows/*)
      case "$path" in
        .github/workflows/*/*) return 1 ;;
        *.yml|*.yaml) return 0 ;;
      esac
      ;;
    scripts/bifrost-migration-cli/scripts/*.sh) return 0 ;;
    scripts/*)
      case "$path" in
        scripts/*/*) return 1 ;;
        *.sh) return 0 ;;
      esac
      ;;
    transports/Dockerfile*) return 0 ;;
    helm-charts/index.yaml) return 0 ;;
    helm-charts/bifrost/Chart.yaml|helm-charts/bifrost/README.md|helm-charts/bifrost/values.yaml|helm-charts/bifrost/values.schema.json) return 0 ;;
    helm-charts/bifrost/templates/*.yaml|helm-charts/bifrost/values-examples/*.yaml) return 0 ;;
    npx/*/package.json|npx/*/bin.js) return 0 ;;
    terraform/*.tf) return 0 ;;
    dist/*|*/dist/*|*.tgz|*.tar.gz|*.zip) return 0 ;;
    *) return 1 ;;
  esac
}

is_dependency_manifest_candidate() {
  local path="$1"
  case "$path" in
    core/go.mod|framework/go.mod|transports/go.mod|cli/go.mod|scripts/bifrost-migration-cli/go.mod) return 0 ;;
    plugins/*/go.mod) return 0 ;;
    ui/package.json|npx/*/package.json) return 0 ;;
    *) return 1 ;;
  esac
}

is_dependency_lock_candidate() {
  local path="$1"
  case "$path" in
    core/go.sum|framework/go.sum|transports/go.sum|cli/go.sum|scripts/bifrost-migration-cli/go.sum) return 0 ;;
    plugins/*/go.sum) return 0 ;;
    ui/package-lock.json|npx/*/package-lock.json) return 0 ;;
    *) return 1 ;;
  esac
}

dep_source_has_manifest() {
  local file="$1"
  local value="$2"
  awk -F '\t' -v value="$value" '
    NR == 1 { next }
    $0 == "" || $0 ~ /^#/ { next }
    $2 == value { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$file"
}

dep_source_has_lockfile() {
  local file="$1"
  local value="$2"
  awk -F '\t' -v value="$value" '
    NR == 1 { next }
    $0 == "" || $0 ~ /^#/ { next }
    $3 == value { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$file"
}

validate_discovered_candidates() {
  local ledger="$ROOT/provenance/file-ledger.tsv"
  local deps="$ROOT/provenance/dependency-license-sources.tsv"
  local path

  while IFS= read -r path || [ -n "$path" ]; do
    [ -n "$path" ] || continue
    if is_distribution_candidate "$path"; then
      row_exists_in_tsv "$ledger" "$path" || fail "discovered distribution/build/package candidate lacks file-ledger classification: $path"
    fi
    if is_dependency_manifest_candidate "$path"; then
      dep_source_has_manifest "$deps" "$path" || fail "discovered dependency manifest lacks dependency inventory contract: $path"
    fi
    if is_dependency_lock_candidate "$path"; then
      dep_source_has_lockfile "$deps" "$path" || fail "discovered dependency lockfile lacks dependency inventory contract: $path"
    fi
  done <<EOF
$(list_repo_files)
EOF
}

notice_checks() {
  require_file "LICENSE"
  require_file "NOTICE"

  if [ -f "$ROOT/LICENSE" ] && ! grep -q "Apache License" "$ROOT/LICENSE"; then
    fail "LICENSE does not look like Apache-2.0 text"
  fi

  if [ -f "$ROOT/NOTICE" ]; then
    local notice_text
    notice_text="$(tr '\n' ' ' < "$ROOT/NOTICE")"
    printf '%s\n' "$notice_text" | grep -q "Bifrost AI Gateway" || fail "NOTICE missing Bifrost AI Gateway attribution"
    printf '%s\n' "$notice_text" | grep -Eiq "not[[:space:]]+affiliated|not[[:space:]].*endors" || fail "NOTICE missing non-affiliation/non-endorsement language"
  fi
}

validate_distribution_and_ledger() {
  local surfaces="$ROOT/provenance/distribution-surfaces.txt"
  local ledger="$ROOT/provenance/file-ledger.tsv"
  local expected_header="path	origin	license	attribution	modification_notice_required	modification_notice_location	approval_ref	notes"
  local surface path origin license attribution mod_required mod_location approval _notes

  require_file "provenance/distribution-surfaces.txt"
  require_file "provenance/file-ledger.tsv"
  [ -f "$ledger" ] || return

  check_header "$ledger" "$expected_header"
  check_field_count "$ledger" 8 "file-ledger"

  if [ -f "$surfaces" ]; then
    while IFS= read -r surface || [ -n "$surface" ]; do
      is_data_line "$surface" || continue
      validate_rel_path "$surface" || continue
      [ -f "$ROOT/$surface" ] || fail "distribution surface listed but missing: $surface"
      row_exists_in_tsv "$ledger" "$surface" || fail "distribution surface missing from file ledger: $surface"
    done < "$surfaces"
  fi

  while IFS=$'\t' read -r path origin license attribution mod_required mod_location approval _notes || [ -n "${path:-}" ]; do
    [ "${path:-}" != "path" ] || continue
    is_data_line "${path:-}" || continue
    validate_rel_path "$path" || continue
    [ -f "$ROOT/$path" ] || fail "ledger path missing in checkout: $path"
    [ -n "${origin:-}" ] || fail "ledger origin missing for $path"
    [ -n "${license:-}" ] || fail "ledger license missing for $path"
    [ -n "${attribution:-}" ] || fail "ledger attribution missing for $path"
    case "${mod_required:-}" in
      yes)
        if [ -z "${mod_location:-}" ] || [ "$mod_location" = "none" ]; then
          fail "modification notice required but location missing for $path"
        elif [ ! -f "$ROOT/$mod_location" ]; then
          fail "modification notice location missing for $path: $mod_location"
        fi
        ;;
      no) ;;
      *) fail "modification_notice_required must be yes/no for $path" ;;
    esac
    case "${origin:-}" in
      competitor-import)
        if [ -z "${approval:-}" ] || [ "$approval" = "none" ]; then
          fail "competitor import ledger row lacks approval: $path"
        fi
        ;;
    esac
  done < "$ledger"
}

validate_protected_marks() {
  local marks="$ROOT/provenance/protected-marks.tsv"
  local surfaces="$ROOT/provenance/distribution-surfaces.txt"
  local expected_header="mark	owner	allowed_use	approval_required	approval_ref	notes"
  local mark owner allowed approval_required approval_ref _notes surface
  local builtins="Bifrost
Maxim
Maxim HQ
getbifrost.ai"

  require_file "provenance/protected-marks.tsv"
  [ -f "$marks" ] || return
  check_header "$marks" "$expected_header"
  check_field_count "$marks" 6 "protected-marks"

  while IFS=$'\t' read -r mark owner allowed approval_required approval_ref _notes || [ -n "${mark:-}" ]; do
    [ "${mark:-}" != "mark" ] || continue
    is_data_line "${mark:-}" || continue
    [ -n "${owner:-}" ] || fail "protected mark owner missing for $mark"
    [ -n "${allowed:-}" ] || fail "protected mark allowed_use missing for $mark"
    case "${approval_required:-}" in
      yes)
        if [ -z "${approval_ref:-}" ] || [ "$approval_ref" = "none" ]; then
          fail "protected mark requires approval but approval_ref is missing: $mark"
        fi
        ;;
      no) ;;
      *) fail "approval_required must be yes/no for protected mark $mark" ;;
    esac
  done < "$marks"

  [ -f "$surfaces" ] || return
  if ! printf '%s\n' "$builtins" | while IFS= read -r mark; do
    [ -n "$mark" ] || continue
    local found=0
    while IFS= read -r surface || [ -n "$surface" ]; do
      is_data_line "$surface" || continue
      [ -f "$ROOT/$surface" ] || continue
      if grep -Iq . "$ROOT/$surface" && grep -qF "$mark" "$ROOT/$surface"; then
        found=1
        break
      fi
    done < "$surfaces"
    if [ "$found" -eq 1 ] && ! row_exists_in_tsv "$marks" "$mark"; then
      echo "FAIL: protected mark appears in distribution surfaces but is not recorded: $mark" >&2
      exit 1
    fi
  done; then
    FAILURES=$((FAILURES + 1))
  fi
}

validate_competitor_imports() {
  local imports="$ROOT/provenance/competitor-imports.tsv"
  local ledger="$ROOT/provenance/file-ledger.tsv"
  local expected_header="path	source_name	source_url	source_license	import_type	approval_ref	notes"
  local path source_name source_url source_license import_type approval_ref _notes

  require_file "provenance/competitor-imports.tsv"
  [ -f "$imports" ] || return
  check_header "$imports" "$expected_header"
  check_field_count "$imports" 7 "competitor-imports"

  while IFS=$'\t' read -r path source_name source_url source_license import_type approval_ref _notes || [ -n "${path:-}" ]; do
    [ "${path:-}" != "path" ] || continue
    is_data_line "${path:-}" || continue
    validate_rel_path "$path" || continue
    [ -f "$ROOT/$path" ] || fail "competitor import path missing: $path"
    row_exists_in_tsv "$ledger" "$path" || fail "competitor import path missing from file ledger: $path"
    [ -n "${source_name:-}" ] || fail "competitor import source_name missing for $path"
    [ -n "${source_url:-}" ] || fail "competitor import source_url missing for $path"
    [ -n "${source_license:-}" ] || fail "competitor import source_license missing for $path"
    [ -n "${import_type:-}" ] || fail "competitor import type missing for $path"
    if [ -z "${approval_ref:-}" ] || [ "$approval_ref" = "none" ]; then
      fail "competitor import lacks human approval: $path"
    fi
  done < "$imports"
}

validate_bundled_notices() {
  local notices="$ROOT/provenance/bundled-notices.tsv"
  local expected_header="component	distribution_surface	license	notice_file	source	notes"
  local component surface license notice_file source _notes
  local rows=0

  require_file "provenance/bundled-notices.tsv"
  [ -f "$notices" ] || return
  check_header "$notices" "$expected_header"
  check_field_count "$notices" 6 "bundled-notices"

  while IFS=$'\t' read -r component surface license notice_file source _notes || [ -n "${component:-}" ]; do
    [ "${component:-}" != "component" ] || continue
    is_data_line "${component:-}" || continue
    rows=$((rows + 1))
    [ -n "${surface:-}" ] || fail "bundled notice distribution_surface missing for $component"
    [ -n "${license:-}" ] || fail "bundled notice license missing for $component"
    [ -n "${notice_file:-}" ] || fail "bundled notice notice_file missing for $component"
    [ -n "${source:-}" ] || fail "bundled notice source missing for $component"
    if [ "${notice_file:-}" != "none" ] && [ ! -f "$ROOT/$notice_file" ]; then
      fail "bundled notice file missing for $component: $notice_file"
    fi
  done < "$notices"

  [ "$rows" -gt 0 ] || fail "bundled notices inventory has no entries"
}

validate_dependency_sources() {
  local deps="$ROOT/provenance/dependency-license-sources.tsv"
  local expected_header="ecosystem	manifest	lockfile	closure_artifact	sbom_artifact	inventory_status	denied_patterns	approval_ref	notes"
  local ecosystem manifest lockfile closure_artifact sbom_artifact inventory_status denied approval _notes

  require_file "provenance/dependency-license-sources.tsv"
  [ -f "$deps" ] || return
  check_header "$deps" "$expected_header"
  check_field_count "$deps" 9 "dependency-license-sources"

  while IFS=$'\t' read -r ecosystem manifest lockfile closure_artifact sbom_artifact inventory_status denied approval _notes || [ -n "${ecosystem:-}" ]; do
    [ "${ecosystem:-}" != "ecosystem" ] || continue
    is_data_line "${ecosystem:-}" || continue
    [ -n "${ecosystem:-}" ] || fail "dependency source ecosystem missing"
    validate_rel_path "$manifest" || continue
    [ -f "$ROOT/$manifest" ] || fail "dependency manifest missing: $manifest"
    validate_rel_path "$closure_artifact" || continue
    validate_rel_path "$sbom_artifact" || continue
    [ -n "${inventory_status:-}" ] || fail "dependency inventory_status missing for $manifest"
    [ -n "${denied:-}" ] || fail "denied_patterns missing for $manifest"
    if [ "${lockfile:-}" != "none" ]; then
      validate_rel_path "$lockfile" || continue
      if [ ! -f "$ROOT/$lockfile" ]; then
        fail "dependency lockfile missing: $lockfile"
      elif [ -n "$denied" ] && grep -Eiq "\"license\"[[:space:]]*:[^,\}\"]*\"?([^,\}\"]*)($denied)" "$ROOT/$lockfile"; then
        if [ -z "${approval:-}" ] || [ "$approval" = "none" ]; then
          fail "denied dependency license pattern found without approval in $lockfile"
        fi
      fi
    fi
    if [ ! -f "$ROOT/$closure_artifact" ]; then
      fail "missing dependency closure artifact for $manifest: $closure_artifact"
    else
      validate_dependency_closure_artifact "$closure_artifact" "$manifest" "$denied"
      validate_inventory_input_hashes "$closure_artifact" "$manifest" "$lockfile"
    fi
    if [ ! -f "$ROOT/$sbom_artifact" ]; then
      fail "missing dependency SBOM artifact for $manifest: $sbom_artifact"
    else
      validate_sbom_artifact "$sbom_artifact" "$manifest"
      if [ -f "$ROOT/$closure_artifact" ]; then
        validate_inventory_sbom_equality "$closure_artifact" "$sbom_artifact" "$manifest"
        if [ "$ecosystem" = "npm" ] && [ "$lockfile" != "none" ] && [ -f "$ROOT/$lockfile" ]; then
          validate_npm_lock_inventory_equality "$lockfile" "$closure_artifact" "$manifest"
        fi
      fi
    fi
    case "$inventory_status" in
      resolved) ;;
      unresolved|denied)
        fail "dependency inventory status blocks release for $manifest: $inventory_status (artifact: $closure_artifact)"
        ;;
      *) fail "dependency inventory_status must be resolved/unresolved/denied for $manifest" ;;
    esac
  done < "$deps"
}

validate_dependency_closure_artifact() {
  local artifact="$1"
  local manifest="$2"
  local denied="$3"
  local file="$ROOT/$artifact"
  local expected_header="dependency	version	license	status	evidence	approval_ref"
  local dependency version license status evidence approval evidence_path evidence_sha actual_sha
  local rows=0

  check_header "$file" "$expected_header"
  check_field_count "$file" 6 "dependency-closure"
  while IFS=$'\t' read -r dependency version license status evidence approval || [ -n "${dependency:-}" ]; do
    [ "${dependency:-}" != "dependency" ] || continue
    is_data_line "${dependency:-}" || continue
    rows=$((rows + 1))
    [ -n "${version:-}" ] || fail "dependency version missing in $artifact for $dependency"
    [ -n "${license:-}" ] || fail "dependency license missing in $artifact for $dependency"
    [ -n "${evidence:-}" ] || fail "dependency evidence missing in $artifact for $dependency"
    case "$evidence" in
      *.sum|*go.sum*) fail "go.sum is not license evidence in $artifact for $dependency" ;;
    esac
    case "$evidence" in
      *'#sha256='*)
        evidence_path="${evidence%%#sha256=*}"
        evidence_sha="${evidence##*#sha256=}"
        ;;
      *)
        evidence_path="$evidence"
        evidence_sha=""
        fail "dependency evidence lacks a bound sha256 in $artifact for $dependency"
        ;;
    esac
    if [ "${#evidence_sha}" -ne 64 ] || printf '%s\n' "$evidence_sha" | grep -Eq '[^0-9a-f]'; then
      fail "dependency evidence sha256 is not 64 lowercase hex characters in $artifact for $dependency"
    fi
    if validate_rel_path "$evidence_path"; then
      if [ ! -f "$ROOT/$evidence_path" ]; then
        fail "dependency evidence file missing in $artifact for $dependency: $evidence_path"
      elif [ -n "$evidence_sha" ]; then
        actual_sha="$(sha256_file "$ROOT/$evidence_path" 2>/dev/null || true)"
        [ -n "$actual_sha" ] || fail "no SHA-256 implementation available for dependency evidence"
        [ "$actual_sha" = "$evidence_sha" ] || fail "dependency evidence sha256 mismatch in $artifact for $dependency: $evidence_path"
      fi
    fi
    if [ -n "$denied" ] && printf '%s\n' "$license" | grep -Eiq -- "$denied"; then
      if [ -z "${approval:-}" ] || [ "$approval" = "none" ]; then
        fail "denied dependency license found without approval in $artifact: $dependency ($license)"
      fi
    fi
    case "${status:-}" in
      resolved) ;;
      unresolved|denied)
        fail "dependency closure for $manifest contains blocking $status dependency: $dependency"
        ;;
      *) fail "dependency status must be resolved/unresolved/denied in $artifact for $dependency" ;;
    esac
    if [ "${status:-}" = "denied" ] && { [ -z "${approval:-}" ] || [ "$approval" = "none" ]; }; then
      fail "denied dependency lacks approval reference in $artifact: $dependency"
    fi
  done < "$file"
  [ "$rows" -gt 0 ] || fail "dependency closure artifact has no dependency rows for $manifest: $artifact"
}

validate_inventory_input_hashes() {
  local inventory="$1"
  local manifest="$2"
  local lockfile="$3"
  local metadata manifest_sha lock_sha actual

  metadata="$(sed -n '2p' "$ROOT/$inventory")"
  case "$metadata" in
    '# manifest_sha256='*' lockfile_sha256='*) ;;
    *) fail "dependency inventory lacks input hash metadata for $manifest: $inventory"; return ;;
  esac
  manifest_sha="${metadata#\# manifest_sha256=}"
  manifest_sha="${manifest_sha%% *}"
  lock_sha="${metadata##* lockfile_sha256=}"
  actual="$(sha256_file "$ROOT/$manifest" 2>/dev/null || true)"
  [ "$actual" = "$manifest_sha" ] || fail "dependency inventory manifest sha256 is stale for $manifest: $inventory"
  if [ "$lockfile" = "none" ]; then
    [ "$lock_sha" = "none" ] || fail "dependency inventory lockfile hash must be none for $manifest"
  else
    actual="$(sha256_file "$ROOT/$lockfile" 2>/dev/null || true)"
    [ "$actual" = "$lock_sha" ] || fail "dependency inventory lockfile sha256 is stale for $manifest: $inventory"
  fi
}

validate_inventory_sbom_equality() {
  local inventory="$1"
  local sbom="$2"
  local manifest="$3"
  local inventory_set sbom_set

  inventory_set="$(awk -F '\t' '
    NR == 1 || $0 == "" || $0 ~ /^#/ { next }
    { print $1 "\t" $2 "\t" $3 }
  ' "$ROOT/$inventory" | LC_ALL=C sort -u)"
  sbom_set="$(jq -r '
    .packages[] | [.name, .versionInfo, .licenseConcluded] | @tsv
  ' "$ROOT/$sbom" 2>/dev/null | LC_ALL=C sort -u)"
  if [ "$inventory_set" != "$sbom_set" ]; then
    fail "dependency inventory and SBOM package sets differ for $manifest: $inventory vs $sbom"
  fi
}

validate_npm_lock_inventory_equality() {
  local lockfile="$1"
  local inventory="$2"
  local manifest="$3"
  local lock_set inventory_set

  lock_set="$(jq -r '
    .packages
    | to_entries[]
    | select(.value.link != true)
    | [
        (if .key == "" then .value.name
         else (.key | split("node_modules/") | last)
         end),
        .value.version
      ]
    | select(.[0] != null and .[0] != "" and .[1] != null and .[1] != "")
    | @tsv
  ' "$ROOT/$lockfile" 2>/dev/null | LC_ALL=C sort -u)"
  inventory_set="$(awk -F '\t' '
    NR == 1 || $0 == "" || $0 ~ /^#/ { next }
    { print $1 "\t" $2 }
  ' "$ROOT/$inventory" | LC_ALL=C sort -u)"
  if [ "$lock_set" != "$inventory_set" ]; then
    fail "npm lockfile and dependency inventory package sets differ for $manifest: $lockfile vs $inventory"
  fi
}

validate_sbom_artifact() {
  local artifact="$1"
  local manifest="$2"
  local file="$ROOT/$artifact"
  if ! command -v jq >/dev/null 2>&1; then
    fail "jq is required to validate SBOM artifacts"
    return
  fi
  if ! jq -e '
    .spdxVersion == "SPDX-2.3" and
    .dataLicense == "CC0-1.0" and
    .SPDXID == "SPDXRef-DOCUMENT" and
    (.name | type == "string" and length > 0) and
    (.documentNamespace | type == "string" and length > 0) and
    (.creationInfo.created | type == "string" and length > 0) and
    (.creationInfo.creators | type == "array" and length > 0) and
    (.packages | type == "array" and length > 0) and
    ([.packages[].SPDXID] as $ids | ($ids | unique | length) == ($ids | length)) and
    (.documentDescribes | type == "array" and length > 0) and
    ([.packages[].SPDXID] as $ids |
      all(.documentDescribes[]; . as $id | $ids | index($id) != null)
    ) and
    all(.packages[];
      (.SPDXID | type == "string" and startswith("SPDXRef-")) and
      (.name | type == "string" and length > 0) and
      (.versionInfo | type == "string" and length > 0) and
      (.licenseDeclared | type == "string" and length > 0) and
      (.licenseConcluded | type == "string" and length > 0 and . != "NOASSERTION") and
      (.externalRefs | type == "array" and
        any(.[];
          .referenceCategory == "PACKAGE-MANAGER" and
          .referenceType == "purl" and
          (.referenceLocator | type == "string" and startswith("pkg:"))
        )
      ) and
      (.checksums | type == "array" and length > 0) and
      all(.checksums[];
        ((.algorithm == "SHA256") and
         (.checksumValue | type == "string" and test("^[0-9a-fA-F]{64}$"))) or
        ((.algorithm == "SHA512") and
         (.checksumValue | type == "string" and test("^[0-9a-fA-F]{128}$")))
      )
    ) and
    (.relationships | type == "array") and
    (([.packages[].SPDXID] + ["SPDXRef-DOCUMENT"]) as $ids |
      all(.relationships[]; . as $rel |
        ($ids | index($rel.spdxElementId) != null) and
        ($ids | index($rel.relatedSpdxElement) != null) and
        ($rel.relationshipType | type == "string" and length > 0)
      )
    )
  ' "$file" >/dev/null 2>&1; then
    fail "SBOM artifact for $manifest is not a complete SPDX 2.3 JSON document: $artifact"
  fi
}

validate_artifact_bundles() {
  local bundles="$ROOT/provenance/artifact-bundles.tsv"
  local expected_header="artifact	notice_file	license_file	sbom_file	dependency_inventory	notes"
  local artifact notice_file license_file sbom_file dependency_inventory _notes
  local rows=0

  require_file "provenance/artifact-bundles.tsv"
  [ -f "$bundles" ] || return
  check_header "$bundles" "$expected_header"
  check_field_count "$bundles" 6 "artifact-bundles"

  while IFS=$'\t' read -r artifact notice_file license_file sbom_file dependency_inventory _notes || [ -n "${artifact:-}" ]; do
    [ "${artifact:-}" != "artifact" ] || continue
    is_data_line "${artifact:-}" || continue
    rows=$((rows + 1))
    [ -n "${artifact:-}" ] || fail "artifact bundle name missing"
    validate_rel_path "$notice_file" || continue
    validate_rel_path "$license_file" || continue
    validate_rel_path "$sbom_file" || continue
    validate_rel_path "$dependency_inventory" || continue
    [ -f "$ROOT/$notice_file" ] || fail "artifact bundle notice input missing for $artifact: $notice_file"
    [ -f "$ROOT/$license_file" ] || fail "artifact bundle license input missing for $artifact: $license_file"
    [ -f "$ROOT/$sbom_file" ] || fail "artifact bundle SBOM input missing for $artifact: $sbom_file"
    [ -f "$ROOT/$dependency_inventory" ] || fail "artifact bundle dependency inventory missing for $artifact: $dependency_inventory"
  done < "$bundles"
  [ "$rows" -gt 0 ] || fail "artifact bundle inventory has no entries"
}

run_validation() {
  notice_checks
  validate_distribution_and_ledger
  validate_protected_marks
  validate_competitor_imports
  validate_bundled_notices
  validate_dependency_sources
  validate_artifact_bundles
  validate_discovered_candidates

  if [ "$FAILURES" -eq 0 ]; then
    pass_msg "provenance gate passed for $ROOT"
    return 0
  fi
  echo "provenance gate failed for $ROOT with $FAILURES failure(s)" >&2
  return 1
}

run_self_tests() {
  local cases="$ROOT/provenance/fixtures/cases.tsv"
  local name case_root expected status output mutation_root
  local failed=0

  if [ ! -f "$cases" ]; then
    echo "missing self-test cases: $cases" >&2
    return 1
  fi

  while IFS=$'\t' read -r name case_root expected || [ -n "${name:-}" ]; do
    [ "${name:-}" != "name" ] || continue
    is_data_line "${name:-}" || continue
    set +e
    output="$(bash "$SCRIPT_PATH" --root "$case_root" 2>&1)"
    status=$?
    set -e
    if [ "$expected" = "pass" ] && [ "$status" -eq 0 ]; then
      echo "PASS self-test $name"
    elif [ "$expected" = "fail" ] && [ "$status" -ne 0 ]; then
      echo "PASS self-test $name"
    else
      echo "FAIL self-test $name expected $expected got status $status" >&2
      echo "$output" >&2
      failed=$((failed + 1))
    fi
  done < "$cases"

  # A text grep must never be sufficient SBOM evidence. Exercise the parser
  # against syntactically valid but structurally empty SPDX-looking JSON.
  mutation_root="$(mktemp -d)"
  cp -R "$ROOT/provenance/fixtures/valid/." "$mutation_root/"
  printf '%s\n' '{"spdxVersion":"SPDX-2.3","SPDXID":"SPDXRef-DOCUMENT"}' \
    > "$mutation_root/provenance/sbom/npm.spdx.json"
  set +e
  output="$(bash "$SCRIPT_PATH" --root "$mutation_root" 2>&1)"
  status=$?
  set -e
  rm -rf "$mutation_root"
  if [ "$status" -ne 0 ] && printf '%s\n' "$output" | grep -q 'not a complete SPDX 2.3 JSON document'; then
    echo "PASS self-test invalid-sbom"
  else
    echo "FAIL self-test invalid-sbom expected structural SBOM rejection" >&2
    echo "$output" >&2
    failed=$((failed + 1))
  fi

  mutation_root="$(mktemp -d)"
  cp -R "$ROOT/provenance/fixtures/valid/." "$mutation_root/"
  printf '%s\n' 'omitted-from-sbom	9.9.9	MIT	resolved	package-lock.json	none' \
    >> "$mutation_root/provenance/dependency-inventory/npm.tsv"
  set +e
  output="$(bash "$SCRIPT_PATH" --root "$mutation_root" 2>&1)"
  status=$?
  set -e
  rm -rf "$mutation_root"
  if [ "$status" -ne 0 ] && printf '%s\n' "$output" | grep -q 'inventory and SBOM package sets differ'; then
    echo "PASS self-test incomplete-sbom-closure"
  else
    echo "FAIL self-test incomplete-sbom-closure expected exact package-set rejection" >&2
    echo "$output" >&2
    failed=$((failed + 1))
  fi

  mutation_root="$(mktemp -d)"
  cp -R "$ROOT/provenance/fixtures/valid/." "$mutation_root/"
  awk -F '\t' 'BEGIN { OFS="\t" } $1 == "fixture" { $3="AGPL-3.0-only" } { print }' \
    "$mutation_root/provenance/dependency-inventory/npm.tsv" \
    > "$mutation_root/provenance/dependency-inventory/npm.tsv.new"
  mv "$mutation_root/provenance/dependency-inventory/npm.tsv.new" \
    "$mutation_root/provenance/dependency-inventory/npm.tsv"
  jq '.packages[0].licenseDeclared="AGPL-3.0-only" | .packages[0].licenseConcluded="AGPL-3.0-only"' \
    "$mutation_root/provenance/sbom/npm.spdx.json" \
    > "$mutation_root/provenance/sbom/npm.spdx.json.new"
  mv "$mutation_root/provenance/sbom/npm.spdx.json.new" \
    "$mutation_root/provenance/sbom/npm.spdx.json"
  set +e
  output="$(bash "$SCRIPT_PATH" --root "$mutation_root" 2>&1)"
  status=$?
  set -e
  rm -rf "$mutation_root"
  if [ "$status" -ne 0 ] && printf '%s\n' "$output" | grep -q 'denied dependency license found without approval'; then
    echo "PASS self-test denied-inventory-license"
  else
    echo "FAIL self-test denied-inventory-license expected license-policy rejection" >&2
    echo "$output" >&2
    failed=$((failed + 1))
  fi

  mutation_root="$(mktemp -d)"
  cp -R "$ROOT/provenance/fixtures/valid/." "$mutation_root/"
  awk -F '\t' 'NR == 1 || $1 != "example"' \
    "$mutation_root/provenance/dependency-inventory/npm.tsv" \
    > "$mutation_root/provenance/dependency-inventory/npm.tsv.new"
  mv "$mutation_root/provenance/dependency-inventory/npm.tsv.new" \
    "$mutation_root/provenance/dependency-inventory/npm.tsv"
  jq '.packages |= map(select(.name != "example"))' \
    "$mutation_root/provenance/sbom/npm.spdx.json" \
    > "$mutation_root/provenance/sbom/npm.spdx.json.new"
  mv "$mutation_root/provenance/sbom/npm.spdx.json.new" \
    "$mutation_root/provenance/sbom/npm.spdx.json"
  set +e
  output="$(bash "$SCRIPT_PATH" --root "$mutation_root" 2>&1)"
  status=$?
  set -e
  rm -rf "$mutation_root"
  if [ "$status" -ne 0 ] && printf '%s\n' "$output" | grep -q 'npm lockfile and dependency inventory package sets differ'; then
    echo "PASS self-test omitted-lock-dependency"
  else
    echo "FAIL self-test omitted-lock-dependency expected derived-closure rejection" >&2
    echo "$output" >&2
    failed=$((failed + 1))
  fi

  mutation_root="$(mktemp -d)"
  cp -R "$ROOT/provenance/fixtures/valid/." "$mutation_root/"
  printf '%s\n' 'tampered after inventory generation' \
    >> "$mutation_root/provenance/license-evidence/example-mit.txt"
  set +e
  output="$(bash "$SCRIPT_PATH" --root "$mutation_root" 2>&1)"
  status=$?
  set -e
  rm -rf "$mutation_root"
  if [ "$status" -ne 0 ] && printf '%s\n' "$output" | grep -q 'dependency evidence sha256 mismatch'; then
    echo "PASS self-test tampered-license-evidence"
  else
    echo "FAIL self-test tampered-license-evidence expected digest-bound evidence rejection" >&2
    echo "$output" >&2
    failed=$((failed + 1))
  fi

  mutation_root="$(mktemp -d)"
  cp -R "$ROOT/provenance/fixtures/valid/." "$mutation_root/"
  printf '%s\n' ' ' >> "$mutation_root/package.json"
  set +e
  output="$(bash "$SCRIPT_PATH" --root "$mutation_root" 2>&1)"
  status=$?
  set -e
  rm -rf "$mutation_root"
  if [ "$status" -ne 0 ] && printf '%s\n' "$output" | grep -q 'dependency inventory manifest sha256 is stale'; then
    echo "PASS self-test stale-inventory-input"
  else
    echo "FAIL self-test stale-inventory-input expected input-digest rejection" >&2
    echo "$output" >&2
    failed=$((failed + 1))
  fi

  if [ "$failed" -eq 0 ]; then
    pass_msg "all provenance self-tests passed"
    return 0
  fi
  echo "provenance self-tests failed with $failed failure(s)" >&2
  return 1
}

if [ "$SELF_TEST" -eq 1 ]; then
  run_self_tests
else
  run_validation
fi
