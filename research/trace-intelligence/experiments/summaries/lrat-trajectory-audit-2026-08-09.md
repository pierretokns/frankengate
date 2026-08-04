# LRAT public trajectory audit (2026-08-09)

LRAT (Learning to Retrieve from Agent Trajectories) is a close method-level
match for trajectory-supervised retrieval ([repository](https://github.com/Yuqi-Zhou/LRAT),
[paper](https://arxiv.org/abs/2604.04949), [training dataset](https://huggingface.co/datasets/Yuqi-Zhou/LRAT-Train)). Its public repository is Apache-2.0
and reproducible under the documented `uv` workflow. The released
`LRAT-Train` dataset is public but large: the Hub manifest reports an 8.16 GB
dataset, including a 3.9 GB training-pairs JSONL and a trajectory archive. We
did not download that corpus. Instead, this audit uses the ten Apache-licensed
sample trajectories shipped in the repository.

## Sample mechanics

The ten samples contain:

- **10/10** records with `status=completed`;
- **280** ordered steps: 140 reasoning, 130 tool calls, and 10 final output
  records;
- **130/130** tool calls with non-empty outputs;
- **102** search calls and **28** browse calls (`get_document`/`visit`);
- an average of **62.4** retrieved document IDs per sample;
- query, answer, model/retriever metadata, tool arguments, and tool outputs;
- **no explicit reward, correctness, success, failure, gold-answer, or outcome
  field** in any sample record.

The repository README says the released training set contains completed
trajectories with correct final answers. That is useful positive retrieval
supervision, but it creates a hard boundary for Frankengate: the sample schema
does not retain observed failure, friction, abandonment, NIL, or wrong-system
examples, and `status=completed` is not an independently verified outcome
field.

## What Frankengate can take

1. **Trajectory-to-retrieval supervision:** use ordered search queries,
   browsed documents, subsequent reasoning, and final answer context to train
   or score retrievers rather than relying only on static query/document
   labels.
2. **Post-action exposure:** preserve which candidate was exposed before a
   later browse/reasoning step; this is the useful LRAT signal for candidate
   generation.
3. **Separate retriever and outcome lanes:** retain the trajectory evidence,
   but require an independent validator or human/SME label before calling an
   artifact successful.

## Hard edges

- LRAT's successful-web-search domain is not corporate SQL/tool artifact
  reuse. Its positives are documents and browse actions, not validated SQL,
  tool contracts, schema fingerprints, or changed-system replays.
- LLM-judged trajectory pairs can supply weak supervision, but they cannot
  establish enterprise alias truth, same-surface/different-system negatives,
  temporal authority, or user intent.
- The current sample has rich tool arguments/results but no stable principal,
  team, project, authorization epoch, or enterprise outcome fields.
- Reproducing the full retriever-training result requires the 3.9 GB training
  file, model checkpoints, and the paper's search benchmarks; this audit does
  not claim a training or end-to-end gain.

## Decision

Adapt LRAT as a **candidate-coverage experiment** after Frankengate's
structured scope/identifier stage. Do not adopt it as a memory, skill, eval,
or artifact-promotion system. The next fair test should use a fixed corporate
or SQL artifact pool with:

- positive exposure followed by validated consumption;
- unexposed-but-correct candidates;
- same-surface/wrong-system and temporal hard negatives;
- task-, project-, and principal-disjoint evaluation; and
- independent execution and human utility labels.

Receipt: [`lrat-trajectory-audit-2026-08-09.json`](../results/lrat-trajectory-audit-2026-08-09.json).
Runner: [`lrat_trajectory_audit.py`](../../lrat_trajectory_audit.py). Raw sample
files remain in `/private/tmp/lrat-repro`; only hashes and aggregate counts are
committed.
