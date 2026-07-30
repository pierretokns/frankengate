# Wisp content-minimized Frankengate analysis arms

**Status:** reproducible aggregate analysis complete

**Run date:** 2026-07-30

## Research question

How far can Frankengate progress from a real longitudinal harness export toward
enterprise trace intelligence without serializing transcript content or
inventing outcomes that the source does not contain?

The experiment runs five cumulative arms over the pinned
[`crispwisp/wisp-claude-code-sessions`](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions)
snapshot:

| Arm | Added mechanism | Permitted claim |
| --- | --- | --- |
| S0 | ingestion metadata and quality | corpus and lifecycle coverage |
| S1 | deterministic signals | candidate selection for review |
| S2 | exact/structured controlled vocabulary | content-free retrieval mechanics |
| S4 | temporal error/retry reconstruction | proposal-only episode candidates |
| S6 | eval, memory, and procedure records | bounded review queues, not promotion |

The analyzer never reads prompt text, reasoning, tool arguments, tool-result
content, or filesystem path values. It serializes no native or synthetic
session/event identifiers, exact timestamps, paths, or per-session rows. The
committed result contains aggregate counts only.

## Results

| Measurement | Result |
| --- | ---: |
| Sessions | 104 |
| Valid / malformed records | 10,698 / 2 |
| Tool calls / results | 2,209 / 2,207 |
| Linked tool-result share | 100% |
| Explicit tool errors | 103 |
| S1 signal-selected sessions | 62 |
| S2 structured-retrieval sessions | 88 |
| S4 temporal episode candidates | 92 across 7 sessions |
| S4 high / medium / low specificity | 53 / 31 / 8 |
| S6 eval-review records | 103 |
| Repeated structural memory-review motifs | 3 |
| Episodes supporting those motifs | 69 |
| Automatic memory/skill writes | 0 |
| Skill-gap recommendations | 0 |
| Cross-user collaboration recommendations | 0 |

The review policy allocates 20% of the corpus, bounded to 10–25 sessions. It
therefore selects 21 sessions in broad S1 and S2 arms. S4 has only seven
eligible sessions and S6 has eleven, so the review queue does not pad either
arm with unrelated sessions.

### Candidate overlap

S1 and S2 overlap on 51 sessions (Jaccard 0.5152), while S1 and S4 overlap on
only seven (Jaccard 0.1129). Deterministic signals are therefore much broader
than reconstructable error/retry episodes. Treating every selected friction
signal as an episode would substantially overstate the evidence.

All seven S4 sessions are also S6 proposal candidates, but four additional S6
sessions have explicit errors without a qualifying temporal recovery chain.
That distinction is useful for the UI: “an error worth turning into an eval”
and “a possible recovery worth reviewing as a procedure” are different
objects.

### Recovery specificity proxies

Every explicit error result links to a known tool proposal. The greedy
one-to-one temporal reconstruction finds a later, newly proposed, non-error
tool result within 24 records for 89.32% of errors. Of those candidates:

- 57.61% use the same tool family within eight records;
- 91.30% use the same tool family within 24 records;
- 8.70% switch tool family within that window.

These are structural specificity proxies, not empirical precision estimates.
A non-error tool result does not prove that the task succeeded, that the action
was correct, or that the later action caused recovery. The source provides no
independent outcome or environment-state label with which to measure those
claims.

### Strata

The seven sessions with S4 candidates comprise three main-user sessions, two
nested-subagent sessions, one benchmark-development session, and one
benchmark-task session. Keeping those strata separate is load-bearing:
subagent failures, benchmark authoring behavior, benchmark executions, and the
human's ordinary work are not interchangeable evidence.

## Direct answer to the enterprise questions

This experiment supports the following Frankengate product behavior now:

- show a user all of their own sessions under policy;
- identify malformed, branched, incomplete, and error-bearing traces;
- retrieve traces by controlled structural facts without an embedding model;
- rank a bounded evidence-review queue;
- propose an error trace as a candidate regression eval;
- propose a narrowly defined error/retry chain for memory or procedure review.

It does **not** support claims that:

- a user lacks a skill or is less productive;
- a temporal candidate is a correct recovery;
- a repeated structural motif contains a reusable fact or procedure;
- two people should collaborate;
- a memory, prompt, skill, model, or fine-tune would improve work.

Those are not conservative versions of the same analysis; they are different
estimands requiring independent task outcomes, environment/access/tool
availability labels, scoped content review, multiple consented users, and a
prospective intervention.

## What the combined local system should do

The smallest justified pipeline remains:

```text
native governed trace
  -> loss-aware canonical event graph
  -> current authority / purpose / classification gate in PostgreSQL
  -> S0 quality checks
  -> S1 deterministic signals
  -> S2 exact / structured retrieval
  -> S4 temporal episode reconstruction
  -> S6 versioned proposal records
  -> scoped human review
  -> isolated replay or prospective intervention
  -> independent outcome
```

This result does not justify adding an embedding model, graph database, or
automatic dream/memory writer. PostgreSQL structure and controlled terms are
enough to build the first review queues. Dense retrieval becomes an
experimental arm only when semantic task grouping is evaluated against labels
that exact and structured retrieval cannot recover.

## Next empirical gates

1. Have reviewers label the 21-session queue for actual friction category,
   environmental blocker, retry relationship, and task outcome while keeping
   raw evidence governed and uncommitted.
2. Measure S4 precision and recall against those labels; the present
   specificity shares are not substitutes.
3. Run the same episode constructor on the outcome-bearing CMU corpus and
   estimate whether candidate tiers predict reward or evaluator success.
4. Run a separate consented multi-user study for task similarity and reciprocal
   collaboration; do not fabricate an enterprise by combining unrelated public
   contributors.
5. Promote an eval, memory, or procedure only through versioned review,
   provenance, replay, canary measurement, and rollback.

## Reproduction

```bash
python3 research/trace-intelligence/real_user_analysis_arms.py \
  /path/to/pinned/transcripts \
  --manifest research/trace-intelligence/configs/datasets/wisp-claude-code-sessions.json \
  --output research/trace-intelligence/experiments/results/wisp-content-minimized-analysis-arms-2026-07-30.json
```

The synthetic tests inject secret prompts, reasoning, commands, paths, tool
outputs, and native identifiers, then assert that none appear in serialized
analysis output.
