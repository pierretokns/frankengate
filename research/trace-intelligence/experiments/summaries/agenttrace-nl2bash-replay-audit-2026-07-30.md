# AgentTrace loss-aware admission and NL2Bash replay audit

**Run date:** 2026-07-30

**Source:** [pagarsky/agent-trace @
`4b05b2f00eea267a5bb4d841c228059d1bf9ac0c`](https://huggingface.co/datasets/pagarsky/agent-trace/tree/4b05b2f00eea267a5bb4d841c228059d1bf9ac0c),
Apache-2.0

## Bottom line

AgentTrace is a useful tool-telemetry and bounded replay corpus, but it is not
the causal-memory benchmark the research plan previously assumed.

All 1,400 source rows, 4,039 LLM steps,
and 3,609 tool spans project to
7,648 canonical lane events with zero silent loss.
However, 3,599 LLM tool proposals have zero shared
call IDs with executions, and the release contains collection completion rather
than a task-correctness verdict.

The bounded executor attempted 400 historical
NL2Bash task/model rows. It safely executed both the last recorded bash command
and the pinned upstream gold command for 17 rows;
9 had identical stdout and exit status
(0.529 among executable rows).
Unsupported shell constructs remain refused. This is a deterministic task proxy,
not proof of semantic correctness.

## Corpus and representation

- 1,400 traces: 1,000 MBPP and 400 NL2Bash.
- Two model strata: {"Qwen/Qwen3-0.6B":700,"Qwen/Qwen3-1.7B":700}.
- 3,609 tool spans:
  {"bash":843,"final_answer":1313,"python_interpreter":1453}.
- 0 explicit tool-parent edges.
- Fixture: 38 files,
  tree digest `9e702abc531e150cc312331b2661f4b5d4388a2c9fcc9d29e0cc526d43fbb325`.
- Raw traces, prompts, commands, outputs, and fixture contents remain outside Git.

## Bounded replay results

| Model | Selected | Executed | Equivalent | Rate | Unsupported/timeout | No bash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen/Qwen3-0.6B | 200 | 6 | 3 | 0.500 | 192 | 2 |
| Qwen/Qwen3-1.7B | 200 | 11 | 6 | 0.545 | 189 | 0 |

Status counts: `{"candidate_and_gold_unsupported":292,"candidate_unsupported":7,"executed":17,"gold_unsupported":82,"no_historical_bash_command":2}`.

The executor uses fixed binaries and argument vectors; it never invokes a shell,
disables arbitrary commands by construction, rejects mutation/execution flags,
validates paths against a fresh fixture copy, and records only aggregate hashes.
It does not claim OS-level isolation.

## Why this does not complete E6

1. AgentTrace has no independent task-correctness field.
2. The upstream MIT reference provides a gold command, not an expected stdout or
   filesystem-state digest.
3. Historical traces contain no no-memory, relevant, placebo, or curated
   procedure exposure.
4. Model sampling seeds are absent.
5. A matching stdout and exit code can still be semantically incomplete.

The earlier plan's statement that AgentTrace already provides a deterministic
task verifier was too strong. The next experiment must add verifier-owned output
and state digests, frozen seeds, and the four intervention arms before reporting
a causal procedural-memory effect.

## Reproduce

Keep the two pinned datasets outside Git, then run:

```bash
python agenttrace_replay_audit.py \
  --agenttrace /private/research-cache/agenttrace/data/agenttrace.parquet \
  --reference /private/research-cache/nl2bash/data/train.parquet \
  --fixture /private/research-cache/agenttrace/testdata \
  --output-json experiments/results/agenttrace-nl2bash-replay-audit-2026-07-30.json \
  --output-markdown experiments/summaries/agenttrace-nl2bash-replay-audit-2026-07-30.md
```

Result content hash: `4c38c694817d02e90a8944e4a877ea660a4e4aea0621f584a2150d36a8164cef`.
