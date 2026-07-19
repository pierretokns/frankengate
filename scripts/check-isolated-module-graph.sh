#!/usr/bin/env bash
set -euo pipefail

# Verify that every shipped Go module can resolve its imports without the
# developer-only go.work file. This compile-only check catches published-module
# drift before an image or release job starts.
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
MODULES=(core framework transports plugins/governance plugins/otel plugins/telemetry plugins/logging)
GOCACHE="${GOCACHE:-/tmp/frankengate-gocache}"
failed=0

for module in "${MODULES[@]}"; do
	if [[ ! -f "$ROOT/$module/go.mod" ]]; then
		echo "missing go.mod: $module" >&2
		failed=1
		continue
	fi
	echo "checking isolated module graph: $module"
	# The fork's modules intentionally retain the upstream module paths for
	# drop-in compatibility.  With GOWORK=off, Go would otherwise download the
	# upstream core/framework/plugins and silently test a different graph.  Use
	# a throw-away modfile that points sibling modules at this checkout; this
	# keeps the check workspace-independent while exercising the fork sources.
	modfile="$(mktemp "${TMPDIR:-/tmp}/frankengate-${module//\//-}.XXXXXX.mod")"
	trap 'rm -f "$modfile"' RETURN
	cp "$ROOT/$module/go.mod" "$modfile"
	# Go derives the checksum filename from -modfile's basename. Keep the
	# module's checked-in sums alongside the throw-away modfile so this check
	# remains read-only and does not need to rewrite dependency metadata.
	modsum="${modfile%.mod}.sum"
	if [[ -f "$ROOT/$module/go.sum" ]]; then
		cp "$ROOT/$module/go.sum" "$modsum"
	fi
	for mapping in \
		"github.com/maximhq/bifrost/core=$ROOT/core" \
		"github.com/maximhq/bifrost/framework=$ROOT/framework" \
		"github.com/maximhq/bifrost/transports=$ROOT/transports" \
		"github.com/maximhq/bifrost/plugins/compat=$ROOT/plugins/compat" \
		"github.com/maximhq/bifrost/plugins/governance=$ROOT/plugins/governance" \
		"github.com/maximhq/bifrost/plugins/logging=$ROOT/plugins/logging" \
		"github.com/maximhq/bifrost/plugins/otel=$ROOT/plugins/otel" \
		"github.com/maximhq/bifrost/plugins/telemetry=$ROOT/plugins/telemetry"; do
		(cd "$ROOT/$module" && go mod edit -modfile "$modfile" -replace "$mapping")
	done
	if ! (cd "$ROOT/$module" && GOWORK=off GOCACHE="$GOCACHE" go test -modfile "$modfile" -run '^$' ./...); then
		echo "isolated module graph failed: $module" >&2
		failed=1
	fi
	rm -f "$modfile" "$modsum"
	trap - RETURN
done

if (( failed != 0 )); then
	echo "isolated module graph check failed; do not publish this release" >&2
	exit 1
fi

echo "isolated module graph passed"
