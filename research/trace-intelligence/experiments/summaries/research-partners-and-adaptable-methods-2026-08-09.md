# Corporate trace learning: adjacent methods and partner targets (2026-08-09)

This memo is a current literature/partner screen, not a claim that any cited
method has been validated on Frankengate data. The evidence matrix remains the
authority for our empirical results.

## Methods that are genuinely adaptable

### Learning to Retrieve from Agent Trajectories (LRAT)

LRAT is the closest recent match to the proposed trace-to-retriever flywheel.
It derives positives from documents an agent browses, negatives from exposed
but unbrowsed candidates, and relevance intensity from post-browse reasoning.
The authors report gains in evidence recall, task success, and interaction
steps across in-domain and out-of-domain research benchmarks. See the
[paper](https://arxiv.org/abs/2604.04949), especially its trajectory-signal and
negative-sampling sections.

**Frankengate adaptation:** treat a retrieved tool/schema/artifact as exposed
only when it was actually offered to the agent; treat execution, inspection,
and post-tool state change as progressively stronger positive signals. A
candidate absent from a trace is not a negative unless exposure is recorded.
For artifacts, explicit replay success should outrank “the model mentioned it”
and post-tool repair should be a negative or uncertainty signal. This directly
fixes a weakness in naive mining from raw logs.

**Hard edge:** LRAT's browse-success assumption does not automatically transfer
to governed tools. A tool can be correct but intentionally not executed because
of authority, cost, or user choice. We need exposure and refusal reasons in the
trace schema.

### Enterprise hard-negative mining

The paper [Hard Negative Mining for Domain-Specific Retrieval in Enterprise
Systems](https://arxiv.org/abs/2505.18366) is directly adjacent to corporate
concept discovery. It selects semantically close but contextually irrelevant
documents and reports improvements on a proprietary cloud-services corpus plus
public domain datasets.

**Frankengate adaptation:** generate negatives from the same surface in a
different system, same system but different table/tool, temporal replacements,
and near-identical identifiers with different authority. Preserve the negative
type instead of collapsing all negatives into one class. Our existing public
reranker result already shows that identifier-aware features beat dense
retrieval, while extra hard-negative weighting did not improve the small proxy;
the next test must use reviewed labels and larger strata.

**Hard edge:** the paper's proprietary corpus and headline gains are not
reproducible from the abstract. Treat its method as a sampling hypothesis, not
as an expected uplift.

### Cursor-style historical retrieval supervision

[Cursor's semantic-search report](https://cursor.com/blog/semsearch) is the
closest production precedent found so far for learning a retriever from agent
trajectories. Cursor describes using later search/open behavior in a session,
having an LLM rank what would have been useful earlier, and distilling those
rankings into a custom embedding model. Its companion
[CursorBench report](https://cursor.com/blog/cursorbench) pairs real internal
agent requests with committed changes through Cursor Blame and checks offline
scores against controlled online experiments.

This is directly adaptable as a **labeling and evaluation protocol**, not as a
drop-in enterprise embedding. Cursor's objects are repository code chunks; the
posts do not establish governed tool exposure, authority, changed-system
replay, NIL/refusal labels, or skill transfer. The Frankengate adaptation must
log the exposed candidate set, distinguish unexposed from rejected candidates,
and require authorized replay before treating a candidate as useful. The full
method-transfer contract is in
[`cursor-historical-retrieval-supervision-2026-08-09.md`](cursor-historical-retrieval-supervision-2026-08-09.md).

This strengthens the proposed study: compare a Cursor-style
trajectory-distilled ranker with exact/identifier, lexical, frozen-dense, and
frontier-review arms under principal/project/system/time holdouts. It does not
justify training on raw traces or promoting a custom embedding without
changed-system artifact outcomes.

### FastContext: promising but withdrawn

[FastContext](https://arxiv.org/abs/2606.14066) describes a separate repository
explorer trained from reference-model trajectories and task-grounded rewards.
That separation is a useful design hypothesis for our artifact explorer, but
the arXiv record marks the paper withdrawn over product-IP issues, provides no
license, and its linked `microsoft/fastcontext` repository is unavailable. Its
reported benchmark gains therefore cannot be treated as evidence or a fork
target. Preserve only the experiment idea—cheap evidence/path discovery before
frontier reasoning—and validate it with our own exposure-complete traces and
changed-system replay. See
[`fastcontext-withdrawn-method-audit-2026-08-09.md`](fastcontext-withdrawn-method-audit-2026-08-09.md).

Our independent [TRAJECT-Bench separate-explorer probe](traject-bench-separate-explorer-probe-2026-08-09.md)
tests this concept without FastContext. Across two eight-case Luna runs,
full-pool exploration improved public target coverage from `.500` for lexical
top-16 to `.750` and `.708333`, while emitting only about four candidates. The
prompt was large (about 45.9k characters on average), cost/latency were not
recorded, and no replay or authority labels existed. This supports a separate
explorer as a candidate-generation arm, not as proof of skill or artifact
promotion.

The follow-on [44-case task-disjoint WMH-BIRD cohort](wmh-bird-sql-explorer-cohort-2026-08-09.md)
is the stronger current retrieval receipt: explorer strict MRR/Recall@1
`.965909/.931818` versus lexical `.796266/.704545`, with replay-compatible
selection `.924242` versus `.391153`. The family breakdown includes two weaker
families, so the result supports a stratified explorer arm rather than a pooled
automatic policy. Enterprise authority, changed-system, and human-utility
labels remain the required partner contribution.

The follow-up [WMH-BIRD SQL explorer bridge](wmh-bird-sql-separate-explorer-probe-2026-08-09.md)
is the first replay-backed adaptation. On two eight-case Luna runs, it found
all recorded SQL tables at rank one, selected `2.5` tables on average instead
of `6.375`, and had `.979167` replay-compatible selection versus `.418006` for
lexical top-8. This is still a small hinted public proxy; it supports the
explorer/noise-reduction hypothesis, not semantic alias quality or enterprise
artifact reuse. The next partner study must use task-disjoint, authority-aware
and changed-system traces.

The [changed-system authority explorer probe](changed-system-authority-explorer-2026-08-09.md)
now supplies that missing safety control in a synthetic fixture. Names-only
input produced complete abstention, while typed semantic inputs, system ID,
authority epoch, schema version, and active status found `9/9` non-NIL targets
with zero unsafe selections and correctly abstained on the NIL case. This
supports typed artifact projections and deterministic admission gates as a
research requirement. It does not show that frontier selection can enforce
governance, nor does it substitute for an authorized changed-system cohort.
The [replay bridge](changed-system-authority-replay-bridge-2026-08-09.md)
connects that metadata result to independent execution: typed-gated selections
were `10/10` safe/correct, while a name-first control produced seven unsafe
accepts, including cases whose output happened to match. This should be a
required partner-study endpoint: report semantic correctness and authority
validity separately, because a successful query can still be unauthorized or
semantically wrong.

The matched [dense/frontier WMH-BIRD cohort](wmh-bird-sql-dense-frontier-cohort-2026-08-09.md)
adds a useful cascade result for data-systems partners: local Nomic reached
`.940152` MRR and `.909091` Recall@1, while Luna reached `.954545` and the same
Recall@1. Frontier's replay-compatible selected rate was `.928030` versus
`.408198` for dense, with a much smaller shortlist. This separates candidate
recall from noise reduction, but still needs reviewed enterprise aliases,
authority labels, and changed-system outcomes before it can support a custom
embedding or production collaboration claim.

### Trajectory-aware tool evaluation

[TRAJECT-Bench](https://arxiv.org/abs/2510.04550) evaluates tool selection,
argument correctness, ordering, and dependency satisfaction—not merely final
answers. Its production-style APIs are synthetic, so it is an evaluation
decomposition rather than an enterprise-data match.

**Frankengate adaptation:** add these dimensions to every artifact replay:
selection correctness, parameter binding, authority compatibility, order/dependency
correctness, independent execution outcome, and post-execution recovery. This
lets us distinguish “wrong tool” from “right tool, wrong argument” and from
“correct artifact rejected by governance.”

### Multi-step tool retrieval (ToolQP)

MIT CSAIL work on [Tool Query Planning](https://people.csail.mit.edu/weifang/)
frames tool retrieval as iterative subtask planning rather than one-shot query
embedding. The thesis describes dynamic retrieval, inter-tool dependencies,
and using the retrieval trajectory as downstream context.

**Frankengate adaptation:** retrieve a typed subplan in stages: identify the
system/scope, retrieve a compatible tool or SQL artifact, bind parameters,
then validate the expected observation. This is a better fit for our failed
whole-query dense retrieval result than simply training a larger embedding
model.

**Hard edge:** planning can amplify an early wrong system choice. Every stage
needs a scope/authority filter and an abstention path; the final replay oracle
remains mandatory.

## Open-source implementations worth testing

- [LRAT](https://github.com/Yuqi-Zhou/LRAT) provides the authors' trajectory-
  supervision implementation. It is a direct candidate for a forked
  experiment, but its search/browse data model must be adapted to governed
  tool exposure and execution outcomes.
- [TRAJECT-Bench](https://github.com/PengfeiHePower/TRAJECT-Bench) publishes
  executable tool definitions, parallel and sequential trajectory data, and
  evaluation scripts. Its README describes 10 domains, 50 task types, and
  trajectory-aware metrics, making it the best public harness for validating
  selection/argument/order metrics before using private enterprise traces.
- [TOOLQP](https://arxiv.org/abs/2601.07782) is the current research target for
  staged retrieval. The paper reports a lightweight 1.7B planner and explicit
  query/retrieval feedback loops; its claims still need an independent
  Frankengate reproduction.

The immediate test sequence is therefore: run the unmodified public
TRAJECT-Bench evaluator; add Frankengate's authority/scope and replay metrics;
then compare static dense retrieval, LRAT-style exposed-candidate training,
and ToolQP-style staged retrieval on the same tool pools. No method should be
ported into production based on the paper numbers alone.

## Best research partners

1. **MIT DSAIL / Data Systems Group.** Its stated agenda explicitly combines
   learned components with indexes, query optimization, schema design, data
   integration, and enterprise applications, and emphasizes industry
   collaboration and technology transfer. This is the strongest fit for the
   validated-SQL-artifact and data-system portion of the project. See the
   [DSAIL research page](https://dsg.csail.mit.edu/dsail/).

2. **MIT Everest Lab.** Everest focuses on engineering principles for
   AI-driven data systems, including large-scale retrieval, data analytics,
   code generation, and agent operations; its page cites deployed technical
   assistance and data-processing systems. It is a strong fit for a retrieval
   and operations benchmark with real systems constraints. See
   [Everest](https://everest.csail.mit.edu/).

3. **MIT CLEAR Lab.** CLEAR studies agents learning with and around people,
   including human expectations and user studies. It is the best fit for
   consented feedback loops, skill-gap recommendations, and measuring whether
   recommendations help rather than merely correlate with traces. See
   [CLEAR](https://clear.csail.mit.edu/).

4. **Harvard MTERMS Lab** is an adjacent, domain-specific terminology and
   information-extraction partner. Its work covers extraction, normalization,
   retrieval, relation identification, and deployment in clinical systems. It
   is useful for ontology/alias methodology, but the clinical domain and
   terminology standards make it a weaker fit than MIT for agent artifacts.
   See [MTERMS](https://mterms.bwh.harvard.edu/mterms/).

## What we should propose as a publishable study

The strongest paper is not “memory improves agents.” It is:

> **From agent traces to governed enterprise artifacts: exposure-aware
> supervision, identifier-aware hard negatives, and replay-validated reuse.**

Preregister one authorized cohort and compare, under principal/project/system/
time-held-out splits:

1. exact + scope filters;
2. lexical and identifier-aware reranking;
3. dense retrieval;
4. LRAT-style exposure/post-tool supervision;
5. ToolQP-style staged retrieval;
6. frontier adjudication without replay;
7. frontier adjudication followed by independent replay;
8. no-artifact regeneration and reviewed-artifact controls.

Primary measures should be semantic-label agreement, Recall@K/MRR,
wrong-system-before-target, NIL abstention, changed-system execution success,
unsafe/stale acceptance rate, latency, and cost. Secondary measures should be
skill transfer, repeat-task time, and whether a recommendation changes the
next task outcome. Report results separately for exact identifiers, aliases,
temporal replacements, and unresolved/NIL cases.

The minimum cohort gate already recorded in the readiness checker remains:
100 labeled targets, 50 hard negatives, 25 NIL/unclear examples, at least two
principals/projects/systems, two changed environments, two blinded labels, and
independent terminal outcomes. Public BIRD/Defog/Trace Commons data can test
mechanics, but cannot substitute for this cohort.

## Bottom line

The new literature strengthens—not overturns—the current architecture:

```text
exposure + scope/authority
  -> exact/identifier/lexical retrieval
  -> embedding candidate recall
  -> trajectory-aware or frontier review
  -> independent replay and changed-system validation
  -> versioned artifact/skill with expiry and rollback
```

The most credible partnership is MIT DSAIL/Everest for the data-system and
retrieval study, with CLEAR for human-feedback and skill-impact evaluation.
Harvard MTERMS is a useful terminology-method collaborator, but not the lead
for the full agent-artifact program.
