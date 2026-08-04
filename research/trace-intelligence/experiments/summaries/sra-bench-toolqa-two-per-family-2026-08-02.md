# SRA-Bench ToolQA two-per-family incorporation control — 2026-08-02

## Protocol

This is a family-disjoint expansion of the earlier ToolQA pilot. It uses two
fresh instances from each of ToolQA's 14 skill families (28 tasks total; the
pilot's first instance from each family is excluded). All arms use the same
public ToolQA corpus, ReAct engine, 15-step limit, temperature `0`, 512 output
token limit, and `gpt-5.6-luna` through the Codex-subscription loopback
endpoint:

1. no skill;
2. BGE top-1 retrieved skill;
3. gold-skill oracle.

Raw transcripts remain outside Git. The receipt commits hashes, aggregate
metrics, and a deterministic typed execution audit.

## Results

| arm | strict correct | accuracy | finished | actions | error-like observations | avg steps |
|---|---:|---:|---:|---:|---:|---:|
| no skill | `10/28` | `.3571` | `28/28` | `111` | `26` | `3.96` |
| BGE top-1 | `12/28` | `.4286` | `28/28` | `102` | `16` | `3.64` |
| gold-skill oracle | `14/28` | `.5000` | `28/28` | `85` | `3` | `3.04` |

Relative to no skill, BGE adds `+2/28` strict successes and the gold oracle
adds `+4/28`. The oracle also uses fewer actions and sees fewer deterministic
error-like observations. This is stronger evidence than the 14-task pilot
that skill retrieval and skill incorporation are separate bottlenecks: BGE
helps, but its remaining gap to the oracle is not just top-1 retrieval.

## Semantic check boundary

The full 48 strict failures were not relabeled. A bounded frontier probe over
12 no-skill failures produced 10 `incorrect`, 1 `format_only`, and 1
`correct_semantic` under the normal rubric; the skeptical rubric produced 11
`incorrect` and 1 `correct_semantic`. This confirms that strict scoring has a
small formatting component, but it is not a full semantic adjudication of the
28-task cohort.

## What this establishes

- The dense skill arm improves terminal benchmark accuracy on a fresh,
  family-disjoint cohort.
- Gold skill context still improves over BGE top-1, so retrieval hit rate and
  downstream incorporation both require measurement.
- The typed execution audit exposes a plausible mechanism: no-skill has more
  invalid/error-like observations and actions than BGE, while the oracle has
  fewer. This is diagnostic, not causal proof.

## What this does not establish

This remains a public ToolQA control. It is not evidence of enterprise
transfer, corporate alias/identifier quality, causal user productivity,
changed-system replay, authority safety, skill release utility, or long-run
learning. The error-like observation detector is a deterministic text pattern,
not a semantic tool-quality judge.

## Next experiment

Use the same family-disjoint protocol with an explicit irrelevant-skill arm,
top-`k` progressive disclosure, semantic adjudication on a powered sample, and
changed-environment replay. Then transplant the best arm into the wiki/MCP
matrix tracked in [issue #131](https://github.com/pierretokns/frankengate/issues/131)
so retrieval quality and agent incorporation are evaluated together.

## Receipts

- [content-minimized receipt](../results/sra-bench-toolqa-two-per-family-2026-08-02.json)
- [typed execution auditor](../../sra_bench_toolqa_execution_audit.py)
- [cohort receipt generator](../../sra_bench_toolqa_cohort_receipt.py)
