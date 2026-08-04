# ToolQP-inspired query-planning probe (2026-08-09)

ToolQP models tool retrieval as iterative query planning: decompose a request
into sub-tasks, generate targeted queries, and retrieve tools dynamically. The
paper trains this policy with synthetic trajectories and RLVR; that full
training result is not reproduced here. See the [ACL 2026 paper](https://aclanthology.org/2026.findings-acl.2090/).

This probe tests only the portable mechanism on eight public TRAJECT-Bench
cases selected round-robin across domains:

1. retrieve a domain lexical top-16 shortlist without appending target names;
2. show the query and a small initial shortlist to Luna;
3. ask for three subtask-oriented queries, without target labels or tool
   outputs;
4. union lexical results for the original and generated queries;
5. rank that union deterministically.

## Result

| Arm | Target coverage in top-16 | MRR | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|---:|
| Domain lexical baseline | 0.666667 | 0.348333 | 0.041667 | 0.250000 | 0.541667 |
| Query-planning union | **0.750000** | **0.562500** | **0.083333** | **0.458333** | **0.625000** |

On this small public probe, query planning increased candidate coverage by
8.3 percentage points and improved MRR by 0.214. The gain is promising because
it attacks the coverage ceiling identified by the no-target-append reranker
control; it is not evidence that ToolQP's trained policy transfers to
enterprise SQL or tool artifacts.

## Hard edges and next test

- The planner is a frontier model prompted to emit three queries; it is not
  ToolQP's trained model or RLVR objective.
- TRAJECT-Bench has public tool names/descriptions and synthetic task labels,
  not validated enterprise artifacts, wrong-system aliases, or human utility
  labels.
- The eight-case result needs a larger, family-disjoint pool and a cost/latency
  comparison against structured aliases, dense retrieval, and reranking.
- A Frankengate promotion gate still requires artifact execution/validator
  success, temporal/schema scope checks, and human or SME labels.

Receipts:

- [probe result](../results/traject-bench-query-planning-probe-2026-08-09.json)
- [independent verification](../results/traject-bench-query-planning-probe-verification-2026-08-09.json)
- [runner](../../traject_bench_query_planning_probe.py)
- [verifier](../../verify_traject_bench_query_planning_probe.py)

Raw model outputs remain external under `/private/tmp`; only hashes and
aggregate metrics are committed.
