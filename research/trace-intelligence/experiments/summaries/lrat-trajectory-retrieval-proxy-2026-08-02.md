# LRAT-style exposure-aware retrieval proxy

## Question

When later browsing is used as silver relevance evidence, does a generic dense
retriever beat the trace's original search ordering or lexical ranking over the
same exposed candidate pool?

## Protocol

The ten Apache-licensed LRAT sample trajectories were parsed locally. For each
trajectory, search outputs define the exposed document pool and later
`visit`/`get_document` calls define a stronger-but-silver positive set. Search
order, lexical query/snippet overlap, and local
`sentence-transformers/all-MiniLM-L6-v2` cosine ranking were evaluated on the
same candidates. No raw query, snippet, document ID, or model output was
committed.

## Result

| Arm | MRR | R@1 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: |
| Search order | `.630682` | `.500` | `.700` | `.800` |
| Lexical query/snippet | `.766667` | `.600` | `1.000` | `1.000` |
| Generic MiniLM dense | `.456591` | `.300` | `.500` | `.900` |

All ten trajectories had at least one browsed document in the exposed pool;
the pool contained 624 distinct exposed documents and 26 browsed positives.

## Interpretation

This is the first direct exposure-aware candidate-coverage result in the
program. On this tiny web-search sample, lexical query/snippet matching beats
both the recorded search order and generic dense retrieval. The dense model is
not a better default simply because the supervision came from trajectories.
However, the result is not a failure of trajectory supervision: it evaluates a
zero-shot dense model, not the LRAT training objective. The missing experiment
is a fold-local ranker trained from exposed/browsed/reasoning outcomes, with
unexposed candidates treated as missing data and independent answer/replay
labels.

## Claim boundary

Browsing is a silver relevance signal. The LRAT samples contain no independent
correctness, principal, authority, changed-system, or enterprise artifact
outcome labels. This result therefore supports only a candidate-recall
mechanics decision:

```text
scope/identifier filtering
  -> exposure-aware lexical/dense candidates
  -> trajectory-distilled ranker (once labels and folds exist)
  -> independent outcome/replay validation
```

It does not establish web-answer correctness, corporate alias quality, skill
improvement, or safe artifact promotion.

Receipt: [`lrat-trajectory-retrieval-proxy-2026-08-02.json`](../results/lrat-trajectory-retrieval-proxy-2026-08-02.json)  
Runner: [`lrat_trajectory_retrieval_proxy.py`](../../lrat_trajectory_retrieval_proxy.py)
