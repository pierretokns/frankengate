# Hugging Face NL2SQL trajectories and replay audit

**Status:** source-pinned and empirically audited
**Reviewed:** 2026-07-30
**Decision:** mine real procedures from WMH BIRD-SQL and CRMArena, but run the
first PostgreSQL causal skill experiment on a separately hardened Defog cohort

## Decision

Frankengate now has real public NL2SQL action/observation traces, not only
question-to-SQL examples. The corpora still occupy different evidence classes:

| Source | What is actually present | Frankengate role | Not valid for |
| --- | --- | --- | --- |
| [WMH BIRD-SQL](https://huggingface.co/datasets/experiential-labs/wmh-bird-sql-traces/tree/26e54b84ec94bcb0bfb153f664c9d150b64dd0e3) | 1,993 real runs, 4,168 tool transitions, 222 traced train tasks, 20 untraced tests, 11 DDLs, 242 gold SQL sidecars | Primary real procedure/failure mining; reconstructable SQLite replay | Latency, full reasoning, default schema-held-out claims, Aurora transfer |
| [WMH CRMArena](https://huggingface.co/datasets/experiential-labs/wmh-crmarena-traces/tree/9a70e127f6dce74110a17092f62696f25a3a526b) | 80 real runs, 553 tool transitions, 45 traced train tasks, 18 untraced tests over nine CRM task types | Enterprise-analytics qualitative/control arm | Commercial training, cross-schema transfer, mutation workflows |
| [Microsoft MAGIC](https://huggingface.co/datasets/microsoft/MAGIC/tree/9b8da842fcb82ac750ca1a025af7645f5ba95a30) | 48,124 feedback, correction, and manager-prompt rows | Mine correction hypotheses and failure taxonomies | Raw tool behavior, independent replay, causal benefit |
| [PT-BR agentic Text-to-SQL](https://huggingface.co/datasets/YnJhY2lzMjAyNnRleHQyc3Fs/pt-br-agentic-text-to-sql-distilled-trajectories/tree/790158a2bdbd5ee5007dbf0b4e88bb665fd67675) | 7,442 distilled tool-protocol conversations with schema, execution, answer, clarification, and abstention actions | Multilingual/noisy-metadata procedure-mining arm | Natural behavior or independent correctness |
| [Analyst Buddy](https://huggingface.co/datasets/hjerpe/analyst-buddy-traces/tree/d6dee846a92e16381ebd9dafa78bdfcb7dd4bc1d) | Six paired base/fine-tuned trajectories on one synthetic retail database | Qualitative error-recovery example | Statistical, enterprise, or cross-schema claims |
| [Defog SQL-Eval](https://github.com/defog-ai/sql-eval/tree/b83332416ea2d424b0cd12994a0a9ba100f4b4af) + [Defog Data](https://github.com/defog-ai/defog-data/tree/856295d8f0aa8a0b0fb71b9623e86f363469797a) | Executable PostgreSQL fixtures and gold SQL, but no intermediate agent trajectories | First hardened schema-disjoint causal replay cohort | Natural trace mining or stock-verifier security |

The correct composition is:

```text
real evidence-family traces
  -> cheap signal detectors and failure taxonomy
  -> evidence-linked candidate SQL procedure
  -> visible selection on a different schema family
  -> signed immutable skill release
  -> hidden replay on a third schema family
  -> semantic outcome + independent security verdict
```

The proposer must never read tasks, traces, schema metadata, gold SQL, results,
or verifier messages from the selection or test families.

## World Model Optimizer v0.2.2 (2026-07-28)

**Repo:** [experientiallabs/world-model-optimizer @ d7bb0077](https://github.com/experientiallabs/world-model-optimizer/tree/d7bb0077fb87da0b078065743f7bab310883bbb2)

The repository is still reachable through the former
`world-model-harness` name, but the stable source and pull requests use
`world-model-optimizer`.

### Commands

| Task | Command | Notes |
| --- | --- | --- |
| Download published trace bundle | `uv run wmo download bird-sql` | Downloads traces/tasks/gold/DDL, not BIRD database files |
| Materialize base BIRD split | `uv run python packages/environment-capture/bird-sql/fetch_data.py --minidev-root minidev/MINIDEV` | Four databases, 52 train + 20 test |
| Expand BIRD train families | add `--expand` | Materializes all 11 databases and appends train only |
| Capture BIRD runs | `uv run python packages/environment-capture/bird-sql/capture.py --split train --models … --append` | Source refuses test capture |
| Download CRMArena org | `uv run python packages/environment-capture/crmarena/fetch_data.py` | Direct official SQLite dump |
| Rebuild CRMArena split | run `fetch_data.py --all`, then `build_split.py` | Seeded nine-type split |
| Capture CRMArena runs | `uv run python packages/environment-capture/crmarena/capture.py --models … --runs 1 --append` | Train only |
| Evaluate learned world model | `uv run wmo eval run bird-sql/default --examples-root packages/environment-capture` | World-model fidelity, not SQL-task skill benefit |

### BIRD configuration

| Option | Default | Meaning |
| --- | --- | --- |
| `--databases` | four base DBs; all 11 under `--expand` | Materialized schema families |
| `--per-db` | 18; 22 under `--expand` | Candidate cap per database |
| `--test-frac` | `0.3` | Base per-database held-out fraction |
| `--seed` | `7` | Source selection and split seed |
| capture `--split` | `train` | Source explicitly refuses `test` |
| capture `--max-steps` | `12` | Maximum real environment transitions |
| capture `--runs` | `1` | Repeated passes, with run-suffixed IDs |

These behaviors are implemented in the pinned
[materializer](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/bird-sql/fetch_data.py#L52-L66),
[split logic](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/bird-sql/fetch_data.py#L91-L127),
and [capture guard](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/bird-sql/capture.py#L94-L119).

### Environment variables

| Variable/credential | Purpose | Frankengate handling |
| --- | --- | --- |
| AWS Bedrock credential chain and region | Generate fresh Bedrock capture runs | Never present in the tool subprocess |
| `HF_TOKEN` or `hf auth login` | Push private/public trace bundles | Not required to read public pinned files |
| None for replayed SQLite tools | Local BIRD/CRM database exploration | Run inside the governed sandbox with network denied |

The source's `LocalBashEnv` scrubs credential-shaped environment variables, but
its hygiene scan is defense in depth rather than the Frankengate authorization
boundary.

### Replay and grading

BIRD stages a fresh database copy and DDL, then executes the submitted and gold
queries on a pristine read-only database. Result rows are compared as a
multiset unless question keywords imply order. The implementation is
[deterministic and LLM-free](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/environment_capture/benchmarks/bird_sql.py#L1-L14);
the [grade path](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/environment_capture/benchmarks/bird_sql.py#L140-L183)
runs both SQL programs against the source database.

CRMArena stages a fresh read-only copy of the official org plus a bounded
50-row/2,000-character query tool. Eight analytical task types use exact or
whole-token matching; knowledge QA uses token F1. See the
[query runner](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/environment_capture/benchmarks/crmarena.py#L43-L86)
and [grader](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/environment_capture/benchmarks/crmarena.py#L127-L176).

### Gotchas

- **The Hugging Face BIRD snapshot is not replay-complete.** It contains tasks,
  gold SQL, DDL, and traces, but the 11 database files are gitignored. The
  source documents the separate BIRD mini-dev archive and materialization path
  ([source](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/bird-sql/README.md#L67-L80)).
- **“OTel” does not mean full telemetry here.** Empirical inspection found
  9,442/9,442 empty parent references and synthetic ordinal timestamps. The
  one-span-per-line records are an OTel-shaped projection, not an OTLP
  resource/scope envelope. Use a receipted source adapter and do not infer
  latency or distributed parentage.
- **The BIRD default split is not schema-held-out.** Source selection draws
  train and test from each base database
  ([source](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/bird-sql/fetch_data.py#L108-L127)).
  Frankengate must partition database families before trace mining.
- **CRMArena is one org and SQLite, not native SOQL.** The source explicitly
  documents the query-surface substitution
  ([source](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/crmarena/README.md#L55-L68)).
- **CRMArena is non-commercial.** CC-BY-NC-4.0 permits this research arm but
  not automatic production-training adoption
  ([source](https://github.com/experientiallabs/world-model-optimizer/blob/d7bb0077fb87da0b078065743f7bab310883bbb2/packages/environment-capture/crmarena/README.md#L94-L102)).
- **The environment runner has open lifecycle defects.** Upstream reports that
  `LocalBashEnv` timeouts can leave child processes
  ([issue #168](https://github.com/experientiallabs/world-model-optimizer/issues/168))
  and `new_session` can corrupt seed-state traces through a missing deep copy
  ([issue #169](https://github.com/experientiallabs/world-model-optimizer/issues/169)).
  Frankengate should reuse neither process lifecycle nor in-memory session
  mutation without its own containment tests.
- **Stable v0.2.2 lacks the later one-command reproduction work.** The
  `wmo reproduce` feature landed after the stable tag in
  [PR #379](https://github.com/experientiallabs/world-model-optimizer/pull/379).
  Our manifest therefore pins explicit download/materialization commands
  instead of documenting unreleased main-branch behavior.

## Empirical trace-format result

The aggregate audit is committed as
[`hf-nl2sql-trace-audit-2026-07-30.json`](../../../research/trace-intelligence/experiments/results/hf-nl2sql-trace-audit-2026-07-30.json).

| Property | BIRD-SQL | CRMArena |
| --- | ---: | ---: |
| JSONL span objects | 8,336 | 1,106 |
| Distinct trace IDs | 1,993 | 80 |
| Tool actions/results | 4,168 / 4,168 | 553 / 553 |
| Malformed rows | 0 | 0 |
| Duplicate span IDs | 0 | 0 |
| Non-empty parent IDs | 0 | 0 |
| Maximum end timestamp | 103 | 153 |
| Test tasks represented in traces | 0 | 0 |
| Full assistant narrative field | absent | absent |

This validates exact action/result supply and held-out task IDs. It also proves
that a generic OTel ingestion path would silently overclaim causal and latency
fidelity unless it records a loss receipt.

## Frankengate implementation requirements

1. Import the flattened spans through a WMH-specific adapter into the governed
   canonical event DAG; never pass them through as lossless OTLP.
2. Store source file/revision/hash, base task, database family, model, run,
   reward, action/result position, and every projection loss.
3. Mine cheap rephrase, retry, SQL-error, empty-result, schema-revisit,
   cardinality, and stagnation signals before using embeddings or judges.
4. Require evidence links from every proposed SQL lesson to exact trace
   transitions; proposal text remains untrusted.
5. Freeze evidence, selection, and hidden-test database families before any
   candidate generation.
6. Rerun candidates through a read-only governed SQL role with statement,
   lock, row, byte, and wall-clock bounds.
7. Record semantic result equivalence and security/policy validity as separate
   verdicts. A correct result that reads unauthorized columns fails release.
8. Publish only a signed immutable skill release after the candidate beats
   baseline and placebo with per-family floors and no security regression.
9. Record release exposure in subsequent traces so later improvement is not
   misattributed to an unobserved memory or prompt.
10. Keep CRMArena results and derivatives confined to a non-commercial
    research purpose.

## Governed replay status

The separate Defog layer now implements requirements 5–7 at the verifier and
policy level. Across the frozen 96-task cohort, 95 tasks execute as PostgreSQL
and all 95 match the hardened semantic comparator. The default authority
correctly denies two sensitive projections; both match only with explicit
field entitlements. One wildcard-bearing source query is invalid PostgreSQL
even after an auditable dialect repair and remains quarantined. Missing epoch,
multiple statement, mutation, system function, unknown table, wildcard, and
database read-only controls pass on all four database families.

The separate cache-disabled mechanics factorial has now run four F0 selection
tasks under no-skill, formatting-placebo, and expert-seed arms. Every arm
passed the same 2/4 tasks with zero unauthorized observations, but
terminal-protocol failure was 25%, 50%, and 25%. The preregistered protocol
gate therefore failed and hidden outcomes remain sealed. No model-quality or
trace-learning claim follows. Requirements 8–9 remain unmet until a
protocol-remediated paired screen, evidence-only mined artifact, hidden-family
test, and prospective release-exposure study run.

## Sources

- [WMH BIRD-SQL dataset](https://huggingface.co/datasets/experiential-labs/wmh-bird-sql-traces/tree/26e54b84ec94bcb0bfb153f664c9d150b64dd0e3)
- [WMH CRMArena dataset](https://huggingface.co/datasets/experiential-labs/wmh-crmarena-traces/tree/9a70e127f6dce74110a17092f62696f25a3a526b)
- [World Model Optimizer v0.2.2 source](https://github.com/experientiallabs/world-model-optimizer/tree/d7bb0077fb87da0b078065743f7bab310883bbb2)
- [BIRD benchmark](https://bird-bench.github.io/)
- [CRMArena source](https://github.com/SalesforceAIResearch/CRMArena)
- [MAGIC dataset](https://huggingface.co/datasets/microsoft/MAGIC/tree/9b8da842fcb82ac750ca1a025af7645f5ba95a30)
- [PT-BR distilled trajectories](https://huggingface.co/datasets/YnJhY2lzMjAyNnRleHQyc3Fs/pt-br-agentic-text-to-sql-distilled-trajectories/tree/790158a2bdbd5ee5007dbf0b4e88bb665fd67675)
- [Analyst Buddy traces](https://huggingface.co/datasets/hjerpe/analyst-buddy-traces/tree/d6dee846a92e16381ebd9dafa78bdfcb7dd4bc1d)
