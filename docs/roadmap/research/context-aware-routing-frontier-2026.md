# Context-aware routing frontier review (2026)

Status: research and evaluation plan; no router is promoted by this document.

## Decision

FrankenGate should treat routing as a policy-and-evidence problem, not as a
single prompt classifier. The candidate router must consume a bounded,
privacy-reviewed request summary; model and provider capability metadata; recent
multi-turn history features; current health, queue, quota and price signals; and
the applicable tenant/model policy. It must emit a versioned decision receipt
and be shadowed against a deterministic policy baseline before it can affect
production traffic.

## Frontier patterns worth testing

| Pattern | What it contributes | FrankenGate experiment |
|---|---|---|
| ICL-Router | In-context learned representations of model capability rather than a fixed hand-written taxonomy | Compare capability embeddings against policy-only routing on frozen enterprise tasks |
| Long-context-aware routing | Treats context length and serving cost/latency as first-class routing variables | Add prompt-token bands, cache locality, and provider context limits to candidate scoring |
| MTRouter | Joint history/model embeddings for cost-aware multi-turn routing | Measure whether history features improve quality without leaking raw conversation content |
| Lookahead routing | Uses an early response signal to decide whether escalation is worthwhile | Test only in opt-in shadow/canary mode; bound extra tokens and duplicate side effects |
| CASTER/task-aware routing | Uses task and graph context for multi-agent model selection | Evaluate on MCP/tool traces with a hard prohibition on policy bypass |
| Past-performance retrieval | Routes using retrieved, domain-specific prior outcomes | Use redacted evaluation records and require cohort isolation, decay, and rollback |

## Required receipt

Every decision should record only bounded, redacted features:

- router revision and feature-schema revision;
- candidate models after governance filtering;
- context-length band, modality, tool-use flag, and task/domain class;
- policy, authority, budget, health and quota revisions;
- selected model, fallback chain, reason codes, and deterministic assignment key;
- shadow alternatives and quality/cost/latency outcomes when available.

Raw prompts, secrets, provider credentials, and unredacted retrieved documents
must not enter the router training or analytics store by default.

## Acceptance gates

1. Offline replay beats the current policy baseline on quality at a fixed cost
   budget and does not regress p50/p95 latency beyond the approved envelope.
2. Cross-tenant and stale-policy adversarial cases fail closed before candidate
   exposure; shadow and progressive results obey the same rule.
3. Multi-turn and long-context cohorts are evaluated separately from short-turn
   cohorts; no aggregate score may hide a tail failure.
4. Shadow mode is side-effect-free. MCP/tool execution, billing, mutations and
   provider retries cannot be duplicated by experimentation.
5. Promotion requires a frozen holdout, human MR approval, signed model/data
   manifests, rollback metadata, and an observed stability window.

## Sources

- [ICL-Router, AAAI 2026](https://ojs.aaai.org/index.php/AAAI/article/view/40628)
- [Accuracy Is Speed: long-context-aware routing](https://arxiv.org/abs/2604.15732)
- [MTRouter: cost-aware multi-turn routing](https://aclanthology.org/2026.acl-long.2045/)
- [Lookahead Routing, NeurIPS 2025](https://papers.neurips.cc/paper_files/paper/2025/file/552456ddb6f4b2956b2933ab83f56df0-Paper-Conference.pdf)
- [CASTER: context-aware strategy routing](https://arxiv.org/abs/2601.19793)
- [Generalising routing using past-performance retrieval](https://aclanthology.org/2026.eacl-srw.22.pdf)
