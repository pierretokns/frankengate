# Day-2 trace delivery and rollout runbook

This runbook covers the failure modes that must remain safe after an A2A or
Agent Card deployment is live. Observability is deliberately best effort: a
collector outage must not turn a completed inference or task response into a
gateway failure.

## Trace delivery

The OTel plugin persists a privacy-safe replay record first when durable replay
is configured, then attempts collector delivery after the response is written.
The request context is not used for either operation, so client disconnects do
not cancel completed trace delivery.

Collector delivery has two bounded layers:

1. The immediate export makes three attempts with short backoff.
2. A bounded in-memory queue holds failed deliveries for up to five more
   worker attempts, with exponential backoff capped at 30 seconds.

The queue capacity is 256 jobs per plugin instance. When it is full, the job is
dropped and the durable replay record remains the recovery source. The retry
worker is stopped during plugin cleanup and never blocks the request path.

Watch these metrics by configured service name:

- `bifrost_otel_trace_exports_total`
- `bifrost_otel_trace_export_errors_total`
- `bifrost_otel_trace_export_retries_total`
- `bifrost_otel_trace_export_retry_drops_total`
- `bifrost_otel_trace_export_retry_exhausted_total`
- `bifrost_otel_trace_export_retry_queue_depth`

Alert on a sustained increase in export errors, any retry-queue drops, or a
queue depth that remains near capacity. A replay record is not an automatic
collector replay across a process restart; operators must use the configured
replay-store recovery workflow. Replay records are tenant-scoped, redacted by
default, integrity checked, and retained only for the configured period.

## Rollout gates

Model and Agent Card candidates carry an immutable experiment and revision.
`routing.RolloutPolicy` deterministically assigns subjects and evaluates a
candidate using bounded sample, error-rate, p95-latency, and cost gates.

- Fewer than `min_samples` produces `pending`; it cannot be promoted.
- Malformed policy or metrics produce `rejected` and fail closed.
- Any threshold breach produces `rejected` with a stable reason.
- Only `approved` decisions may be promoted.
- Revision promotion is monotonic; stale revisions cannot overwrite active
  state.
- The previous active revision is retained as the last-known-good (LKG)
  target. Rollback is explicit and records an operator reason.

Trace and audit evidence should include the experiment, revision, gate state,
decision reason, sample count, error rate, p95 latency, and cost per request.
Do not put tenant IDs, credentials, prompts, tool arguments, or Agent Card
content in rollout attributes.

## Operator response

For an unhealthy candidate:

1. Confirm the rollout revision and gate reason from the operator snapshot and
   trace attributes.
2. Stop promotion and rollback to the retained LKG revision.
3. Verify that new requests are assigned to the LKG and that the candidate's
   trace/error rate falls.
4. Investigate collector health separately; OTel loss is a degraded
   observability condition, not permission to accept an unsafe candidate.
5. Reconcile durable audit and replay records after the incident.

The readiness contract remains authoritative for security/configuration
authority freshness. Trace delivery degradation must be visible in telemetry
and diagnostics, but must not silently weaken authentication, authorization,
revocation, budget, or policy enforcement.
