PYTHON ?= python3
PYTHONPYCACHEPREFIX ?= /private/tmp/frankengate-trace-intelligence-pycache
QWEN3_EMBEDDING_DEVICE ?= cpu

.PHONY: verify test validate compile governed-wisp otel-roundtrip history-discovery trace-memory longitudinal-memory-expansion longitudinal-memory-local-model longitudinal-memory-local-finalize memory-h5-concurrency e2-retrieval e2-postgres-joint defog-sql-conformance defog-sql-design defog-sql-mechanics nl2sql-postgres-role-audit nl2sql-linux-oci-conformance

verify: test validate compile

test:
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) -m unittest discover \
			-s nl2sql_capabilities/tests -p 'test_*.py'

validate:
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) reproducibility.py

compile:
	PYTHONPYCACHEPREFIX="$(PYTHONPYCACHEPREFIX)" \
		$(PYTHON) -m compileall -q -f -x '/datasets/' .

# Rebuilds the content-free, leakage-safe four-fold SQL factorial contract.
# Model and authority manifests are pinned inputs; benchmark content is never
# copied into this output.
defog-sql-design:
	$(PYTHON) defog_sql_factorial_design.py \
		--cohort-manifest experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json \
		--model-manifest configs/models/qwen3.5-9b-optiq-4bit-mlx.json \
		--authority-manifest configs/governance/defog-factorial-authority-epoch-2026-07-30.json \
		--output experiments/manifests/defog-sql-factorial-design-2026-07-30.json

# Runs the four-task/three-arm P0 mechanics smoke. The caller must start the
# pinned loopback model runtime exactly as recorded in the model manifest.
# Raw prompts, SQL, tool results, and model messages stay outside Git.
defog-sql-mechanics:
	@test -n "$(DEFOG_SOURCE_ROOT)" || \
		(printf '%s\n' 'DEFOG_SOURCE_ROOT is required' >&2; exit 2)
	@test -n "$(DEFOG_REPLAY_DSN_TEMPLATE)" || \
		(printf '%s\n' 'DEFOG_REPLAY_DSN_TEMPLATE is required' >&2; exit 2)
	@test -n "$(DEFOG_RAW_AUDIT_DIR)" || \
		(printf '%s\n' 'DEFOG_RAW_AUDIT_DIR is required' >&2; exit 2)
	@test -n "$(DEFOG_MODEL_ENDPOINT)" || \
		(printf '%s\n' 'DEFOG_MODEL_ENDPOINT is required' >&2; exit 2)
	$(PYTHON) defog_sql_factorial.py \
		--source-root "$(DEFOG_SOURCE_ROOT)" \
		--cohort-manifest experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json \
		--dataset-manifest configs/datasets/defog-sql-eval-enterprise.json \
		--design-manifest experiments/manifests/defog-sql-factorial-design-2026-07-30.json \
		--model-manifest configs/models/qwen3.5-9b-optiq-4bit-mlx.json \
		--authority-manifest configs/governance/defog-factorial-authority-epoch-2026-07-30.json \
		--fold-id fold-0 \
		--dsn-template "$(DEFOG_REPLAY_DSN_TEMPLATE)" \
		--endpoint "$(DEFOG_MODEL_ENDPOINT)" \
		--raw-audit-dir "$(DEFOG_RAW_AUDIT_DIR)" \
		--output experiments/results/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.json

# Replays the hash-pinned Defog cohort through a constrained local PostgreSQL
# role. Source content and raw tool records remain outside Git; only a
# content-free aggregate result is durable.
defog-sql-conformance:
	@test -n "$(DEFOG_SOURCE_ROOT)" || \
		(printf '%s\n' 'DEFOG_SOURCE_ROOT is required' >&2; exit 2)
	@test -n "$(DEFOG_REPLAY_DSN_TEMPLATE)" || \
		(printf '%s\n' 'DEFOG_REPLAY_DSN_TEMPLATE is required' >&2; exit 2)
	@test -n "$(DEFOG_RAW_AUDIT_DIR)" || \
		(printf '%s\n' 'DEFOG_RAW_AUDIT_DIR is required' >&2; exit 2)
	$(PYTHON) defog_sql_replay_conformance.py \
		--source-root "$(DEFOG_SOURCE_ROOT)" \
		--manifest experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json \
		--dataset-manifest configs/datasets/defog-sql-eval-enterprise.json \
		--dsn-template "$(DEFOG_REPLAY_DSN_TEMPLATE)" \
		--raw-audit-dir "$(DEFOG_RAW_AUDIT_DIR)" \
		--output experiments/results/defog-governed-sql-replay-conformance-2026-07-30.json

# Runs a bounded real PostgreSQL 16 candidate/evaluator role and snapshot audit.
# The fixture and raw SQL/result/identity evidence must remain outside Git.
nl2sql-postgres-role-audit:
	@test -n "$(NL2SQL_PG16_DSN)" || \
		(printf '%s\n' 'NL2SQL_PG16_DSN is required' >&2; exit 2)
	@test -n "$(NL2SQL_ROLE_AUDIT_FIXTURE)" || \
		(printf '%s\n' 'NL2SQL_ROLE_AUDIT_FIXTURE is required' >&2; exit 2)
	@test -n "$(NL2SQL_ROLE_AUDIT_FIXTURE_SHA256)" || \
		(printf '%s\n' 'NL2SQL_ROLE_AUDIT_FIXTURE_SHA256 is required' >&2; exit 2)
	@test -n "$(NL2SQL_ROLE_AUDIT_RAW)" || \
		(printf '%s\n' 'NL2SQL_ROLE_AUDIT_RAW is required' >&2; exit 2)
	$(PYTHON) nl2sql_postgres_role_audit.py \
		--dsn "$(NL2SQL_PG16_DSN)" \
		--fixture-json "$(NL2SQL_ROLE_AUDIT_FIXTURE)" \
		--fixture-sha256 "$(NL2SQL_ROLE_AUDIT_FIXTURE_SHA256)" \
		--raw-audit-jsonl "$(NL2SQL_ROLE_AUDIT_RAW)" \
		--output-json experiments/results/nl2sql-postgres-role-audit-2026-07-30.json

# Must run as root inside the disposable Linux/Colima VM. The pinned image must
# already be cached; the runner never pulls it. Exact raw evidence stays external.
nl2sql-linux-oci-conformance:
	@test "$$(uname -s)" = Linux || \
		(printf '%s\n' 'nl2sql-linux-oci-conformance requires Linux' >&2; exit 2)
	@test -n "$(NL2SQL_OCI_RAW)" || \
		(printf '%s\n' 'NL2SQL_OCI_RAW is required' >&2; exit 2)
	$(PYTHON) nl2sql_linux_oci_conformance.py \
		--raw-output "$(NL2SQL_OCI_RAW)" \
		--aggregate-output experiments/results/nl2sql-linux-oci-conformance-2026-07-30.json

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

# Rebuilds the path-minimized Fable stratum, scans it without emitting possible
# credential values, and runs the source-stratified longitudinal expansion.
# Both raw source trees and the prepared content-addressed quarantine are
# external to Git.
longitudinal-memory-expansion:
	@test -n "$(TRACE_COMMONS_ROOT)" || \
		(printf '%s\n' 'TRACE_COMMONS_ROOT is required' >&2; exit 2)
	@test -n "$(FABLE5_SOURCE_ROOT)" || \
		(printf '%s\n' 'FABLE5_SOURCE_ROOT is required' >&2; exit 2)
	@test -n "$(FABLE5_PREPARED_ROOT)" || \
		(printf '%s\n' 'FABLE5_PREPARED_ROOT is required' >&2; exit 2)
	$(PYTHON) prepare_fable5_memory_cohort.py \
		--source-root "$(FABLE5_SOURCE_ROOT)" \
		--output-root "$(FABLE5_PREPARED_ROOT)" \
		--manifest configs/datasets/fable5-top-level-memory-cohort.json
	$(PYTHON) aggregate_sensitive_token_scan.py \
		--manifest configs/datasets/fable5-top-level-memory-cohort.json \
		--source-root "$(FABLE5_PREPARED_ROOT)" \
		--output experiments/results/fable5-sensitive-token-scan-2026-07-30.json
	$(PYTHON) longitudinal_memory_cohort_expansion.py \
		--trace-commons-manifest configs/datasets/trace-commons-memory-full-cohort.json \
		--trace-commons-root "$(TRACE_COMMONS_ROOT)" \
		--fable-manifest configs/datasets/fable5-top-level-memory-cohort.json \
		--fable-root "$(FABLE5_PREPARED_ROOT)" \
		--output experiments/results/longitudinal-memory-cohort-expansion-2026-07-30.json \
		--summary experiments/summaries/longitudinal-memory-cohort-expansion-2026-07-30.md

# Runs the frozen 17-unit, five-arm, five-repeat state-selection experiment.
# The endpoint must be loopback, while source traces, model inputs/responses, and
# the unminimized base result remain in explicit internal paths outside Git.
longitudinal-memory-local-model:
	@test -n "$(TRACE_COMMONS_ROOT)" || \
		(printf '%s\n' 'TRACE_COMMONS_ROOT is required' >&2; exit 2)
	@test -n "$(FABLE5_PREPARED_ROOT)" || \
		(printf '%s\n' 'FABLE5_PREPARED_ROOT is required' >&2; exit 2)
	@test -n "$(LONGITUDINAL_LOCAL_ENDPOINT)" || \
		(printf '%s\n' 'LONGITUDINAL_LOCAL_ENDPOINT is required' >&2; exit 2)
	@test -n "$(LONGITUDINAL_RAW_AUDIT_DIR)" || \
		(printf '%s\n' 'LONGITUDINAL_RAW_AUDIT_DIR is required' >&2; exit 2)
	@test -n "$(LONGITUDINAL_BASE_RESULT)" || \
		(printf '%s\n' 'LONGITUDINAL_BASE_RESULT is required' >&2; exit 2)
	@test -n "$(LOCAL_TOKENIZER_PYTHON)" || \
		(printf '%s\n' 'LOCAL_TOKENIZER_PYTHON is required' >&2; exit 2)
	@test -n "$(LOCAL_MODEL_SNAPSHOT)" || \
		(printf '%s\n' 'LOCAL_MODEL_SNAPSHOT is required' >&2; exit 2)
	$(PYTHON) longitudinal_memory_local_model.py \
		--trace-commons-manifest configs/datasets/trace-commons-memory-full-cohort.json \
		--trace-commons-root "$(TRACE_COMMONS_ROOT)" \
		--fable-manifest configs/datasets/fable5-top-level-memory-cohort.json \
		--fable-root "$(FABLE5_PREPARED_ROOT)" \
		--experiment-config configs/experiments/longitudinal-memory-model-human-replication-2026.json \
		--model-manifest configs/models/qwen3.5-9b-optiq-4bit-mlx-runtime-0.31.2.json \
		--endpoint "$(LONGITUDINAL_LOCAL_ENDPOINT)" \
		--raw-audit-dir "$(LONGITUDINAL_RAW_AUDIT_DIR)" \
		--output "$(LONGITUDINAL_BASE_RESULT)" \
		--independent-runs 5 \
		--timeout-seconds 180 \
		--max-completion-tokens 256 \
		--tokenizer-python "$(LOCAL_TOKENIZER_PYTHON)" \
		--model-snapshot "$(LOCAL_MODEL_SNAPSHOT)"

# Verifies and minimizes one completed local-model run. Only this
# source-stratified aggregate is suitable for the repository.
longitudinal-memory-local-finalize:
	@test -n "$(LONGITUDINAL_RAW_AUDIT_DIR)" || \
		(printf '%s\n' 'LONGITUDINAL_RAW_AUDIT_DIR is required' >&2; exit 2)
	@test -n "$(LONGITUDINAL_BASE_RESULT)" || \
		(printf '%s\n' 'LONGITUDINAL_BASE_RESULT is required' >&2; exit 2)
	$(PYTHON) longitudinal_memory_local_finalize.py \
		--raw-audit-dir "$(LONGITUDINAL_RAW_AUDIT_DIR)" \
		--base-result "$(LONGITUDINAL_BASE_RESULT)" \
		--max-completion-tokens 256 \
		--output experiments/results/longitudinal-memory-local-model-replication-2026-07-30.json \
		--summary experiments/summaries/longitudinal-memory-local-model-replication-2026-07-30.md

# Drives independent PostgreSQL sessions through deterministic failure,
# promotion, withdrawal, exposure, revocation, and deletion schedules. The
# runner refuses every Kubernetes context except the disposable colima lab.
memory-h5-concurrency:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) \
		tests/run_trace_commons_memory_h5_concurrency.py --timeout 30

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
