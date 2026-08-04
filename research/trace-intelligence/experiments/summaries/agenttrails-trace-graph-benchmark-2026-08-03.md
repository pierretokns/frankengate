# AgentTrails-style provenance graph probe (2026-08-03)

## Question

Does representing a trajectory as a provenance graph—tool/action nodes linked
to output-schema/status artifact nodes and then to subsequent actions—recover
better reusable workflow structure than flattened tool-family or call-shape
similarity?

This adapts [AgentTrails](https://arxiv.org/abs/2607.18816), which argues that
chronological logs hide dataflow and that provenance graphs can reveal
recurring tool/artifact dependencies. The implementation is intentionally a
structural probe: it uses no raw prompt, output, path, session, or project
content in the receipt.

## Protocol

- Source: 48 and 96-row bounded samples from the pinned public
  `zhiyaowang/dataclaw-zhiyaowang` revision used by the earlier trace audit.
- Eligible episodes contain at least four tool calls. The chronological 70/30
  split is by `start_time`; the query is every event except the final one and
  the target is the final event.
- Action IDs hash tool name plus input-key shape. Artifact IDs hash bounded
  output schema plus status. Graph edges are
  `action -> artifact -> next action`.
- Arms: tool-family Jaccard, action-shape Jaccard, graph Jaccard, and an
  equal-weight graph+shape score.
- Metrics: next tool-family accuracy, exact next action-shape accuracy, and
  next output-schema accuracy. These are structural proxy labels, not task
  correctness or user value.

## Results

| Sample | Arm | Test cases | Next family | Next action shape | Next artifact schema |
|---:|---|---:|---:|---:|---:|
| 48 | tool-family | 12 | `.250` | `.000` | `.167` |
| 48 | action-shape | 12 | `.500` | `.333` | `.667` |
| 48 | graph | 12 | `.583` | `.417` | `.667` |
| 48 | graph+shape | 12 | `.500` | `.333` | `.667` |
| 96 | tool-family | 24 | `.292` | `.083` | `.125` |
| 96 | action-shape | 24 | `.625` | `.417` | `.792` |
| 96 | graph | 24 | `.542` | `.375` | `.708` |
| 96 | graph+shape | 24 | `.583` | `.375` | `.750` |

## Findings

1. Provenance structure consistently beats the weak tool-family-only control
   for predicting the next tool family (`.583` vs `.250` on the 48-row sample;
   `.542` vs `.292` on the 96-row sample).
2. Action-shape similarity is stronger for exact next-action and output-schema
   prediction on the larger sample (`.417/.792`), so graph structure is not a
   replacement for identifier/input-shape features.
3. The equal-weight graph+shape arm improves over graph alone on artifact
   schema prediction in the larger sample (`.750` vs `.708`) but does not beat
   shape-only. The correct architecture is therefore a graph feature or
   reranking signal alongside exact call-shape and scope features, not a graph
   only index.
4. The effect is stable in direction but not large enough to claim semantic
   workflow reuse. The public corpus has no independent task outcome, user
   identity, authorization scope, or changed-system replay label.

## Frankengate implication

AgentTrails contributes a useful representation layer for the trace commons:

```text
OTel/MCP trace
  -> action identity + typed output/artifact schema
  -> action/artifact/dataflow graph
  -> graph + exact identifier/scope retrieval
  -> independently validated artifact or skill candidate
  -> changed-system replay
```

It should be used to group and explain recurring workflows, detect hidden
dependencies, and generate review candidates. It must not promote an artifact
from structural recurrence alone. The missing experiment is a consented,
outcome-labelled cohort where graph-retrieved subplans are replayed against
changed schemas, tools, and temporal versions.

## Receipts and implementation

- [`agenttrails-trace-graph-benchmark-2026-08-03.json`](../results/agenttrails-trace-graph-benchmark-2026-08-03.json)
- [`agenttrails-trace-graph-benchmark-2026-08-03-repeat96.json`](../results/agenttrails-trace-graph-benchmark-2026-08-03-repeat96.json)
- [`agenttrails_trace_graph_benchmark.py`](../../agenttrails_trace_graph_benchmark.py)
- [`tests/test_agenttrails_trace_graph_benchmark.py`](../../tests/test_agenttrails_trace_graph_benchmark.py)

The three structural contract tests pass. This probe is adjacent evidence for
AgentTrails, not a reproduction of its full joined-quotient visualization or a
claim about enterprise task completion.
