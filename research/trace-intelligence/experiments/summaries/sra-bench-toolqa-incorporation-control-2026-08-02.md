# SRA-Bench ToolQA incorporation control — 2026-08-02

## Protocol

This is a bounded frontier-model execution pilot using one fixed instance from
each of ToolQA's 14 skill families. All arms used the same ReAct engine, the
same extracted public ToolQA corpus, the same 15-step limit, and the same
Codex-subscription-backed `gpt-5.6-luna` endpoint:

1. no skill;
2. BGE top-1 retrieved skill;
3. gold-skill oracle.

The benchmark's strict evaluator was used unchanged. Raw prompts, transcripts,
and external corpus contents remain outside the repository; only hashes and
aggregate metrics are committed.

## Results

| arm | strict correct | accuracy | finished | BGE/gold skill identity |
|---|---:|---:|---:|---:|
| no skill | `4/14` | `.2857` | `14/14` | n/a |
| BGE top-1 | `7/14` | `.5000` | `14/14` | `6/14` exact gold hits |
| gold-skill oracle | `7/14` | `.5000` | `14/14` | `14/14` by construction |

The independent verifier passed all checks. Dense retrieval therefore produced
a `+3/14` strict accuracy lift over no-skill on this fixed stratified cohort,
while matching the gold-skill oracle's aggregate score despite only `6/14`
top-1 retrieval hits.

## What this establishes

- A dense capability retriever can improve terminal task success, not merely
  candidate recall, on a bounded public tool-use cohort.
- Retrieval quality is not the only bottleneck: the oracle did not beat BGE on
  this cohort, and BGE succeeded on some tasks with a non-gold skill.
- The remaining failures include incorporation and answer-format failures even
  when the tool observation was correct. The strict score should not be
  reinterpreted as a semantic enterprise outcome.

## What it does not establish

This is not evidence of enterprise transfer, corporate alias quality, causal
skill improvement, changed-system robustness, authority safety, or user
productivity. It is one frontier model, 14 tasks, and one public benchmark
environment. It justifies the next experiment: a powered, family-disjoint
incorporation study with independent semantic scoring, irrelevant-skill NILs,
and changed-system replay.

## Receipts

- [content-minimized result](../results/sra-bench-toolqa-incorporation-control-2026-08-02.json)
- [independent verification](../results/sra-bench-toolqa-incorporation-control-verification-2026-08-02.json)
- [dense retrieval control](sra-bench-toolqa-lexical-dense-comparison-2026-08-02.md)
