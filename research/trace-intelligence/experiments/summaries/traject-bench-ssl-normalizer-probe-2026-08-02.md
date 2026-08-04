# Frontier SSL-style normalization probe (2026-08-02)

This probe tests the part of the SSL paper that the metadata-only ablation
could not test: whether a frontier model can normalize source records into a
grounded scheduling/structural/logical representation. It is a feasibility
probe, not a retrieval, risk, or skill-utility benchmark.

## Protocol

- Source: pinned public TRAJECT-Bench `tools/all_tools.json`.
- Sample: two deterministic tools from each of ten domains (`20` total).
- Model: `gpt-5.6-luna` through the Codex harness.
- Output: a constrained JSON schema with exact source identifiers, evidence
  quotes, optional scenes/transitions, and typed logical actions.
- Raw prompts/responses remain in `/private/tmp/ssl-normalizer-probe-20260802`;
  only hashes and aggregate booleans are committed.
- An independent verifier checks receipt integrity, count reconciliation, and
  that the claim boundary does not overstate retrieval or utility.

## Results

| Measure | Result |
| --- | ---: |
| Valid calls | `20/20` |
| Exact tool/API/domain identifier fidelity | `1.000` |
| Evidence substring grounding | `0.9875` |
| Records with every evidence item grounded | `0.950` |
| Mean logical actions emitted | `1.0` |
| Mean structural scenes emitted | `0.0` |
| Mean wall time per call | `12.273s` |

## Interpretation

The frontier model can reliably preserve exact identifiers and produce mostly
source-grounded evidence under a strict schema. However, it emitted no
structural scenes in this sample and only one conservative `CALL` action per
record. In other words, it behaved like a grounded interface/effect summary,
not the richer execution graph that SSL claims helps discovery and risk
assessment. One of twenty records also contained an evidence quote that was
not an exact source substring; the aggregate is a mechanical check, not a
human grounding judgment.

This supports a two-stage design: deterministic identifiers and source-linked
evidence first, followed by review-only scene/effect proposals. It does not
justify automatic skill publication, risk decisions, alias creation, or
embedding training. The next test must use actual multi-step trajectories with
tool dependencies, retries, branches, and independently labeled effects;
single tool descriptions cannot reveal those structural facts.

## Relation to the SSL paper

The paper's reported skill-discovery improvement requires a rich structured
view. This probe shows that a frontier normalizer can produce a safe, mostly
grounded skeleton, but the richest layer is absent when the source lacks
trajectory structure. The missing signal is therefore data/annotation
coverage, not simply a larger prompt or a different vector index.

## Receipts

- [machine-readable result](../results/traject-bench-ssl-normalizer-probe-2026-08-02.json)
- [independent verification](../results/traject-bench-ssl-normalizer-probe-verification-2026-08-02.json)
- [runner](../../traject_bench_ssl_normalizer_probe.py)
- [verifier](../../verify_traject_bench_ssl_normalizer_probe.py)
- [SSL-shaped retrieval proxy](traject-bench-ssl-proxy-2026-08-02.md)
