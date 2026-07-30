PYTHON ?= python3
PYTHONPYCACHEPREFIX ?= /private/tmp/frankengate-trace-intelligence-pycache
QWEN3_EMBEDDING_DEVICE ?= cpu

.PHONY: verify test validate compile governed-wisp otel-roundtrip history-discovery trace-memory e2-retrieval e2-postgres-joint

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

# Re-runs the pinned two-file real trace plus versioned-memory conformance arm.
# Raw JSONL must already exist in an external disposable cache; this target never
# downloads it and emits only aggregate receipts.
trace-memory:
	@test -n "$(TRACE_COMMONS_ROOT)" || \
		(printf '%s\n' 'TRACE_COMMONS_ROOT is required' >&2; exit 2)
	$(PYTHON) trace_commons_memory_conformance.py \
		--manifest configs/datasets/trace-commons-epilog-memory-lifecycle.json \
		--source-root "$(TRACE_COMMONS_ROOT)" \
		--output experiments/results/trace-commons-memory-conformance-2026-07-30.json \
		--summary experiments/summaries/trace-commons-memory-conformance-2026-07-30.md

# Runs the frozen raw CodeTraceBench E2 quality factorial. The archive root and
# embedding snapshot are intentionally external to Git. PostgreSQL RLS evidence
# is referenced as an independent runtime proof, not misrepresented as a joint run.
e2-retrieval:
	@test -n "$(CODETRACEBENCH_FULL)" || \
		(printf '%s\n' 'CODETRACEBENCH_FULL is required' >&2; exit 2)
	@test -n "$(CODETRACEBENCH_ARCHIVE_ROOT)" || \
		(printf '%s\n' 'CODETRACEBENCH_ARCHIVE_ROOT is required' >&2; exit 2)
	@test -n "$(QWEN3_EMBEDDING_SNAPSHOT)" || \
		(printf '%s\n' 'QWEN3_EMBEDDING_SNAPSHOT is required' >&2; exit 2)
	$(PYTHON) e2_authorized_retrieval_factorial.py \
		--allowlist experiments/manifests/codetracebench-raw-blocked-test-allowlist-2026-07-30.json \
		--full "$(CODETRACEBENCH_FULL)" \
		--archive-root "$(CODETRACEBENCH_ARCHIVE_ROOT)" \
		--authorization-result experiments/results/wisp-governed-postgres-benchmark-2026-07-30.json \
		--embedding-model "$(QWEN3_EMBEDDING_SNAPSHOT)" \
		--embedding-device "$(QWEN3_EMBEDDING_DEVICE)" \
		--output experiments/results/codetracebench-e2-authorized-retrieval-factorial-2026-07-30.json \
		--summary experiments/summaries/codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md

# Re-runs the same-candidate native PostgreSQL retrieval and forced-RLS gate.
# The database must be disposable and have sql/001 through sql/004 applied.
# Corpus rows exist only inside a rollback-only transaction.
e2-postgres-joint:
	@test -n "$(GOVERNED_POSTGRES_DSN)" || \
		(printf '%s\n' 'GOVERNED_POSTGRES_DSN is required' >&2; exit 2)
	@test -n "$(CODETRACEBENCH_FULL)" || \
		(printf '%s\n' 'CODETRACEBENCH_FULL is required' >&2; exit 2)
	@test -n "$(CODETRACEBENCH_ARCHIVE_ROOT)" || \
		(printf '%s\n' 'CODETRACEBENCH_ARCHIVE_ROOT is required' >&2; exit 2)
	@test -n "$(QWEN3_EMBEDDING_SNAPSHOT)" || \
		(printf '%s\n' 'QWEN3_EMBEDDING_SNAPSHOT is required' >&2; exit 2)
	$(PYTHON) e2_postgres_joint_retrieval.py \
		--dsn "$(GOVERNED_POSTGRES_DSN)" \
		--allowlist experiments/manifests/codetracebench-raw-blocked-test-allowlist-2026-07-30.json \
		--full "$(CODETRACEBENCH_FULL)" \
		--archive-root "$(CODETRACEBENCH_ARCHIVE_ROOT)" \
		--embedding-model "$(QWEN3_EMBEDDING_SNAPSHOT)" \
		--embedding-device "$(QWEN3_EMBEDDING_DEVICE)" \
		--output experiments/results/codetracebench-e2-postgres-joint-retrieval-2026-07-30.json \
		--summary experiments/summaries/codetracebench-e2-postgres-joint-retrieval-2026-07-30.md
