PYTHON ?= python3
PYTHONPYCACHEPREFIX ?= /private/tmp/frankengate-trace-intelligence-pycache

.PHONY: verify test validate compile governed-wisp otel-roundtrip history-discovery

verify: test validate compile

test:
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

validate:
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) reproducibility.py

compile:
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) -m compileall -q -f -x '/datasets/' .

# This target intentionally requires explicit private paths and a disposable
# governed database. It never downloads or discovers raw histories itself.
governed-wisp:
	@test -n "$(GOVERNED_POSTGRES_DSN)" || \
		(printf '%s\n' 'GOVERNED_POSTGRES_DSN is required' >&2; exit 2)
	@test -n "$(WISP_CORPUS_ROOT)" || \
		(printf '%s\n' 'WISP_CORPUS_ROOT is required' >&2; exit 2)
	$(PYTHON) wisp_postgres_loader.py \
		--dsn "$(GOVERNED_POSTGRES_DSN)" \
		--corpus-root "$(WISP_CORPUS_ROOT)" \
		--manifest configs/datasets/wisp-claude-code-sessions.json
	$(PYTHON) wisp_postgres_benchmark.py \
		--dsn "$(GOVERNED_POSTGRES_DSN)" \
		--output experiments/results/wisp-governed-postgres-benchmark-2026-07-30.json \
		--iterations 100

# Downloads and verifies the pinned Collector release, builds the pinned
# OpenTelemetry Go SDK sender, and keeps content-bearing runtime artifacts in a
# disposable directory. The only durable output is aggregate JSON.
otel-roundtrip:
	./run-otel-collector-roundtrip.sh

# Rebuilds the content-free, source-pinned public history discovery receipt.
# It performs no network requests and reads only committed manifests.
history-discovery:
	$(PYTHON) public_agent_history_discovery.py \
		--output experiments/results/public-agent-history-discovery-2026-07-30.json \
		--summary experiments/summaries/public-agent-history-discovery-2026-07-30.md
