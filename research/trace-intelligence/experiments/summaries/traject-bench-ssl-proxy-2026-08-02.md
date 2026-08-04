# SSL-shaped structured-field retrieval proxy (2026-08-02)

This is a deterministic ablation inspired by the Scheduling--Structural--
Logical (SSL) skill representation. It is **not** a reproduction of the SSL
paper: TRAJECT-Bench supplies tool metadata and target tool lists, but no
grounded scenes, typed effects, authority decisions, enterprise aliases, or
replay outcomes.

## Protocol

- Dataset: the pinned public TRAJECT-Bench `parallel/` and `sequential/`
  records.
- Candidate pool: the domain-local tool pool, frozen for every arm.
- Cohort: 5,297 records, including 1,975 hard and 2,067 simple records.
- No models, tool endpoints, or recorded outputs were invoked.
- The three proxy projections were fixed before execution:
  - **scheduling:** tool/parent names plus API/domain identifiers;
  - **structural:** tool name plus parameter shape and connected-tool metadata;
  - **logical:** tool/API/domain plus parameter and output metadata.

Each projection scores query-token overlap with its fields. `ssl_rich` combines
the three at fixed weights (`.35/.30/.35`). This tests whether the available
metadata behaves like a useful structured representation; it does not claim
that these fields are true SSL scenes or logical actions.

## Results

### Hard records (1,975)

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| name | `.653222` | `.089015` | `.271746` | `.405251` |
| SSL scheduling proxy | `.647442` | `.088185` | `.264730` | `.405699` |
| SSL structural proxy | `.425240` | `.041257` | `.162471` | `.291558` |
| SSL logical proxy | `.485607` | `.047799` | `.209142` | `.346664` |
| SSL rich proxy | `.521599` | `.055076` | `.232924` | `.371658` |

### Simple records (2,067)

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| name | `.815630` | `.126636` | `.387968` | `.552248` |
| SSL scheduling proxy | `.809558` | `.126177` | `.385179` | `.555566` |
| SSL structural proxy | `.590870` | `.074869` | `.255273` | `.424578` |
| SSL logical proxy | `.706116` | `.100299` | `.324096` | `.500605` |
| SSL rich proxy | `.780923` | `.121727` | `.366691` | `.556775` |

## Interpretation

The scheduling-only projection was effectively a tie with name-only retrieval
and did not improve MRR. Structural and logical projections were substantially
worse on this benchmark. The rich combination recovered some simple-query
Recall@10 (`.556775` vs `.552248`) but lost MRR and was worse on hard-query
Recall@10 (`.371658` vs `.405251`).

This is a **proxy null**, not evidence against SSL. The query text is not
segmented into intent/interface/scene/effect fields, and the benchmark's target
labels are tool names rather than semantic skill outcomes. The result does
show that merely concatenating public metadata into SSL-shaped buckets does
not reproduce the paper's gain. Frankengate needs grounded execution-DAG and
typed-effect extraction, plus reviewed labels, before a richer representation
can be fairly tested.

## Decision

Keep scheduling, structural, and logical projections in the canonical trace
schema as loss-aware views. Do not use these deterministic field weights as a
universal ranker, and do not infer that an SSL normalizer will improve
corporate artifact learning. The next fair test is a consented cohort with
reviewed intent/alias labels, same-surface wrong-system negatives, temporal
renames, and replayable terminal outcomes; compare flat text, a
length-matched outline, grounded SSL projections, and grounded SSL plus
identifier filters under fixed candidate coverage and cost.

## Receipts

- [machine-readable result](../results/traject-bench-ssl-proxy-2026-08-02.json)
- [independent verification](../results/traject-bench-ssl-proxy-verification-2026-08-02.json)
- [runner](../../traject_bench_ssl_proxy.py)
- [verifier](../../verify_traject_bench_ssl_proxy.py)
- [source SSL crosswalk](ssl-representation-crosswalk-2026-08-02.md)
