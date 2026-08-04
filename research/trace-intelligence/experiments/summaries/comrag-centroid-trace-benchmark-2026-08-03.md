# ComRAG centroid-memory trace benchmark

## What was reproduced

ComRAG maintains static knowledge plus high- and low-quality historical QA
stores. New questions join the nearest centroid only when similarity exceeds a
threshold; otherwise a new cluster is created. Similar questions can replace a
lower-quality representative, and query routing distinguishes high-quality
reuse from low-quality avoidance. These details are from the ACL Industry
paper, not an inferred “average embeddings” simplification:
[ComRAG](https://aclanthology.org/2025.acl-industry.53/) (see the paper's
centroid and dynamic-store sections).

## Benchmark

- Dataset: 40 chronological sessions from the pinned
  `zhiyaowang/dataclaw-zhiyaowang` revision, fetched through the Hugging Face
  rows API; 28 train and 12 test sessions were parseable.
- Representation: TF-IDF word/bigram vectors, so this isolates memory
  organization from neural-model choice.
- Quality proxy: sessions with explicit tool errors are low quality; all other
  sessions are high quality.
- Recurrence proxies: normalized tool-shape overlap and project match. These
  are not semantic task labels, artifact correctness, or user outcomes.
- Baseline: chronological full-history nearest-session retrieval.
- ComRAG arm: bounded online centroid store, plus high/low quality routing.

The raw session content is not committed. The receipt contains the provider
payload hash and aggregate metrics only:
[`comrag-centroid-trace-benchmark-2026-08-03.json`](../results/comrag-centroid-trace-benchmark-2026-08-03.json).

## Results

| Threshold | Max clusters | Static shape hit | Centroid shape hit | Static project hit | Centroid project hit | Final clusters |
|---:|---:|---:|---:|---:|---:|---:|
| `0.00` | `4` | `.333` | `.250` | `.667` | `.583` | `1` |
| `0.25` | `4` | `.333` | `.250` | `.667` | `.583` | `4` |
| `0.25` | `12` | `.333` | `.333` | `.667` | `.667` | `11` |
| `0.50` | `12` | `.333` | `.333` | `.667` | `.667` | `12` |

The high/low quality-routed store matched the centroid result on this sample;
it did not add a measurable recurrence lift.

## Interpretation

1. Centroid compression can preserve full-history recurrence when the memory
   budget is large enough (`11–12` clusters here), but not under aggressive
   compression (`4` clusters).
2. The threshold/budget tradeoff is real: lower memory produced a measurable
   proxy regression, not a free storage win.
3. Quality routing did not help on this cohort, so the ComRAG high/low split is
   not automatically useful merely because error metadata exists.
4. This is a mechanics and proxy-recurrence result. It does not establish
   answer quality, artifact reuse, authority safety, stale-fact handling,
   conflict resolution, or user benefit.

## Next gate

Run the same online comparison on consented, timestamped traces with validated
outcomes and explicit stale/conflict mutations. Compare static, centroid, and
hybrid stores under a fixed memory, latency, and token budget; require
identifier/scope/epoch preservation and changed-system replay before any
centroid becomes a production memory representation.
