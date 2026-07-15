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
  local expected_header="ecosystem	manifest	lockfile	scan_mode	allowed_licenses	denied_patterns	approval_ref	notes"
  local ecosystem manifest lockfile scan_mode allowed denied approval _notes

  require_file "provenance/dependency-license-sources.tsv"
  [ -f "$deps" ] || return
  check_header "$deps" "$expected_header"
  check_field_count "$deps" 8 "dependency-license-sources"

  while IFS=$'\t' read -r ecosystem manifest lockfile scan_mode allowed denied approval _notes || [ -n "${ecosystem:-}" ]; do
    [ "${ecosystem:-}" != "ecosystem" ] || continue
    is_data_line "${ecosystem:-}" || continue
    [ -n "${ecosystem:-}" ] || fail "dependency source ecosystem missing"
    validate_rel_path "$manifest" || continue
    [ -f "$ROOT/$manifest" ] || fail "dependency manifest missing: $manifest"
    [ -n "${scan_mode:-}" ] || fail "dependency scan_mode missing for $manifest"
    [ -n "${allowed:-}" ] || fail "allowed_licenses missing for $manifest"
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
  done < "$deps"
}

run_validation() {
  notice_checks
  validate_distribution_and_ledger
  validate_protected_marks
  validate_competitor_imports
  validate_bundled_notices
  validate_dependency_sources

  if [ "$FAILURES" -eq 0 ]; then
    pass_msg "provenance gate passed for $ROOT"
    return 0
  fi
  echo "provenance gate failed for $ROOT with $FAILURES failure(s)" >&2
  return 1
}

run_self_tests() {
  local cases="$ROOT/provenance/fixtures/cases.tsv"
  local name case_root expected status output
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
