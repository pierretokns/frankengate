# Researcher traces and versioned harness memory study

**Status:** new empirical stratum; source inventory in progress
**Decision boundary:** researcher work and durable memory are first-class
evidence, but neither a final paper nor the current `MEMORY.md` may leak
backward into an earlier decision point.

## Why this is a separate stratum

Coding-repair traces overrepresent short feedback loops with executable tests.
Research work contains different hard cases:

- discovering and rejecting sources;
- reformulating questions after conflicting evidence;
- choosing measurements and comparison groups;
- running notebooks, simulations, searches, and data transforms;
- distinguishing observed evidence from inference and citation;
- tracking unresolved uncertainty and negative results;
- synthesizing across long time spans; and
- revising claims after peer or collaborator feedback.

These traces are closer to Frankengate's open-ended enterprise questions than
SWE repair alone. They can test whether the system finds duplicated research,
recurring evidence gaps, useful prior methods, stale assumptions, and candidate
collaborators without pretending that topic similarity proves expertise.

Durable files—`MEMORY.md`, `CLAUDE.md`, `AGENTS.md`, rules, skills, plans,
todos, notebook state, and harness-specific memory stores—are not ordinary
messages. They are versioned context artifacts that may influence many later
sessions.

## Source-pinned corpus strata

| Source | Observed evidence | Classification and experiment use |
| --- | --- | --- |
| [clem/ml-intern-sessions @ `f87189d`](https://huggingface.co/datasets/clem/ml-intern-sessions/tree/f87189d9674394472755896350df0661154bbe0a) | 92 dated JSONL files, 15 unique session IDs, 12 dates from 2026-05-01 through 2026-06-11; messages, tools/results, model metadata, and timestamps | Best longitudinal ML-experiment candidate. Version/deduplicate repeated session snapshots; outcomes are implicit and need independent labels. Hub license `other`; quarantine first. |
| [evalstate/model-toolcall-research @ `061ca7c`](https://huggingface.co/datasets/evalstate/model-toolcall-research/tree/061ca7c19cf3333df71b6d119fd78aee16dc3227) | 15 indexed native Codex research traces/5.47 MB: one provenance session plus repeated per-model investigations with commands, file reads, tool results, model-repository commits, rendering/tests, failures, and evidence reports | Closest bounded analogue to enterprise research: one method applied across many subjects with explicit evidence classes. `NOASSERTION`; not a passive longitudinal population. |
| [biaslab/RAL2026-CPG-ActInf memory @ `cfea3ec`](https://github.com/biaslab/RAL2026-CPG-ActInf/tree/cfea3ecc32869e1cada14c875a8d72468b5338c6/.claude/memory) | 29 research-memory Markdown files and 10 `originSessionId` values; experiment configs, seeds, result paths, statistics, bugs, invalidated runs, contradictions, paper reframing, and follow-up recommendations | Best real experimental-science memory target. Test trace→memory claim support, small-n→large-n conclusion changes, supersession, and honest negative-result retention. Raw source sessions are absent, so origin links cannot yet be replayed. |
| [seokhawn01/wineLab-research @ `c48d48a`](https://github.com/seokhawn01/wineLab-research/tree/c48d48a4787ada6ea4e08e211bd7477ff3dd9409/.claude) | One 230-line dated tool lifecycle log plus four paper-fact-verifier memories; failed/successful WebSearch/WebFetch, certificate/path failures, subagents, and validated-research writes | Real paired partial workflow/memory evidence. Use for friction and trace→memory timing; assistant messages and normalized outcomes are incomplete. |
| [Trace Commons @ `112ebd4`](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf/sessions/claude_code) | 28 volunteered native Claude histories; 14 contain 67 durable-context tool interactions and all 67 have matching results: 19 reads, 37 writes/edits, and 11 Bash/other operations over `MEMORY.md`, project memories, `PROJECT.md`, `CLAUDE.md`, `AGENTS.md`, and skills. At least two same-project cross-session cohorts. | Best real trace-plus-memory pairing found. Use for observed artifact transition and cross-session reuse; contributor selection, scrub/path rewriting, and small cohorts limit population claims. |
| [DiscoverPhysics ARA @ `9be6e92`](https://huggingface.co/datasets/AgentNativeResearchLab/discoverphysics-opus4.8-max-ara/tree/9be6e9264220e922fa7fc18399e2f9187a7a880a) | 11 scientific worlds; 267 files/26.9 MB with 11 native transcripts, 11 judge streams, exploration trees, PM reasoning logs, per-turn logs, logic/evidence/source artifacts, staging observations, and 11 final papers | Near-ideal hypothesis→experiment→observation→claim→paper control. It is a scientific-agent benchmark, not human research; final paper/artifacts must not leak backward without write events. |
| [FrontisAI/NatureBench-traces @ `caa1c5e`](https://huggingface.co/datasets/FrontisAI/NatureBench-traces/tree/caa1c5e1473ac8876e5a0c6ede0141e768e0b163) | 1,080 runs over 90 paper-derived tasks; 1,041 have transcript, submission, judge, and result sidecars, with per-attempt metric changes, validity decisions, and resume history | Controlled scientific-work benchmark and validity oracle, not human longitudinal research. Develop/evaluate detectors here, then measure transfer to real research traces. |
| [OpenDiscoveryTrace @ `b112204`](https://huggingface.co/datasets/aayambansall/OpenDiscoveryTrace/tree/b112204c25ad8944b0d70baf2391dc1647219631) | 432 generated scientific trajectories over 124 drug, materials, genomics, and literature tasks with phase, action/observation/error/revision/confidence/outcome | Structured synthetic control for scientific reasoning phases, not real researchers. |

Additional memory-only strata include
[role-specific opioid-research memories](https://github.com/limserenahansol/opioidaddiction-matlab/tree/8f7f2d84a4dd8bdf25807d869a70e7f4e398273c/.claude/agent-memory)
and
[Burundi household-structure project memory](https://github.com/loveraste/household_structure_burundi/tree/56006f565f83baf1b733c70be1898985fafb029d/.claude).
They are useful target-state/scaffolding examples, but weak longitudinal
evidence until paired traces and artifact revision history are found.

## Canonical representation

Store each durable artifact as:

```text
artifact identity and type
content hash and protected object reference
source repository/home and immutable revision
author or generating mechanism
valid_from / valid_to
system_recorded_at / withdrawn_at
subject, team, project, classification and purpose
source evidence IDs and review state
supersedes / contradicts / derived-from edges
sessions that could have observed the revision
sessions that demonstrably cited or loaded it
```

The current file is never projected backward. A trace at time `t` may use only
the revision whose valid/system-time and authorization envelope made it
available at `t`. File presence is not proof the harness loaded it; preserve
observed injection, read, retrieval, or citation events separately from
availability.

The core analysis unit is an immutable `research_episode`: subject, project,
task/question, start time, canonical trace DAG, source/repository revision, and
the exact artifact snapshot available at episode start. Artifact units are
typed as fact, procedure, preference, constraint, hypothesis, decision,
citation, negative result, or open question. An episode-to-artifact
**availability** edge is not an episode-to-unit **exposure/use** edge.

Represent artifact I/O explicitly:

```text
artifact_snapshot(
  artifact identity, path alias, kind, content hash, protected object ref,
  source event/tool-call identity, observed time, repository revision,
  authority envelope
)

artifact_transition(
  before hash, proposed after hash, application status, later observed hash
)
```

A read establishes an observed snapshot. A write/edit proposes a mutation; a
successful tool result proves application at that moment, not that the revision
remained current forever. Close validity only when a later observation or
mutation supplies evidence. Do not guess from file modification time alone.

Research trajectories additionally need typed evidence for:

- search query and result-set identity;
- source URL/DOI/repository/dataset plus immutable revision;
- acquisition, parse, quote, citation, and rejection events;
- hypothesis/claim revisions;
- experiment configuration, code/environment/data release, seed, output, and
  independent verifier;
- notebook cell and artifact lineage;
- paper/document section diffs and reference edges;
- reviewer/collaborator feedback and response; and
- unresolved questions, limitations, exclusions, and negative results.

## Questions this stratum can answer

| Question | Observable answer | Required boundary |
| --- | --- | --- |
| Which research questions are repeatedly attempted? | Recurrent question/claim/source/method clusters over time | Do not equate similar vocabulary with the same research task |
| Where does a researcher stall and later recover? | Repeated searches, rejected sources, contradictory evidence, failed experiments, and a later independently supported resolution | Final paper text is not automatically ground truth |
| Which memory was useful? | A prior memory revision was available, retrieved/loaded, cited in the decision path, and improves a held-out outcome versus no-memory/placebo | Observational use is not causal benefit |
| Which memory became stale or harmful? | Later evidence contradicts it, it causes a failed prediction/action, or reviewers repeatedly correct it | Preserve historical validity; do not erase the old fact |
| What should become a skill or eval? | Repeated method/procedure with stable inputs, assertions, and external outcomes across held-out tasks | A prose recommendation without replayable evidence is only a proposal |
| Who is working on related research? | Authorized overlap in questions, datasets, methods, sources, or unresolved evidence needs | Introduction requires reciprocal opt-in; no rank or competence inference |
| What capability support is missing? | Repeated evidence-backed friction mapped to a reviewed capability taxonomy and an actionable resource | Must abstain without outcome evidence and expert review |

## Experimental ladder

### R0 — Import and temporal conformance

Import native research traces and every discovered durable-context revision.
Prove exact source counts, tool and citation joins, document/notebook lineage,
artifact version order, and fail-closed authority. Negative controls inject a
future memory revision and an unauthorized team memory; both must yield zero
eligible candidates.

### R1 — Research-signal triage

Run inexpensive detectors before embeddings or judges:

- query rephrasing and repeated source visits;
- citation churn, source rejection, and unsupported-claim markers;
- experiment/notebook failure loops;
- contradictory measurements;
- long stagnation without new evidence;
- repeated reviewer correction; and
- disengagement or abandoned question branches.

Compare against random, recency, length, source-count, and tool-count controls.
Primary outcome is blinded review yield, not detector score.

### R2 — Retrieval factorial

On source-, project-, user-, and time-disjoint splits, compare:

1. identifiers/DOIs/repository/dataset exact match;
2. structured question, method, domain, artifact, and outcome filters;
3. PostgreSQL full text;
4. general embeddings;
5. hybrid retrieval; and
6. a domain adapter only if the general hybrid misses a frozen hard slice.

Hard negatives share terminology or citations but ask a different question.
Positives require human-reviewed task/method/evidence relationships.

### R2b — Forward observational and natural-experiment arms

On forward-only user/project/time splits, measure the incremental predictive
value of trace-only, artifact-presence, artifact-text/typed-unit,
temporal/provenance-graph, and retrieved-unit arms. Report calibration and
incremental value, never causality.

Where an artifact changes at a well-observed boundary, run matched within-user
and within-project pre/post analyses. Interrupted time series or
difference-in-differences is allowed only when timing, comparability, and
parallel-trend checks hold. Label the result quasi-causal. Commit author or
committer time alone is insufficient; use observed checkout/ingest time and
immutable content hashes.

### R3 — Memory attribution

For each later decision, build:

- no-memory baseline;
- artifact-only baseline;
- chronologically valid relevant memory;
- trace plus final artifact snapshot as an intentionally temporally unsafe
  leakage-positive control;
- trace plus event-aligned bitemporal artifact revisions;
- irrelevant but plausible placebo memory;
- stale/superseded memory;
- oracle reviewer-written memory; and
- retrieved raw prior evidence without consolidation.

Measure task/outcome success, evidence support, contradiction, abstention,
turns, cost, latency, unsafe disclosure, and correction burden. Report both
intention-to-treat and actually-retrieved analyses. Only randomized replay or a
prospective trial supports causal benefit.

### R4 — Memory consolidation and rollback

Generate candidate facts, procedures, open questions, and preferences with
source-event citations. A reviewer may accept, edit, reject, scope, expire, or
supersede each candidate. Test contradiction handling, deletion closure,
authority intersection, and rollback to the prior released revision. Generated
memory never directly mutates a live `MEMORY.md`.

### R5 — Cross-user research support

Compute privacy-safe candidate overlap only after current authorization. Show
reviewed abstracts such as “another opted-in group used the same dataset and
resolved a similar measurement issue,” not raw private snippets. Evaluate
reciprocal introduction acceptance and a bounded later outcome prospectively.

## Failure modes that invalidate the study

- using a final paper, current memory file, or later source as context for an
  earlier trace;
- treating file presence as proof of context injection or use;
- treating a citation as agreement, correctness, or successful replication;
- counting subagents, mirrors, forked checkpoints, or transformed exports as
  independent researchers;
- judging the same paper text used to build the retrieval labels;
- fitting and testing an embedding adapter on the same author/project/source
  family;
- flattening conflicting facts into one timeless summary;
- letting a memory inherit broader access than any source evidence;
- surfacing a private cluster size, rare phrase, source, or memory before RLS;
  or
- measuring “productivity” from token volume, session count, commits, or paper
  length.

Kill automatic memory injection if chronologically valid memory does not beat
no-memory while the future/oracle positive control does. If the future/oracle
arm also fails, the instrumentation, retrieval, or evaluator is invalid. If
stale/contradictory-memory harm exceeds relevant-memory benefit after temporal
and provenance safeguards, retain provenance UI and user-triggered retrieval
only.

## Smallest architecture consequence

No additional database is justified. The existing governed PostgreSQL
authority stores canonical trace/event edges, typed research lineage,
bitemporal memory metadata, reviews, and proposals. Large raw transcripts,
papers, notebooks, datasets, and file versions remain in protected object
storage. Full text and pgvector are rebuildable PostgreSQL derivatives after
authority assignment.

The only new product primitive is a **versioned context artifact** linked to
the sessions that could observe it and the sessions that actually loaded or
cited it. Researcher traces then use the same signal → evidence → proposal →
review → prospective-outcome lifecycle as coding traces.
