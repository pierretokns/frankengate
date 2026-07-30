# LangChain eval-engineering skill: Frankengate fit review

**Status:** source-pinned design review

**Date:** 2026-07-30

**Decision:** adopt the guided eval-design contract, not the skill as a trace,
authorization, or eval authority.

## Version and release finding

The requested `eval-engineering` skill is present in
[`langchain-ai/langchain-skills`](https://github.com/langchain-ai/langchain-skills),
but it is newer than the repository's only tagged release:

| Source | Immutable revision | Finding |
| --- | --- | --- |
| Repository `HEAD` reviewed | [`4afeea05`](https://github.com/langchain-ai/langchain-skills/tree/4afeea05bc162716d8a117670bfcbe814a818d02) | Contains `config/skills/eval-engineering/` |
| Latest path change reviewed | [`bbcb0743`](https://github.com/langchain-ai/langchain-skills/commit/bbcb0743b656ca444497e892a8a0b61b3a4d4e27) | Expanded environment-design guidance on 2026-07-30 |
| First path commit | [`89dba19a`](https://github.com/langchain-ai/langchain-skills/commit/89dba19a84020f91bd6a4f9bc7b9f959e99650fd) | Added the skill on 2026-07-22 |
| Latest tagged repository release | [`v0.1.0` / `ffc806a9`](https://github.com/langchain-ai/langchain-skills/tree/ffc806a95c1cef968b1b6d6414173f05617460ac) | Predates the skill and therefore is not a release of `eval-engineering` |

LangChain's
[announcement](https://www.langchain.com/blog/towards-automating-eval-engineering)
describes the skill as available, while the repository still labels the
project early development. Frankengate must pin the commit, not say it adopted
a tagged eval-skill release that does not exist.

The reviewed source includes:

- [`SKILL.md`](https://github.com/langchain-ai/langchain-skills/blob/4afeea05bc162716d8a117670bfcbe814a818d02/config/skills/eval-engineering/SKILL.md);
- trace sourcing, harness, task, environment, verifier, and Harbor references;
- a scripted and model-user multi-turn runner; and
- an example Harbor adapter that records chronological ATIF v1.7.

## What the skill actually contributes

The skill is a disciplined interactive workflow:

```text
map real harness and environment
  -> inspect a small complete trace batch when supplied
  -> propose two or three eval directions
  -> obtain user approval for one capability boundary
  -> build one Harbor task
  -> calibrate its verifier
  -> run the real harness
  -> inspect artifacts and ask for acceptance
```

Its most important concepts are separations, not a particular evaluator:

| Concept | Operational rule | Frankengate value |
| --- | --- | --- |
| Harness | Preserve the real model, prompts, loop, tools, middleware, memory, and session behavior | Prevent a simplified replay wrapper from being called the production agent |
| Environment | Put files, services, records, identity, permissions, network, clock, and mutable state outside the harness | Makes dependencies resettable and exposes environment-caused failures |
| Task | One request must make one capability necessary | Produces small, interpretable regression cases rather than omnibus scenarios |
| Verifier | Judge against independently observable evidence | Stops a recorded answer or agent-authored tool list from becoming truth |
| Trace sourcing | Start with complete traces; treat them as observations, not expected answers | Matches Frankengate's evidence-first, proposal-only model |
| Failure semantics | Adapter, build, reset, timeout, credential, judge, and verifier failures are infrastructure errors | Prevents infrastructure faults from becoming user or agent quality labels |
| Multi-turn fidelity | Reuse one session, never preload future turns, record the origin of every turn | Preserves the behavior that a conversational eval is intended to test |

### Particularly strong details

1. **The trace is not the oracle.** A trace can suggest a task condition or a
   realistic wrong-result fixture. Independent environment state, tests,
   records, or reviewed evidence must define success.
2. **A verifier is calibrated before the agent run.** At minimum, one clearly
   capable result must pass and one realistic wrong result must fail through
   the same verifier image and command.
3. **The environment preserves production-shaped interfaces.** Repository tool
   code stays in the harness; only the data or service behind that interface is
   frozen or simulated.
4. **Task scaffolding must not leak the answer.** Hidden tests, judge rubrics,
   simulator instructions, expected state, and verifier credentials stay
   unavailable to the harness.
5. **Stopping is not success.** A scripted or simulated user can terminate a
   conversation, but only the verifier assigns reward.
6. **Run evidence is inspected, not inferred.** Tool use must come from
   harness-recorded calls and environment-observed effects, never from agent
   prose.

## What does not compose directly

The skill solves eval construction for one repository and one approved task.
It does not supply Frankengate's enterprise trace-intelligence authority.

| Missing or conflicting behavior | Consequence | Frankengate rule |
| --- | --- | --- |
| No tenant, subject, team, purpose, classification, consent, or authorization epoch | A Harbor task directory cannot decide who may see or derive from a trace | Every source, proposal, fixture, run, score, and release inherits the governed envelope |
| No deletion or reclassification closure | A copied task could outlive authorization to its source trace | Maintain source evidence IDs and withdraw derived fixtures and results when policy changes |
| Preserves source trace IDs in working analysis | Useful locally but unsafe in aggregate and cross-user views | Keep identifiers only inside the authorized review scope; publish content-free aggregates |
| Human chooses one task direction | Deliberately not an automatic population-mining pipeline | Cheap signals can nominate traces, but a person approves the capability and task boundary |
| Harbor ATIF output is sequential | It cannot replace the richer event DAG for retries, overlap, fallback, or distributed joins | Export ATIF plus a loss receipt from the canonical trajectory |
| Uses the latest Harbor implementation | Adds a separate runner and container supply chain | Treat Harbor as an isolated eval execution backend, not the trace or policy store |
| No cohort privacy or reciprocal consent | Cannot justify “people doing similar work should talk” | Cross-user releases remain anonymous artifacts or reciprocal opt-in introductions |
| No intervention registry | A passing eval does not show that a suggested prompt, memory, or skill helps users | Record exposure, acceptance, independent outcomes, harms, and rollback |

The skill should therefore remain a design and execution adapter behind
Frankengate. It must never read unrestricted enterprise traces directly or
write live evals, memories, prompts, or skills without the governed release
path.

## Frankengate product flow

The appropriate composition is:

```text
authorized personal trace
  -> deterministic friction/eval-candidacy signals
  -> evidence-linked eval proposal
  -> guided capability boundary
       harness: exact deployed revision
       environment: live, frozen, or simulated per dependency
       verifier: independent pass condition
  -> privacy and lineage review
  -> isolated Harbor or native runner task
  -> verifier calibration
  -> changed-system run
  -> immutable eval release
  -> CI/shadow execution and rollback
```

The user-facing guide should ask:

1. What behavior in this trace should never regress?
2. Which evidence events show the condition, and what remains unknown?
3. Which deployed harness revision should be tested?
4. Which dependency must be live, frozen, or simulated?
5. What independently observable state or result means success?
6. What plausible wrong result must the verifier reject?
7. Is this a retrospective trace assertion or a rerun against a changed system?
8. Who may inspect the source, fixture, run, and released eval?

The UI should preview a proposed task boundary rather than expose a generated
test as already valid:

```text
Capability: recover from a typed shell-tool failure without repeating it
Source evidence: explicit error and bounded later same-family completion
Harness: unresolved until repository and deployed revision are selected
Environment: unresolved until filesystem, network, and permission dependencies are known
Verifier: unresolved until an independent test or state transition is supplied
Lifecycle: proposal; human review required
```

This is the correct result for the current public Wisp experiment. The trace
can nominate a bounded recovery episode, but it lacks an independently
verified task outcome and resettable repository environment. Automatically
turning that episode into a “passing eval” would violate both the LangChain
skill's verifier rule and Frankengate's evidence policy.

## Empirical integration gates

Before exposing “Create eval from this trace” as more than a proposal:

1. **Trace-to-boundary fidelity:** a reviewer agrees that the proposed
   capability and dependency condition are supported by cited event IDs.
2. **Harness parity:** the runner records a content hash for every reachable
   harness-owned module and names any reconstruction.
3. **Environment contract:** operations, state, rules, failures, effects,
   permissions, and reset are explicit and tested twice.
4. **Verifier calibration:** a valid paraphrase or equivalent solution passes;
   a realistic wrong result, unsupported claim, and fabricated tool-use report
   fail.
5. **Mutation utility:** exact, ordered, unordered, forbidden-event, semantic,
   and state assertions are evaluated only where applicable; normal allowed
   variations must not fail.
6. **Authority closure:** denial, stale epoch, reclassification, consent
   withdrawal, and deletion make the source and every derivative
   non-returnable before execution or ranking.
7. **Changed-system evidence:** a regression claim requires an actual run of
   the changed harness. A stored-trace matcher remains a retrospective audit.

## Build decision

**Build now:**

- an evidence-linked eval-proposal record;
- the eight-question guided boundary form;
- harness/environment/verifier fields and missingness;
- verifier calibration fixtures;
- immutable runner artifacts and source hashes; and
- an ATIF export with a canonical loss receipt.

**Defer:**

- automatic task generation from every failed trace;
- organization-wide task mining;
- LLM-user simulation by default;
- automatic release into CI; and
- a Harbor production dependency until a real Frankengate harness task passes
  the parity, reset, verifier, and authority gates.

**Reject:**

- treating trace text as a reference answer;
- scoring infrastructure failures as agent failures;
- trusting agent prose as tool execution evidence;
- calling a stored-trace assertion a rerun; and
- letting an eval task widen the source trace's audience.

The skill materially improves Frankengate's proposed eval wizard. It does not
change the one-database architecture, the canonical-DAG decision, or the need
for prospective enterprise validation.
