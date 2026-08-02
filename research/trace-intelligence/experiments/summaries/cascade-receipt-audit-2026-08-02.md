# Cross-cohort retrieval-cascade receipt audit

This audit recomputes stage deltas from existing independent receipts. It does
not pool raw examples, create new labels, or turn public proxies into
enterprise semantic outcomes. The machine-readable result is
[cascade-receipt-audit-2026-08-02.json](../results/cascade-receipt-audit-2026-08-02.json).

## Findings

| Comparison | Measured result | Interpretation |
|---|---:|---|
| WMH-BIRD dense vs lexical (`44` cases) | MRR `+.143886`, Recall@1 `+.204546`, compatible-selection `+.017045`, invalid-selection `−.136364` | Dense retrieval is a useful broad-recall layer on this proxy, but its compatibility gain is small relative to its ranking gain. |
| WMH-BIRD frontier vs dense (`44` cases) | MRR `+.014393`, Recall@1 `0`, compatible-selection `+.519832`, invalid selections `−3.386364` per case | Frontier review mainly removes incompatible shortlist noise; it does not discover more top-1 targets here. |
| Alias frontier vs exact (`14` targets, `8` NILs) | MRR `+.107143`, Recall@1 `+.214286`; both proposed on `100%` of NILs | Ranking and refusal are separate problems. Frontier review cannot be an acceptance gate without an explicit NIL/refusal mechanism. |
| Fold-local adapter vs dense (`44` cases) | MRR `+.007765`, Recall@1 `+.022727`, Recall@5 `−.022727`, invalid selections unchanged | Small labelled reranking gains do not justify a universal custom embedding. |
| Claude-history project adaptation (`37` projects, `404` sessions) | Prompt MRR `+.029873`; all-message MRR `+.021652` | Scoped lexical adaptation can help when the baseline has headroom. |
| DataClaw project adaptation (`10` projects, `545` sessions) | Combined MRR `+.085111`; tool-only MRR `−.009310` | Adaptation is task/field dependent and can regress the tool lane; it requires per-view monitoring and rollback. |
| Trajectory-aware model vs prompt-only (`16` cases) | Prompt abstained `16/16`; trajectory abstained `2/16`, made `8` correct and `6` false-positive predictions, with `9` replayable outputs | Trajectory context adds signal but also creates a false-positive tail and higher cost; use it selectively. |
| Identifier-aware reranker (`17` cases) | MRR `.736567`, Recall@1 `.647059`, collision-before-target `0` | Structured identity and scope are safety features, not merely ranking features. |

## Architecture decision

The receipts support this ordering:

```text
scope + authority + immutable identifiers
  -> exact / lexical / termhood candidate recall
  -> optional dense expansion
  -> cheap labelled reranker
  -> selective frontier or human review
  -> deterministic compatibility and changed-system gates
  -> independent replay
  -> versioned artifact, eval, or skill proposal
```

The audit rejects three tempting shortcuts:

1. **Dense-only reuse:** improves recall but leaves incompatible candidates.
2. **Frontier-only acceptance:** improves shortlist quality but proposes on NILs.
3. **One global adapter:** helps some views and regresses others, especially
   tool-only retrieval.

## Next empirical gate

Run the same factorial on an authorized enterprise cohort with repeated natural
intents and independent labels for same-surface/different-system, temporal,
result-preserving, and irrelevant candidates. Keep latency/token budgets fixed,
and measure not just Recall/MRR but changed-system replay, false promotion,
correction burden, user acceptance, and downstream task success. The current
receipts establish the cascade mechanics; they do not establish enterprise
skill learning or semantic alias quality.

## Claim boundary

The result is a cross-receipt consistency and comparison audit. It is not a new
causal experiment and must not be cited as proof that embeddings, frontier
models, or adaptation improve enterprise work.
