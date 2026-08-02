# Cursor-style historical retrieval supervision (2026-08-09)

This note records a primary-source review of Cursor's published semantic-search
and benchmark method. It is a method-transfer decision, not a claim that
Frankengate has reproduced Cursor's private data or model.

## Source evidence

- [Improving agent with semantic search](https://cursor.com/blog/semsearch),
  November 6, 2025.
- [How we compare model quality in Cursor](https://cursor.com/blog/cursorbench),
  March 11, 2026 (the post identifies CursorBench 3.1 as the current production
  version in its May 2026 update).

Cursor reports a hybrid grep-plus-semantic-search agent. Its custom embedding
training uses agent sessions as supervision: after an agent searches and opens
files, an LLM ranks what would have been useful earlier, and the embedding
model is trained to reproduce those rankings. The published semantic-search
ablation reports an average 12.5% accuracy increase, 0.3% higher code retention
overall (2.6% on repositories with at least 1,000 files), and 2.2% more
dissatisfied follow-up requests when semantic search is removed. These are
Cursor's internal results, not an independent Frankengate result.

CursorBench adds a second important pattern: tasks are mined from real internal
Cursor sessions and paired to committed changes using Cursor Blame. It scores
correctness, code quality, efficiency, and interaction behavior, then checks
offline rankings against controlled online experiments. The task suite is
refreshed as workflows change and deliberately contains ambiguous, multi-file,
long-running work rather than only public bug-fix cases.

## Exact match versus adjacent work

| Question | Cursor evidence | Frankengate status |
|---|---|---|
| Can historical trajectories supervise retrieval? | Yes: later search/open behavior is converted into LLM-ranked retrieval targets and distilled into an embedding model. | **Directly adaptable; not yet reproduced as a neural model.** |
| Does the retrieval change agent outcomes? | Cursor reports offline gains and an online semantic-search ablation. | **Our evidence is complementary:** action embeddings improved candidate Recall@20, but downstream artifact utility remains unproven. |
| Can this discover governed SQL/tool artifacts? | Not evaluated; Cursor's objects are code chunks in a repository. | **Open:** requires typed artifacts, principal/project scope, authority, expiry, and replay. |
| Does it learn user skills or intent? | Not claimed. | **Open:** retrieval relevance is not skill transfer, competence, or business-intent truth. |
| Is there a public implementation or dataset? | The posts describe private infrastructure and internal benchmarks. | **No fork claim:** reproduce the protocol against licensed traces; do not imply access to Cursor's model or data. |

The key lesson is not “train an embedding on raw logs.” It is to construct
trajectory-derived relevance labels from what the agent was actually exposed to,
what it inspected, and what later evidence shows was useful. This is stronger
than treating every nearby or later message as a positive, and it explains why
our earlier unlabelled embedding adapters were weak controls rather than a
disproof of domain adaptation.

## Frankengate adaptation

For each trace episode, create a candidate packet containing:

1. the query/intent turn and its evidence span;
2. the candidate artifact/tool/schema objects exposed at each step;
3. later inspection, execution, repair, commit, or independent replay outcome;
4. principal, project, system, authority epoch, and artifact version; and
5. explicit refusal, denial, cost, or “not exposed” reasons.

Use the following arms on the same chronological, project-held-out cohort:

1. exact identifier and scope filters;
2. lexical/identifier-aware ranking;
3. frozen general embeddings;
4. a Cursor-style trajectory-distilled ranker, where a frontier model labels
   *which exposed candidates would have been useful at the earlier step*;
5. the same ranker with exposure-aware hard negatives; and
6. frontier review followed by independent artifact replay.

The frontier label is a proposal, not ground truth. A candidate earns a
positive utility label only when it is authorized, replayable, and produces the
expected independent outcome. A candidate that was not exposed is missing data,
not a negative. Candidates exposed but skipped need a typed reason before they
can be used as negatives. Same-surface/different-system, temporal replacement,
wrong-parameter, and stale-authority cases must be separate negative families.

Primary measures are Recall@K/MRR, wrong-system-before-target, NIL/refusal
precision, replay success on the current and changed system, stale/unsafe
acceptance, latency, and frontier cost. Secondary measures are repair-loop
length, repeat-task time, and whether the next task improves. This connects
Cursor's retrieval result to issues [#119](https://github.com/pierretokns/frankengate/issues/119),
[#121](https://github.com/pierretokns/frankengate/issues/121),
[#122](https://github.com/pierretokns/frankengate/issues/122),
[#123](https://github.com/pierretokns/frankengate/issues/123), and the
changed-system causal cohort in [#118](https://github.com/pierretokns/frankengate/issues/118).

## Required controls and hard edges

- **Temporal leakage:** train only on sessions before the evaluation window;
  expire artifacts after schema, authority, or environment changes.
- **Exposure bias:** the agent's existing search policy determines what can be
  become a positive; log the candidate set before selection.
- **LLM-label bias:** compare frontier labels with blinded SME labels and a
  deterministic replay oracle; report disagreement and `unclear` rather than
  forcing a ranking.
- **Pool coverage:** a retrieval null can mean the artifact library has no
  compatible object. Include a regeneration control and known-shared-intent
  tasks before judging the ranker.
- **Outcome mismatch:** code retention or follow-up reduction is not equivalent
  to governed SQL correctness, tool safety, or employee skill improvement.
- **Tenant leakage:** split by principal/project/system and preserve scope and
  authority filters before any embedding or model call.

## Decision

Adopt Cursor's *labeling protocol and online/offline evaluation loop* as the
next independent method arm. Do not import a custom embedding model or claim
that semantic retrieval solves enterprise artifact learning. The immediate
experiment is a trajectory-distilled ranker on a licensed, exposure-complete
artifact cohort with replay and changed-system controls. Promotion requires an
absolute downstream replay lift over the structured baseline without increased
wrong-system, NIL, stale-authority, or unsafe acceptance.

This is the closest public production precedent found so far for our
trace-to-retriever question, but it remains adjacent to the harder
trace-to-governed-skill question.
