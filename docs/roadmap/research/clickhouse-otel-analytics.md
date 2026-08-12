# ClickHouse analytics for A2A and LLM operations

## Decision

FrankenGate should not revive LiteLLM's historical native ClickHouse callback or add a direct ClickHouse dependency to the request path. Keep OpenTelemetry as the canonical telemetry transport and support ClickHouse through an OpenTelemetry Collector deployment. Add a narrow, typed usage-fact projection only if billing or quota queries need a stable table that is not convenient to derive from spans.

This keeps A2A task, handoff, tool, provider-attempt, retry, policy, and credential-audit events correlated by W3C trace context while avoiding a second, request-coupled delivery system.

## Evidence from LiteLLM

Current LiteLLM main (August 2026) has no native ClickHouse callback or ClickHouse integration in its callback registry. Its current logging guidance favors OpenTelemetry, object storage, queues, databases, and custom callbacks: [LiteLLM logging](https://docs.litellm.ai/docs/proxy/logging).

Older LiteLLM releases did contain `clickhouse.py`. The callback auto-created `default.spend_logs`, inserted one row per event, had no batching, durable queue, deduplication, schema migration, retention policy, or useful ordering key, and swallowed insert failures. Its beta test was skipped. We do not copy that design: [historical callback](https://github.com/BerriAI/litellm/blob/v1.50.0/litellm/integrations/clickhouse.py), [historical test](https://github.com/BerriAI/litellm/blob/v1.27.7/litellm/tests/test_clickhouse_logger.py).

## Operating shape

1. FrankenGate emits bounded, low-cardinality OTel spans and metrics for A2A tasks, messages, handoffs, tools, model attempts, retries/fallbacks, guardrails, push delivery, and credential-audit outcomes.
2. The Collector routes telemetry to ClickHouse using exporter-side batching, retry, and a persistent sending queue. The ClickHouse exporter supports traces, logs, and metrics and should be configured with operator-managed DDL: [Collector ClickHouse exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/exporter/clickhouseexporter/README.md).
3. Prompts, responses, tool arguments/results, tokens, and credentials remain suppressed by default. Store hashes, sizes, classifications, or governed encrypted references instead of content in the analytics plane.
4. If a product/billing fact table is needed, use an allowlisted schema with `event_id`, `trace_id`, `span_id`, `tenant_id`, `workflow_id`, `task_id`, `agent_id`, `provider`, `model`, `attempt_number`, `status`, timestamps, token/cost facts, retry count, cache hit, and error type. Make `event_id` the deduplication key.
5. Apply explicit TTLs to detailed data and materialized hourly/daily rollups for cost, latency, error rate, throughput, and queue health. Partition by event date and order around tenant/time/trace access patterns.

## Day-2 requirements

- Telemetry failure must not fail an inference or A2A request.
- Collector queue overflow must be observable and have an explicit drop/block policy.
- Persistent queue storage is required for restart recovery where delivery matters.
- Dashboards must show exporter backlog, retry age, dropped records, schema errors, and privacy-policy violations.
- Test redaction, bounded attributes, exporter outage behavior, replay/deduplication, retention, and rollup correctness without contacting a live ClickHouse service.
