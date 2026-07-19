# Governance and alerting metrics

Prometheus is the primary scrape contract for operating governance sync and
overdraft notifications. OpenTelemetry exporters receive the same low-cardinality
control-plane measurements when configured.

| Metric | Type | Operational meaning |
| --- | --- | --- |
| `bifrost_governance_sync_ready` | gauge | Pod has completed a fresh authority snapshot (`1`) or is fenced (`0`). |
| `bifrost_governance_sync_outbox_depth` | gauge | Unconsumed durable invalidation events observed by the pod. |
| `bifrost_governance_sync_consumer_lag` | gauge | Event-ID distance between the pod cursor and the durable outbox. |
| `bifrost_governance_sync_reload_latency_seconds` | gauge | Most recent authority reload duration. |
| `bifrost_governance_sync_wakeups_total` | counter | Database notification wakeup hints. Notifications are hints; the outbox is authoritative. |
| `bifrost_governance_sync_listener_reconnects_total` | counter | Listener reconnects, useful for detecting database/network churn. |
| `bifrost_governance_notifier_deliveries_total{outcome}` | counter | Bounded notification outcomes (`delivered`, `failed`, `dropped`, or `other`). |

Recommended alerts should combine readiness and lag rather than alerting on a
single transient notification: page when readiness is zero beyond the startup
budget, or when consumer lag remains non-zero for the agreed control-plane
SLO. Notification delivery failures should alert separately from inference
traffic so a disabled email/SNS adapter cannot hide a governance-sync failure.
