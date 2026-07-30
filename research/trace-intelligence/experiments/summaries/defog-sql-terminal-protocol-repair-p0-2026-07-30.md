# Defog terminal-protocol repair and fresh P0

## Result

The arm-independent terminal-protocol repair eliminated the original missing
terminal actions on the complete four-task, three-arm Defog P0. It did **not**
produce evidence that the expert schema-navigation seed improves governed SQL
quality.

| Arm | Original missing terminal | Repaired missing terminal | Original semantic pass | Repaired semantic pass |
| --- | ---: | ---: | ---: | ---: |
| No skill | 1 / 4 | 0 / 4 | 2 / 4 | 2 / 4 |
| Formatting placebo | 2 / 4 | 0 / 4 | 2 / 4 | 2 / 4 |
| Expert seed | 1 / 4 | 0 / 4 | 2 / 4 | 2 / 4 |

All 12 repaired episodes:

- used real native model tool calls;
- inspected or queried the real disposable PostgreSQL database;
- validated the same current authorization epoch and governed identity;
- ended with an explicit `submit_sql`;
- selected a previously executed, authorized attempt;
- produced zero unauthorized observations; and
- retained the frozen model, task set, base prompt, arm artifacts, tool
  schemas, limits, and authority contract.

The repaired content-free result is
`experiments/results/defog-sql-factorial-fold0-terminal-only-p0-2026-07-30.json`
with SHA-256
`f01e9ec93a75bd044d9bb6a1bf6eeb57e0d882e76cf9bb8d32e31318ca653ad1`.
The original result hash is
`508c78b367a791e125f83c5dfdc1f82d2363ef558d9d299812c448fe683ec250`.
The hash-bound comparison is
`experiments/results/defog-sql-terminal-protocol-analysis-2026-07-30.json`.

## The failure and the smallest successful repair

The original raw traces localized the missing terminals to a concrete loop:
after consuming all three accepted SQL-attempt slots, the model continued
calling `execute_sql` until the six-turn ceiling.

The first repair exposed only `submit_sql` and `abstain` after the third
accepted attempt. The real model still emitted `execute_sql`, despite that
tool being absent. This showed that advertised tool availability is not an
enforcement boundary for this pinned MLX/Qwen runtime.

The successful repair has three narrow, arm-independent pieces:

1. enforce the offered-tool set before dispatch;
2. add a structured terminal state to the third attempt observation:
   `remaining_sql_attempts=0`, available actions `submit_sql`/`abstain`, and
   `required_terminal_action=true`; and
3. add a standards-valid protocol-controller user turn requiring one native
   terminal call, while exposing only the two terminal tools.

No correctness feedback, reference SQL, hidden label, or preferred attempt is
added. The model still has to choose a previously executed attempt or abstain.
The controller content hash is
`b7b275156b4dad4708ed53145f40063e865ae324138ab4186e816c3e981b377b`.

An attempted mid-conversation `system` controller was rejected by the pinned
server with `HTTP 404: System message must be at the beginning`; it was
invalidated rather than counted as a model outcome. The runtime receipt records
that failure and the preceding cold-start/timeout failures:
`experiments/manifests/defog-terminal-protocol-p0-runtime-2026-07-30.json`.

## Paired outcome

The repaired primary endpoint is semantic correctness plus policy acceptance
with no unauthorized observation. On the four paired tasks:

| Contrast | Wins | Losses | Ties | Risk difference |
| --- | ---: | ---: | ---: | ---: |
| Expert vs formatting placebo | 0 | 0 | 4 | 0.00 |
| Expert vs no skill | 0 | 0 | 4 | 0.00 |

Every arm passed the same two task hashes and failed the same two task hashes.
The protocol gate therefore passes, but the preregistered intervention-
sensitivity requirement—at least two more expert wins than losses against the
placebo—fails.

The visible 23-task P1 effect screen and all hidden families remain sealed.
Running a trace-mined arm now would conflate an unqualified model/procedure
pair with trace-mining efficacy.

## Runtime evidence

The local stack used:

- pinned `mlx-community/Qwen3.5-9B-OptiQ-4bit` revision
  `319aed167e31e0bf81ddba0c23f8d218a15be612`, loopback only, with prompt
  cache size zero;
- PostgreSQL 16.12 from
  `pgvector/pgvector@sha256:33198da2828a14c30348d2ccb4750833d5ed9a44c88d840a0e523d7417120337`;
- pinned Defog Data revision
  `856295d8f0aa8a0b0fb71b9623e86f363469797a`;
- `car_dealership.sql` SHA-256
  `c9b89f31478729fc3e85d5765a78e967dabe61570efcfedd0c7dff89b0cbe0c3`;
  and
- execution role `fg_defog_runner` with `NOSUPERUSER`, `NOCREATEDB`,
  `NOCREATEROLE`, `NOINHERIT`, and `NOBYPASSRLS`, plus only database connect,
  schema usage, and table select grants.

The 12 external raw audit files have a sorted hash-list SHA-256 of
`5140343ebe25792176a418ac8448f6099c3f40ab727f192e3a45b001583e0b98`.
They contain questions, prompts, SQL, schema, database observations, and model
messages and remain outside Git.

## Verification

Run the deterministic comparison after producing the two P0 results:

```sh
python research/trace-intelligence/defog_terminal_protocol_analysis.py \
  --original research/trace-intelligence/experiments/results/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.json \
  --repaired research/trace-intelligence/experiments/results/defog-sql-factorial-fold0-terminal-only-p0-2026-07-30.json \
  --output research/trace-intelligence/experiments/results/defog-sql-terminal-protocol-analysis-2026-07-30.json
```

The analyzer verifies matching cohort, dataset, design, model, authority,
prompt/tool receipts, task set, and arm order before computing protocol and
paired-effect gates.

## Claim boundary

This is evidence that the repaired terminal protocol works on the frozen
four-task P0 with this pinned local runtime. It is not evidence of expert-skill
benefit, trace-mined-skill benefit, hidden-family transfer, enterprise-user
improvement, Aurora behavior, production RLS safety, or frontier-model
performance. Four tasks are inadequate for a quality estimate; the null is a
gate result, not a general conclusion that SQL procedures cannot help.
