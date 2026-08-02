# Corporate trace artifact-learning status update (2026-08-09)

This update consolidates the latest independent runs. It is a status ledger,
not a claim that the full enterprise research objective is complete.

## What is now supported by evidence

### 1. Validated artifact mechanics

Recorded SQL/tool success must be independently executed and validated before
it becomes an artifact. In the BIRD trace corpus, only **76/193** executable
trace candidates matched the independent gold result. Typed parameter replay
then succeeded **75/75** in a controlled cohort. The lesson is to store
validated, parameterized capsules with scope, schema, authority, freshness,
and replay validators—not raw successful calls.

### 2. Retrieval has two separate jobs

The no-target-append TRAJECT-Bench reranker control showed that Luna can improve
ordering among already-covered candidates (MRR `.360 → .886`) while target
coverage remains `.458`. A ToolQP-inspired query-planning probe improved
public-tool coverage (`.667 → .750`) and MRR (`.348 → .563`) on eight diverse
cases. These are candidate-generation/ranking results, not artifact acceptance.

When applied to the harder BIRD SQL artifact cohort, however, query planning
produced **0/16** executable matches at @1, @5, and @10, just like the lexical
baseline. The artifact pool contained almost no naturally repeated compatible
procedures. Query planning cannot create a missing artifact.

### 3. Trajectory supervision is adaptable but incomplete

The LRAT public sample audit found 10 completed trajectories, 280 ordered
steps, 130 tool calls, and 130 non-empty outputs. The samples contained no
explicit correctness, failure, friction, reward, or enterprise-artifact
fields. LRAT is therefore a good candidate-coverage method to adapt, not a
complete corporate skill-learning dataset.

### 4. Structured tool fields are useful metadata, not a retrieval replacement

The field-aware TRAJECT-Bench probe evaluated 5,297 domain-scoped records with
name-only, name-plus-description, field-aware, and identifier/schema arms. On
1,975 hard records, field-aware Recall@10 was `.423` versus `.421` for name-only,
but MRR was lower (`.631` versus `.671`) and descriptions reduced MRR to `.574`.
This is enough reason to preserve parameter/API/output fields for later
compatibility checks, but not enough reason to promote field-weighted lexical
ranking or claim semantic alias resolution.

### 5. Older vocabulary ports remain narrow

The TermSuite/Termolator-style port provides interpretable candidate terms:
termhood recall was `.358` when the schema vocabulary was represented but only
`.015` on held-out transfer. The AcronymExpansion-style port passed `8/8`
synthetic ambiguity/NIL probes. Both remain offline review primitives; neither
has shown enterprise alias precision, embedding lift, or skill improvement.

### 6. Custom embedding evidence is not yet promotion-positive

The fold-local MATM adapter was effectively neutral (`Recall@20 .5301 → .5331`,
MRR `.3315 → .3300`, intervals crossing zero). The database-family-held-out
schema adapter underperformed deterministic structured ranking and had 51.2%
collision-before-target. Finance-specific embeddings performed well on a
finance corpus, but that does not establish corporate trace transfer. The
current evidence supports testing domain adapters in a shadow lane only after
SME-labelled aliases, NILs, wrong-system negatives, and downstream utility
labels exist.

### 7. Cross-user insight and skill-gap claims remain unproven

Trace Commons and two-user DataClaw audits show that exact prompt/tool overlap
is low and that harness boilerplate can dominate similarity. Frontier
adjudication can produce a review queue, but there are no independent labels
for business intent, employee capability, satisfaction, collaboration value,
or negative transfer. We cannot yet claim that the system identifies who is
doing the same work or which skills a person is missing.

### 8. Friction mining needs structural review, not keyword labels

The corrected native Codex importer found 47,122 user episodes, 228 adjacent
rephrase pairs, and 273 marker-based error-to-success episodes, but lexical
friction markers had only `.79%` precision against a structured process-exit
proxy. A separate public DataClaw Luna calibration (12 stratified messages,
two calls each) reached 11/12 repeat-label agreement; re-prompt overlap was
friction on 4/6 calls, while lexical markers over-flagged productive work.
This supports a review queue built from event ordering and correction/retry
structure, with independent tool/result outcomes required before eval or skill
promotion. It does not establish satisfaction, intent, or employee skill.

### 9. Dataset fit is a hard gate

The current manifest audit covers 44 pinned public datasets. Only **2/44**
are direct-fit for NL2SQL schema retrieval and **3/44** are direct-fit for
basic trace structure. None are direct-fit for friction recovery, causal skill
improvement, cross-user similarity, or reviewed term/alias quality. The rest
are mechanics or proxy corpora. This is why results from WMH-BIRD, BIRD-Interact,
Trace Commons, DataClaw, CodeTraceBench, and MAGIC must remain separate arms;
pooling them would manufacture labels and invalidate the enterprise claims.

### 10. ToolQP's planning and aggregation effects are separable

The official ToolQP method combines iterative query planning, synthetic-trace
SFT, RLVR/GRPO, and peak-rank aggregation. Our bounded inference-stage replay
held the planner outputs fixed and compared aggregation only: peak rank kept
top-16 coverage at `.750` but scored MRR `.419`, versus `.563` for the simpler
query union. This is not a contradiction of the paper; it shows that Frankengate
must measure planner quality, retriever coverage, and aggregation independently
before adopting a trained planner or claiming enterprise artifact value.

The LRAT exposure audit adds a parallel boundary: 598/624 exposed documents in
the public samples were not browsed, so exposure-aware candidate negatives are
available. They are not independently irrelevant labels. Frankengate must
record refusal/authority/cost reasons and require replay or SME outcomes before
turning exposure gaps into hard-negative training data.

## Architecture decision

Keep the smallest governed architecture:

```text
canonical loss-aware trace DAG
  -> exact identifiers + scope/authority filter
  -> lexical / structured candidate recall
  -> optional domain embedding or query-planning expansion
  -> identifier-aware ranking
  -> selective frontier/human review
  -> independent execution, validator, and replay gate
  -> versioned artifact/eval/skill proposal
```

Do not make a custom embedding, graph database, or automatic memory/skill
writer mandatory. Add each only when a frozen hard-negative cohort shows an
absolute retrieval or downstream-utility lift that survives temporal,
project, principal, and changed-system holdouts.

## Next decisive experiments

1. Build a consented enterprise cohort with repeated intents, validated SQL/tool
   artifacts, same-surface/wrong-system negatives, temporal renames, and
   independent human utility labels.
2. Compare exact/identifier, lexical, dense, query-planning, frontier, and
   combined cascades under fixed cost/latency budgets.
3. Replay candidate skills/evals on changed systems with no-skill, placebo,
   mined-artifact, and teacher arms.
4. Measure user outcomes: correction burden, task completion, time-to-success,
   learning, unwanted recommendations, and negative transfer.
5. Publish content-minimized receipts and a sealed evaluation API with MIT,
   CMU, or Harvard partners rather than releasing raw corporate traces.

## Authoritative receipts

- [SQL artifact reuse](bird-trace-artifact-reuse-2026-08-07.md)
- [SQL query-planning probe](bird-artifact-query-planning-probe-2026-08-09.md)
- [TRAJECT-Bench query planning](traject-bench-query-planning-probe-2026-08-09.md)
- [TRAJECT-Bench field-aware retrieval](traject-bench-field-retrieval-2026-08-09.md)
- [LRAT trajectory audit](lrat-trajectory-audit-2026-08-09.md)
- [Older-tool modernization audit](older-tool-modernization-value-audit-2026-08-05.md)
- [Public DataClaw friction calibration](dataclaw-friction-luna-calibration-2026-08-09.md)
- [Dataset-fit audit](../results/dataset-fit-audit-2026-08-04.json)
- [ToolQP peak-rank reproduction](traject-bench-toolqp-peak-rank-2026-08-09.md)
- [LRAT exposure-negative audit](lrat-exposure-negative-audit-2026-08-09.md)
- [Current evidence matrix](current-evidence-matrix-2026-08-06.md)
