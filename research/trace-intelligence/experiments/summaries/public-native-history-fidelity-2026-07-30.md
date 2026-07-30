# Public native-history fidelity study

**Date:** 2026-07-30
**Status:** complete aggregate structural audit
**Result:** [`public-native-history-fidelity-2026-07-30.json`](../results/public-native-history-fidelity-2026-07-30.json)
**Result SHA-256:** `6e92d94d5c1ae8a72369e4b9678bb156b0045e7d5c8ad54298e87465beb511a1`
**Privacy boundary:** no raw content, identifiers, or source paths emitted

## Question

Which public coding-agent histories preserve the native evidence Frankengate
needs for user history, trace mining, memory/eval proposals, and eventual
enterprise studies? Which are transformed derivatives that only look complete
in a dataset viewer?

Hugging Face's
[Agent Traces documentation](https://huggingface.co/docs/hub/en/agent-traces)
defines the key baseline: Claude Code, Codex, and Pi Agent raw JSONL sessions
can be uploaded without conversion. A session-complete derivative, a
record-preserving scrubbed export, a project-tree mirror, and a complete
harness home are still materially different artifacts.

## Method

The audit parsed every available record in six downloaded sources, one
deterministic eight-workflow sample, and the existing Wisp aggregate. It
measured:

- files, session rows, distinct native session IDs, records, messages, and
  malformed lines;
- tool calls, tool results, exact ID joins, ambiguous IDs, and unresolved
  calls/results;
- parent edges, branches, subagent signals, compaction, timestamps, model,
  usage, and project metadata;
- declared and observed redaction evidence;
- high-confidence secret-shaped regex candidates, without retaining or
  emitting their values; and
- exact loss receipts for every transformation.

The scanner traversed strings only to produce category counts. It serialized no
prompt, reasoning, tool argument, tool result, native identifier, project name,
or local path. Public sources without a clear license are retained for
inspection under `NOASSERTION`; public visibility is not presented as
redistribution or training permission.

## Results

| Source | Actual representation | Scope parsed | Messages | Calls / results | Exact joins | Topology retained |
|---|---|---:|---:|---:|---:|---|
| cfahlgren Codex | Byte-native Codex rollouts plus an exact duplicate viewer projection | 2 files, 130 records | 18 | 2 / 2 | 2 | No parent/subagent structure in this tiny sample |
| Alin Fable 5 Claude | Scrubbed, record-preserving Claude event streams | 18 files, 9,497 records | 3,930 | 1,170 / 1,170 | 1,170 | 7,593 joined parent refs, 624 branch points, 1,195 subagent signals, 2 compaction records |
| Wisp Claude | Credential-replaced project-session tree mirror | 104 files, 10,698 valid records | 6,805 | 2,209 / 2,207 | 2,206 exact-prior | 20 branch points and 43 nested-subagent files |
| Mike Codex | Sanitized Codex records inside an added dataset envelope | 27 files, 12,316 records | 2,359 | 3,182 / 3,175 | 0 | No call IDs, parents, branches, or compaction |
| Jobseek Claude sample | Complete workflows after header insertion and main/subagent merge | 8 files, 1,851 records | 1,555 | 579 / 577 | 577 | 1,717 parent refs, 185 branches, 878 subagent signals, but original file boundaries lost |
| Ranga Codex/pi-brain | Flattened and redacted session/message derivative | 79 rows, 22,876 messages | 22,876 | 7,447 / 7,439 | 7,439 | Parent, branch, subagent, compaction, usage, and native record types absent |
| Peter DataClaw mirror | Flattened longitudinal Claude conversations | 549 rows, 169,168 messages | 169,168 | 80,409 / 0 | 0 | Tool outputs, native IDs, parents, branches, subagents, and compaction absent |

### Important discrepancies

- Mike's 27 files contain 49 `session_meta` records and 32 distinct session
  IDs. The files contain 12,316 records, 432 more than the included manifest's
  declared 11,884. Two files contain multiple session IDs.
- Mike removed call IDs. Its 3,175 order/cardinality pairs are not exact
  call-result joins.
- Ranga's file contains the declared 73 Codex rows and 22,528 Codex messages,
  plus 6 OpenCode rows and 348 messages. The 73 Codex rows contain only 64
  unique Codex session IDs, leaving 9 duplicate rows.
- Peter DataClaw declares 549 sessions but has 503 unique session IDs. Its card
  points loaders to Peter O'Malley's source, so this repository is a mirror,
  not a second user.
- Jobseek's sample header counts exactly match all 1,851 following records.
  The complete workflow is preserved, but `_scope`/agent metadata replaces the
  original main/subagent file tree.
- cfahlgren's two derived viewer rows are byte-equal to the two raw rollout
  files. This is the clean native control, but it is far too small for
  longitudinal inference.

### Privacy observations

Alin, Ranga, DataClaw, and Mike contain abundant structural evidence of
redaction. The high-confidence scan found no secret-shaped candidates in Alin,
Ranga, DataClaw, Jobseek, or the two cfahlgren raw sessions. It found six
JWT-shaped candidates in Mike. These are unvalidated regex candidates, not a
claim that live credentials exist; the raw source should remain quarantined
until reviewed. No candidate value appears in the result.

## What is actually native?

- **Byte-native session files:** only the two cfahlgren Codex rollouts in this
  newly downloaded set.
- **Native event graph after content transformation:** Alin's 18 Claude files.
  Their record topology is intact, but 35,732 declared scrub operations mean
  they are not byte-native.
- **Native project-session tree after credential replacement:** Wisp. It is the
  closest source to a real harness transcript subtree because nested subagent
  files remain separate.
- **Record-preserving normalized derivative:** Mike. Codex record and payload
  types remain, but the added envelope and removed tool IDs are material.
- **Merged workflow derivative:** Jobseek. It is session-complete for its task,
  but main and subagents have been combined.
- **Flattened derivatives:** Ranga and DataClaw. Both originate from real
  harness stores but cannot be used to validate a native parser or event DAG.
- **Complete harness home:** none.

No audited source contains all settings, global memories, skills, hooks, MCP
configuration, account state, caches, and transcripts from a real user's
entire harness directory. That absence is desirable for credentials and opaque
caches. Frankengate needs a typed governed export, not indiscriminate home
directory copying.

## Direct relevance to the enterprise questions

### Repeated friction and later recovery

Alin and Wisp are the best structural sources because calls, results, parent
edges, and subagents survive. Ranga can support flattened call/result sequence
studies over several months, but it cannot explain native retries, branches, or
compaction. DataClaw provides stronger longitudinal project coverage but no
tool results, so it cannot establish a failed-call-to-repair chain.

These corpora can test whether Frankengate surfaces useful candidate episodes.
They cannot establish why a user failed, whether the repair was correct, or
whether the person lacked a skill.

### Similar work across users

None of these seven strata is a valid independent cross-user enterprise panel.
Different public publishers are not employees in one organization, Mike and
Jobseek are autonomous/task collections, and the DataClaw repository is a
mirror. The gated SWE-chat source remains the appropriate cross-user,
outcome-linked candidate after authorization and ethics review.

### Skill, prompt, memory, and eval suggestions

The native sources can generate evidence-backed **proposals**:

- exact failed tool call/result pairs can become candidate eval fixtures;
- repeated task/project episodes can become candidate procedures;
- compaction and later-reference episodes can test candidate memory; and
- contrasting branches can support failure localization.

They do not supply verified enterprise capability labels or causal intervention
outcomes. Frankengate must replay or prospectively evaluate every suggestion
under user/project/time-held-out splits and record which memory or skill
influenced the later trace.

### Fine-tuning

The study does not establish training rights or label quality. Even MIT or
CC-BY dataset metadata may not settle rights in embedded third-party code and
tool output. Mike and cfahlgren are `NOASSERTION`; Jobseek explicitly carries a
`not-for-AI-training` tag. Before any embedding fine-tune, use admitted sources
only to design a governed labeling protocol, then train on material with
verified rights, deletion handling, independent outcomes, and user/time/project
splits.

## Decision

1. Use cfahlgren as the byte-native Codex parser control.
2. Use Alin and Wisp for event graph, call/result, branch, subagent, and
   compaction fidelity.
3. Use Ranga as a flattened Codex negative control and limited longitudinal
   call/result source.
4. Use Peter DataClaw for longitudinal candidate retrieval only, never native
   tool-result or independent-user claims.
5. Use the Jobseek sample for merged-workflow reconstruction and repetitive-task
   controls, not human or population inference.
6. Keep Mike quarantined for schema tests; its missing call IDs, count mismatch,
   autonomous sessions, `NOASSERTION` rights, and six secret-shaped candidates
   prohibit broader admission without review.
7. Do not claim enterprise improvement until a consented prospective
   Frankengate study measures outcomes.
