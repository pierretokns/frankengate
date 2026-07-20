# Analytics, LLMOps, and observability vocabulary

These terms overlap, but they describe different layers of FrankenGate:

| Term | FrankenGate meaning |
|---|---|
| Observability | Raw and nearline telemetry: logs, traces, metrics, tool calls, provider outcomes, and replay evidence. |
| LLMOps | Operational lifecycle: model/provider catalog and pricing sync, routing policy, evaluations, prompt/model revisions, deployment, budgets, and promotion gates. |
| Analytics | Derived views and decisions built from telemetry and LLMOps records: team/user dashboards, cost and latency trends, quality scores, friction analysis, and recommendations. |
| Data/skill flywheel | Governed feedback loop that turns approved traces and evaluations into dataset revisions, skill proposals, or model improvements. |

Pricing mirroring is primarily an **LLMOps/model-catalog** operation. Its
history and dashboards are analytics products, and its fetch/validation events
are observable, but calling the mirror itself “analytics” would obscure its
operational role.

The scheduled GitHub workflow publishes validated, attributed snapshots under
`docs/data/pricing`, which GitHub Pages can serve. The workflow must use an
approved source URL and retain the source and retrieval timestamp in each
envelope.
