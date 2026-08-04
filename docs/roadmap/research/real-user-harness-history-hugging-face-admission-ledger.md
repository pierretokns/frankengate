# Real-user coding-agent histories on Hugging Face: admission ledger and enterprise-transfer plan

**Research date:** 2026-07-30

**Scope:** deliberately published coding-agent histories from real users,
including `NOASSERTION` sources for analysis; no unsupported redistribution or
training-right claim is inferred from public availability

**Decision:** real longitudinal histories are abundant enough for the proposed
experiments. The strongest home-level find is a partial `~/.claude` tree; no
verified source in this review is a literal complete global `~/.claude` or
`~/.codex` directory.

**Empirical update:** the aggregate-only
[native-history fidelity study](../../../research/trace-intelligence/experiments/summaries/public-native-history-fidelity-2026-07-30.md)
fully parsed six additional downloaded sources, one deterministic Jobseek
sample, and the existing Wisp aggregate. A follow-up manifest audit found the
Glint/Fable partial Claude home, multiple GitHub-native Codex collections, and
portable Claude session bundles. It confirms that “native,”
“session-complete,” “longitudinal,” and “complete harness home” are different
properties. The broader Hub searches returned roughly 180 overlapping
candidates, not 180 unique real users; mirrors, autonomous workflows,
synthetic/SFT derivatives, and duplicate session rows must be removed before
counting.

## Executive answer

There are three materially different things that are easy to conflate:

1. **Session-complete exports** preserve a conversation, tool calls, tool results, and sometimes thinking.
2. **Transcript-tree mirrors** preserve the relative layout of a harness's session subtree, such as `~/.claude/projects/<project>/<session>.jsonl`.
3. **Home-directory-complete exports** would preserve everything under `~/.claude` or `~/.codex`, including settings, memories, skills, MCP configuration, caches, account state, and potentially credentials.

We found many examples of the first, multiple examples of the second, one
published partial home with adjacent history/cache state, and one genuine
near-complete public Claude home-state tree. The near-complete tree is not a
safe wholesale corpus: it has no declared license, appears unredacted, retains
only one project transcript, includes auth-adjacent state, and is missing
several home areas.

The strongest sources are:

- [SWE-chat](https://huggingface.co/datasets/SALT-NLP/SWE-chat/tree/f66cca95b14caaa4177f7ed5eaa424608dadcffa) for cross-user, outcome-linked analysis: 5,851 real sessions, 205 public repositories, full transcripts, tool activity, commits, diffs, and human/agent code attribution.
- [TraceLab v0.0.1](https://github.com/uw-syfi/TraceLab/tree/fc061574a0f9700ccf88be33112adc8e86b425fa) for privacy-reduced cross-user operational analysis: 357,161 LLM rounds from 43 pseudonymous developers, but semantic tool inputs and outputs are deliberately removed.
- [nmuendler/share-codex](https://huggingface.co/datasets/nmuendler/share-codex/tree/3d8b1397c72dbfbf8b04f518064e2c99dde84ca0) for a deep single-user longitudinal study: 4,333 sessions from `~/.codex/sessions` and `~/.claude/projects` spanning 2025-10-10 through 2026-06-18.
- [peteromallet/my-personal-codex-data](https://huggingface.co/datasets/peteromallet/my-personal-codex-data/tree/8c9543389161e80628dcb183b30f8c6be04f627a) for a second single-user longitudinal study: 1,297 sessions in 63 daily shards, with messages, thinking, tool inputs, tool results, and status.
- [crispwisp/wisp-claude-code-sessions](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce) for native Claude Code structure, branches, parent links, and nested subagents. It mirrors the `~/.claude/projects` transcript layout, not the entire `~/.claude` directory.
- [Glint-Research/Fable-5-traces](https://huggingface.co/datasets/Glint-Research/Fable-5-traces/tree/e05c417852fc59fd8da758e68b352732423ca0cb/claude) for partial-home import fidelity: 115 project/session JSONL files, 36 nested subagent files, 1,758 `history.jsonl` records, paste cache, and cache metadata under one published `claude/` tree.

These sources can support empirical work on recurring friction, task recurrence, tool-use patterns, candidate memories, and candidate evals. They do **not**, by themselves, justify conclusions about employee competence, productivity, missing skills, or who should collaborate. Those are prospective hypotheses that require enterprise-grounded labels, consent, interventions, and measured outcomes.

## Admission definitions

| Level | Required contents | Found? | Enterprise use |
|---|---|---:|---|
| Session-complete | Ordered user/assistant events, tool proposals/calls/results, timestamps | Yes | Friction, recovery, tool patterns, eval and memory candidates |
| Project-longitudinal | Stable person or pseudonym, project, time, multiple sessions | Yes | Repeated work, recurring friction, temporal memory tests |
| Cross-user-longitudinal | Stable user identities across many projects/sessions | Yes, in SWE-chat and TraceLab | Similar-task cohorts and privacy-safe aggregate hypotheses |
| Outcome-linked | Commits, diffs, tests, CI, reward, or verified task outcome | Partly | Repair and transfer evaluation; most outcomes remain proxies |
| Transcript-tree mirror | Native session subtree and parent/subagent layout | Yes, Wisp, Glint, and GitHub-native collections | Parser/schema fidelity and delegation studies |
| Partial harness home | Sessions plus one or more adjacent global/index/cache/config areas | Yes, Glint; portable per-session bundles also exist | Import completeness receipts, area policy, replay/resume fidelity |
| Near-complete harness home | Most global state areas plus at least one native transcript, with explicit missing areas | Yes, one high-risk GitHub source | Completeness/threat-model fixture and lane-policy tests; never wholesale training input |
| Literal complete harness home | Every session plus settings, skills, memories, MCP configuration, caches, indexes, and account state | No verified source found | Unsafe and unnecessary as a normal import target |

“Complete conversation” also does not mean “complete trajectory.” A source may omit system/developer prompts, reasoning, rejected tool calls, permission decisions, retry/fallback edges, environment state, or whether a code change was correct.

## Admission ledger

### A. Cross-user sources

| Source and pinned revision | Real users and longitudinal identity | What is preserved | Consent, license, and privacy | Decision and enterprise-transfer value |
|---|---|---|---|---|
| [SWE-chat @ `f66cca9`](https://huggingface.co/datasets/SALT-NLP/SWE-chat/tree/f66cca95b14caaa4177f7ed5eaa424608dadcffa), ODC-BY | Real developers using Claude Code, Codex, Gemini CLI, Cursor, OpenCode, and Copilot CLI. `user_id` is derived from public commit attribution and is joinable across sessions. | 5,851 sessions, 2,692,480 conversation rows, 13,406 checkpoints, 14,459 commits, 205 repos, tool calls/results, thinking, touched files, full diffs, and agent/human code attribution. An LLM-derived `session_success` field is present but is not ground truth. | Gated; access requires sharing Hugging Face contact information. Collected from public GitHub checkpoint branches, redacted with Presidio and TruffleHog, and offers a removal path. Public availability is not equivalent to direct research consent. | **Highest-value gated source.** Use for similar-task cohorts, repeated work, and outcome-linked hypotheses after access authorization and ethics/privacy review. Do not treat LLM success scores or committed lines as employee performance. |
| [TraceLab v0.0.1 @ `fc06157`](https://github.com/uw-syfi/TraceLab/tree/fc061574a0f9700ccf88be33112adc8e86b425fa), CC BY 4.0 data | 43 pseudonymous developers, joinable session/continuation/user identities. | 357,161 LLM rounds and 432,510 tool records from real Claude/Codex sessions. Token, cache, timing, tool name, error, and structural command metadata remain. Local paths, tool inputs, and full tool outputs are removed. Pinned assets have documented hashes. | Purpose-built public research release; stable pseudonyms; explicit request not to reidentify. | **Admit for operational and behavioral analyses.** Excellent privacy-preserving negative control. It cannot support domain-semantic task similarity, missing-skill inference, or memory-fact extraction because the decisive content was stripped. |
| [Trace Commons @ `112ebd4`](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf), CC BY 4.0 compilation | Real voluntarily donated sessions, but no stable contributor field suitable for a longitudinal person panel in the normalized table. Current raw inventory: 28 Claude Code, one Cursor, and one OpenCode session; Codex and Pi directories are empty. | Raw native session files, ordered messages, tools, calls, results, and harness-specific metadata. | Strongest contribution process found: public OSS work only, local scrubber, TruffleHog backstop, contributor review, explicit confirmation, and maintainer PR review. The card warns anonymization is imperfect and embedded code retains its original licensing. | **Admit as a parser and ethics reference corpus.** Too small and insufficiently identity-linked for enterprise cross-user findings. |
| [SWE-chat paper and card](https://arxiv.org/abs/2604.20779) | Same source as the first row | The paper documents annotated intent/persona/success fields and real-world collection. | Research annotations are model-generated and must be separated from observed evidence. | Use annotations as hypotheses or stratifiers, never as authoritative skill or success labels. |

### B. Single-user longitudinal sources

| Source and pinned revision | Real user and longitudinal scope | What is preserved | Privacy and license | Decision and enterprise-transfer value |
|---|---|---|---|---|
| [nmuendler/share-codex @ `3d8b139`](https://huggingface.co/datasets/nmuendler/share-codex/tree/3d8b1397c72dbfbf8b04f518064e2c99dde84ca0), CC BY 4.0 | One public dataset/export context; 4,333 sessions over about eight months. The rows do not expose a separate stable employee identifier, so “one user” is a dataset-level inference, not a row-level guarantee. | 202,056 messages, 81,057 tool calls, 80,568 tool outputs, Codex CLI/exec/VS Code/MCP/subagent sessions, plus 19 Claude Code sessions. Internal prompts/reasoning are excluded. | Source scanned `~/.codex/sessions` and `~/.claude/projects`. The author excluded 37 cwd prefixes, removing 3,003 rows; scanner redaction made 4,476 replacements from 132 findings. Project license was not found for 3,622 of 4,333 rows. | **Restricted admit.** Best single-person source for temporal friction, recurrence, and candidate-memory experiments. Embedded tool output and unknown project licensing require an isolated research enclave and content-risk filtering. |
| [peteromallet/my-personal-codex-data @ `8c95433`](https://huggingface.co/datasets/peteromallet/my-personal-codex-data/tree/8c9543389161e80628dcb183b30f8c6be04f627a), MIT card | Self-published personal Codex history: 1,297 sessions, 63 date shards from 2026-02-16 through 2026-04-25. | User/assistant messages, thinking, tool input/output/status, project, branch, timestamps, model, and aggregate usage. | DataClaw reports 62,661 redactions. Paths are project-relative and usernames hashed. Automated redaction is explicitly best effort. Dataset-level MIT metadata does not override licenses or third-party rights in embedded source material. | **Restricted admit.** Strong second longitudinal cohort for replication across a different user's work. No verified task outcome, issue identity, test result normalization, or stable cross-user identity. |
| [lelouch0110/claudeset-community @ `fe11da9`](https://huggingface.co/datasets/lelouch0110/claudeset-community/tree/fe11da9ac006d5592378a3d284ee2ed81ffb7578), MIT | Card says real daily Claude Code use and contributor consent. Current pinned shard contains 114 sessions, one hashed contributor, 23 projects, 1,158 exchanges, 467 compacts, and 3,862 tool calls from 2026-01-27 through 2026-03-01. | Ordered exchanges, thinking, tool inputs/outputs, context compacts, model, project, branch, dates, and token statistics. | Community push redacts credentials, usernames in paths, emails, phones, credit cards, and high-entropy strings. Personal-repo pushes do not receive the same redaction, but this is the community dataset. | **Admit after secondary content scan.** Explicit contribution intent and compact events are valuable for studying memory/context loss. Current snapshot is one contributor, not a cross-user corpus. |
| [crispwisp/wisp-claude-code-sessions @ `c2c90b5`](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce), MIT | One named user's workstation. 61 root session files plus 43 subagent/workflow files. It mixes real voice-driven work with automated Hyprland benchmark tasks. | Native Claude Code JSONL, UUID/parent UUID, cwd, session, version, git branch, text, thinking, tool use/result, and nested workflow journals. `transcripts/` mirrors the `~/.claude/projects/` layout. | Credentials were replaced, but the card intentionally retains public identity and warns that transient host state and file snippets remain. | **Quarantine, then use narrowly.** Closest source to native transcript-tree structure and best for branch/subagent parser fidelity. Do not use the benchmark portion as evidence about human behavior; do not release derived text without review. |
| [michaelwaves/my-personal-codex-data @ `2ac8473`](https://huggingface.co/datasets/michaelwaves/my-personal-codex-data/tree/2ac84737812defdc1b3a8482c4897205534ab327), MIT | Self-published history: 151 sessions across 32 projects. | Messages, thinking, tool calls/results, branch, time, model, project, and stats. | Paths are project-relative and usernames hashed. No detailed consent protocol beyond self-publication. | **Reserve replication source.** Useful for checking whether findings from the two larger users generalize, but underpowered for cross-user conclusions by itself. |

### C. Exclude, hold, or use only as controls

| Source | Why it is not a real-user enterprise cohort |
|---|---|
| [Mike0021/codex-sessions @ `29b52c1`](https://huggingface.co/datasets/Mike0021/codex-sessions/tree/29b52c15654087c5c5d0adcd062bfe40f6464d6b) | 27 sanitized autonomous Codex files building Hugging Face Spaces. The empirical audit shows that these are record-preserving normalized derivatives, not byte-native fixtures: an envelope was added, call IDs are absent, and observed/declared record counts disagree. Useful only as a schema/loss control. The card does not declare a dataset license (`NOASSERTION`). |
| [ultralazr/claude-code-traces @ `afe3c10`](https://huggingface.co/datasets/ultralazr/claude-code-traces/tree/afe3c108c148427625f7b2275791517f99f8115d) | One redacted native session; useful only for parser testing. License is `other`, and the card warns embedded images and private material can remain. |
| [Zen Agentic Dataset @ `cdc75ca`](https://huggingface.co/datasets/zenlm/zen-agentic-dataset/tree/cdc75caa622c76b86d040a3423c58c9b4aa335b1) | Claims millions of real Claude Code entries, but the pinned Hugging Face repository currently exposes only documentation/source files, requires commercial licensing contact, and does not document a contribution/consent process adequate for this study. |
| Personal-history forks that duplicate another user's repository | They are not independent users. For example, `misterkerns/my-personal-claude-code-data` identifies itself as a duplicate of Peter O'Malley's source. Treating forks as people would invalidate cross-user statistics. |
| `segin/my-personal-codex-data` at `0108ae7` | Public but has no dataset license in the Hub metadata. Hold until provenance and rights are clarified. |
| Synthetic benchmark and distillation traces | Useful for ground-truth task outcomes and format diversity, but not evidence about real user needs, work patterns, learning, or organizational collaboration. Keep them in a separately labeled benchmark stratum. |

### D. Native-fidelity and transformation controls added by empirical audit

| Source and pinned revision | Observed structure | Fidelity decision |
|---|---|---|
| [Alin Fable 5 Claude @ `e33ebbca`](https://huggingface.co/datasets/AlinCiocan/fable-5-claude-code-traces/tree/e33ebbca230ae258b2c28aeee9fe3429e7fbeab6), CC-BY-4.0 | 18 files and 9,497 records; 1,170/1,170 tool calls/results joined exactly; 7,593 parent references, 624 branch points, 1,195 subagent signals, and two compaction records. Publisher declares 35,732 scrub operations. | **Admit for scrubbed native-event fidelity.** Strongest newly audited Claude event graph, but not byte-native, cross-user, or outcome-linked. |
| [cfahlgren Codex @ `87dcc5b0`](https://huggingface.co/datasets/cfahlgren1/codex-sessions/tree/87dcc5b0df77f94b8750772dce7078866d3e6877), Hub license `other` / `NOASSERTION` | Two untouched Codex rollouts, 130 records, and two derived rows that are byte-equal to the raw files. | **Admit for byte-native parser fidelity only.** Too small for longitudinal inference; no redistribution or training-right claim. |
| [Mike Codex @ `29b52c15`](https://huggingface.co/datasets/Mike0021/codex-sessions/tree/29b52c15654087c5c5d0adcd062bfe40f6464d6b), `NOASSERTION` | 27 sanitized files and 12,316 observed records versus 11,884 declared; 49 session metadata rows, 32 distinct IDs, and no call IDs. Aggregate scan found six unvalidated JWT-shaped candidates. | **Quarantine for schema control.** It is a normalized autonomous-session derivative, not a real-user cohort; count mismatch and secret candidates require review. |
| [Ranga coding sessions @ `9745612d`](https://huggingface.co/datasets/RangaPrasath/coding-sessions/tree/9745612dbb84733bd9da15544e7ca8cebaa82c2a), MIT | 73 Codex rows/22,528 messages plus six OpenCode rows/348 messages. The Codex rows contain 64 unique IDs and nine duplicates. Tool messages retain 7,439 exact joins but lose native topology and usage. | **Admit as a flattened Codex negative control.** Originates from real harness storage but cannot validate native ingestion. |
| [Peter DataClaw mirror @ `96e52d19`](https://huggingface.co/datasets/Edmon02/dataclaw-peteromallet/tree/96e52d19e236676f323cc41916daab006a6ac2e2), MIT | 549 rows, 503 unique session IDs, 14 projects, 169,168 messages, 41,873 thinking records, and 80,409 tool inputs; no tool outputs or native IDs. The card points loaders to Peter's source. | **Admit for longitudinal flattened retrieval only.** Deduplicate 46 repeated rows and treat as a mirror, not an additional user. |
| [Jobseek traces @ `5aae9972`](https://huggingface.co/datasets/viktor-shcherb/jobseek-agent-traces/tree/5aae997225724606da9f7d23ada9cd49e81ff177), MIT plus `not-for-AI-training` | Deterministic eight-workflow sample: 1,851 records, 579 calls, 577 exact results, and merged main/subagent topology. Full corpus is approximately 5.155 GB of repetitive job-monitor workflows. | **Admit sample for merged-workflow reconstruction only.** Not a user/population cohort and not a training source. |

The [source-pinned landscape correction](hugging-face-native-agent-history-landscape-2026.md)
records the native/derived taxonomy and deduplication rules.

## The complete-directory question

No admissible candidate contains an entire real user's `~/.claude` or `~/.codex` directory.

The closest cases are:

- The pinned `jkim0731/2p-hcr-autoreg` `.claude` tree contains 2,067
  files/76.4 MB across history, one project transcript, file history, plugins,
  tasks, shell snapshots, plans, agents, settings, backups, jobs, paste cache,
  session metadata, and auth-adjacent state. It is a genuine near-complete
  state dump, but not a literal complete home and not safe for undifferentiated
  ingestion.
- Glint publishes `claude/projects`, `claude/history.jsonl`, `claude/cache`, and
  `claude/paste-cache`, but not the other global home areas.
- Wisp mirrors only `~/.claude/projects/`, including session and subagent JSONL.
- share-codex scans `~/.claude/projects` and `~/.codex/sessions`, then emits normalized, filtered rows.
- DataClaw reads harness session stores and emits normalized conversation shards.
- SWE-chat releases public repository checkpoints, transcripts, `context.md`, and Entire metadata—not a user's harness home.
- Trace Commons preserves donated raw session files—not user settings, skills, or account state.

A complete harness home would likely include material the study should deliberately **not** ingest:

- authentication/account data, tokens, provider state, and cached secrets;
- user-level settings, permission decisions, hook configuration, and MCP server credentials;
- unrelated project names, local paths, shell history, and third-party personal data;
- global memories and instructions that may contain confidential corporate facts;
- caches and transient files with unclear retention or deletion semantics.

The correct enterprise analogue is not “copy the whole folder.” It is an explicit, typed export with independent consent and policy classes:

1. native session events;
2. tool proposals, authorization decisions, executions, results, and state changes;
3. project and repository identifiers;
4. versioned skills/instructions/memory references by content hash;
5. outcome evidence such as tests, CI, review, or user feedback;
6. authority epoch, purpose, classification, subject/team scope, retention, and deletion state.

Credentials and opaque caches are exclusions, not missing research features.

## What the public sources let Frankengate test

| Original enterprise question | Public-source experiment | What can be concluded | What remains unproven |
|---|---|---|---|
| Where does one user repeatedly struggle and eventually recover? | Build temporal episodes from share-codex, Peter, Claudeset, and Wisp. Detect loops, rephrasing, repeated errors, tool failures, test failures, and later contrasting successful actions. | Whether detectors recover review-worthy repeated friction and whether a later trace provides a plausible repair. | That the person lacked a skill, that the later answer was correct, or that Frankengate caused improvement. |
| Which users are doing similar work? | On SWE-chat, group by observed repository/task/file/diff semantics and compare lexical, structured, and embedding retrieval. Use TraceLab as a content-stripped negative control. | Whether the system retrieves human-judged similar work while respecting user/project/time splits. | That users should talk, that similarity implies expertise, or that collaboration will help. |
| What cloud or domain skills are missing? | Map trace evidence to a versioned capability taxonomy, then ask experts to label evidence-backed candidate gaps and abstentions. | Precision and calibration of **candidate** capability suggestions. | True competence, readiness, or missing skills. No reviewed corpus supplies a gold enterprise skill label. |
| Can a successful peer trace help another user? | Retrieve prior contrasting episodes from a different user, replay the suggested procedure in an isolated task, and compare to no-retrieval and same-user controls. | Prospective uplift on a bounded task with an independent outcome. | General productivity or organizational value without a real controlled intervention. |
| What should become an eval? | Promote repeated failure/repair patterns into assertions; evaluate future held-out episodes or sandbox replays. | Whether proposed evals predict or catch recurrence without excessive false positives. | That an assertion is causal or broadly representative of the enterprise. |
| What should become `MEMORY.md` or harness memory? | Extract typed fact/procedure candidates from earlier sessions, require provenance and review, then evaluate retrieval on later sessions. | Future-query usefulness, contradiction rate, staleness, and reviewer acceptance. | Permission to auto-write live memory. Public data should not normalize autonomous memory mutation. |
| Who should talk to whom? | Compute privacy-safe artifact/topic overlap, then test a reciprocal opt-in introduction workflow. | Introduction acceptance and subsequent bounded outcome, if run prospectively. | A named recommendation from trace similarity alone. This should be refused without consent and purpose controls. |
| Should an embedding model be fine-tuned? | Create weak positives from continuations, same resolved task, same checkpoint, and accepted memory/eval pairs; hard negatives from same language/repo but different task. Compare to exact/FTS/structured baselines under user-and-time splits. | Whether a domain adapter improves retrieval on human-labeled enterprise-like questions. | That public OSS coding semantics transfer to confidential enterprise work without enterprise labels. |

## Study design that directly answers the enterprise questions

### Cohorts

Keep each cohort separate so “real user,” “cross user,” and “verified outcome” never collapse into one label.

| Cohort | Sources | Purpose |
|---|---|---|
| U1: deep longitudinal individual | share-codex | Primary repeated-friction, recurrence, memory, and eval-candidate study |
| U2: independent individual | Peter DataClaw | Replicate U1 with different models, projects, and collection path |
| U3: compact-aware individual | Claudeset community | Test context compaction, lost context, and memory candidates |
| U4: native branching/subagents | Wisp restricted subset | Test parent/child reconstruction and delegation failure modes |
| X1: semantic cross-user | SWE-chat after gated authorization | Similar work, cross-user transfer, checkpoint/diff and attribution analyses |
| X2: privacy-reduced cross-user | TraceLab | Determine what can be learned from metadata/signals without semantic content |
| E1: explicit-donation parser set | Trace Commons | Native format conformance and consent-oriented ingestion |
| B1: synthetic/benchmark traces | Existing CMU, MATM, and task benchmarks | Independent ground-truth outcome controls, never mixed with human-behavior claims |

### Sequential systems

Every system must be evaluated against the same frozen episode splits:

1. **S0 — metadata only:** time, model, project, event count, tool name, error/exit status.
2. **S1 — deterministic signals:** loops, rephrasing, stagnation, retries, tool failures, abandonment, and delayed recovery.
3. **S2 — exact/structured/FTS retrieval:** identifiers, files, commands, errors, project, task terms, and event structure.
4. **S3 — semantic retrieval:** generic embedding and reranker, added only after S2 establishes a measured gap.
5. **S4 — temporal episode reconstruction:** same task across sessions, failed attempts, repair, outcome, and uncertainty.
6. **S5 — contrastive diagnosis:** compare failed and successful episodes without treating a successful trace as a universal procedure.
7. **S6 — memory/eval/skill candidates:** typed, evidence-backed, versioned candidates with abstention.
8. **S7 — cross-user transfer:** retrieve a peer artifact or procedure under purpose, privacy, and opt-in constraints.
9. **S8 — prospective intervention:** measure actual later outcome. No “employee improvement” claim is allowed before this stage.

### Required splits and controls

- Split by **user**, then project, then time. Random trace splitting leaks a user's repeated work into both train and test.
- Deduplicate DataClaw forks and repeated exports by native session ID plus normalized content hash.
- Hold later sessions out chronologically for memory and learning claims.
- Separate human-driven sessions from autonomous benchmark/exec/subagent sessions.
- Treat unknown project licenses and best-effort redaction as admission risk, not as benign missing metadata.
- Use TraceLab as a test of whether cheap metadata signals alone explain apparent gains.
- Use lexical/structured retrieval as a hard baseline before claiming embeddings are necessary.
- Require independent outcomes: tests/CI/replay or human review. LLM `session_success`, assistant self-report, commit existence, and number of changed lines are not sufficient.
- Bootstrap by user and task episode rather than by event row.

### Metrics

| Question | Primary metrics |
|---|---|
| Episode reconstruction | episode precision/recall, cross-session link accuracy, temporal leakage audit |
| Friction detection | AUPRC at a fixed review budget, lead time, false escalation rate, user-stratified calibration |
| Same-task retrieval | human-labeled nDCG/Recall@k, exact-identifier preservation, user/project leakage |
| Recovery mining | precision of failed→repair→independent-outcome chains; abstention coverage |
| Memory proposal | reviewer acceptance, later retrieval usefulness, contradiction/staleness rate, deletion propagation |
| Eval proposal | future recurrence detection, false-positive rate, mutation sensitivity, replay reproducibility |
| Skill suggestion | expert-verified evidence precision, abstention rate, prospective task uplift |
| Cross-user transfer | outcome uplift versus no retrieval and same-user retrieval, privacy violations, opt-in acceptance |
| Privacy | residual secret/PII rate, source-license coverage, cohort-size disclosure checks, deletion latency |

## Admission and handling controls

Public does not mean safe to copy into a normal source repository. Use the following controls:

1. Pin the exact dataset revision and record the upstream file hashes.
2. Store raw trace content outside Git in an encrypted, access-controlled research location.
3. Run secret, PII, internal-hostname, and license/provenance scanners before any content is indexed.
4. Store only governed canonical events and derived artifact references in the Frankengate research database.
5. Tag every event with source, dataset revision, user/pseudonym, project, observed/derived status, license status, purpose, and retention/deletion state.
6. Do not attempt reidentification or enrich pseudonyms with external personal data.
7. Do not quote or publish raw user/tool content in reports. Release aggregates and synthetic examples.
8. Keep user-level analyses private to that user. Team/enterprise views should prefer reviewed derived artifacts over raw traces.
9. Support source takedown and derived-artifact invalidation.
10. Require a human review gate before a memory, skill, eval, or collaboration suggestion becomes active.

## Immediate empirical program

The next experiments can run without pretending the public data is an enterprise:

1. **Single-user temporal benchmark:** ingest the 4,333 share-codex sessions and 1,297 Peter sessions into separate governed tenants. Compare S0–S6 on repeated-friction and later-recovery episode retrieval.
2. **Compact-memory benchmark:** run the 114 Claudeset sessions with and without compact events to measure whether proposed memory items restore later-needed facts without increasing contradiction.
3. **Structural fidelity benchmark:** ingest Wisp's 61 root sessions and 43 subagent/workflow files only after a secondary safety scan; measure parent/child, branch, tool proposal/result, and delegation reconstruction.
4. **Cross-user outcome benchmark:** after authorized gated access, ingest SWE-chat sessions, checkpoints, commits, and diffs. Create human-reviewed same-task and failed→repair labels; compare S1, S2, S3, and S5.
5. **Content-ablation benchmark:** run the same operational questions on TraceLab. This quantifies which findings survive without raw semantic content and protects against overclaiming embedding value.
6. **Prospective enterprise pilot:** use public results only to freeze detectors and candidate-generation logic. Evaluate real usefulness, skill suggestions, and introductions only on consenting Frankengate users with current authorization and independent outcomes.

## Bottom line

We did find real users' coding-agent histories that are substantially richer than standard benchmark trajectories. The most valuable combination is:

- share-codex + Peter + Claudeset for deep individual temporal patterns;
- SWE-chat for cross-user and code-outcome structure;
- TraceLab as a privacy-reduced control;
- Wisp + Trace Commons for native format, branches, subagents, and ingestion fidelity.

We verified one genuine near-complete public Claude home-state tree, a
substantial partial Claude home, thousands of native Claude/Codex JSONL files,
and multiple rich native or portable session archives. We did **not** verify a
literal complete global `~/.claude` or `~/.codex` home.

Frankengate should accept near/partial homes and native archives through strict
path and policy lanes, emit an area-by-area completeness receipt, and collect a
typed governed evidence export that includes the research-critical semantics
while explicitly excluding credentials, `.codex/auth*`, MCP auth/cache,
unrelated caches, shell configuration, and opaque account state.

The public corpora can establish that the machinery finds repeated friction, related work, repair candidates, memory candidates, and eval candidates. Only a consented prospective enterprise pilot can establish that these suggestions improve users or work across users.

## Primary sources

- [SWE-chat dataset @ `f66cca95`](https://huggingface.co/datasets/SALT-NLP/SWE-chat/tree/f66cca95b14caaa4177f7ed5eaa424608dadcffa)
- [SWE-chat paper, arXiv:2604.20779](https://arxiv.org/abs/2604.20779)
- [TraceLab source and v0.0.1 release @ `fc061574`](https://github.com/uw-syfi/TraceLab/tree/fc061574a0f9700ccf88be33112adc8e86b425fa)
- [TraceLab Hugging Face mirror @ `5c6ff6c8`](https://huggingface.co/datasets/dharshanrai/tracelab-syfi-coding-trace/tree/5c6ff6c8ba22fd80c746dc06ea5c960b959249b7)
- [share-codex dataset @ `3d8b1397`](https://huggingface.co/datasets/nmuendler/share-codex/tree/3d8b1397c72dbfbf8b04f518064e2c99dde84ca0)
- [Peter O'Malley DataClaw history @ `8c954338`](https://huggingface.co/datasets/peteromallet/my-personal-codex-data/tree/8c9543389161e80628dcb183b30f8c6be04f627a)
- [Claudeset community @ `fe11da9a`](https://huggingface.co/datasets/lelouch0110/claudeset-community/tree/fe11da9ac006d5592378a3d284ee2ed81ffb7578)
- [Wisp Claude Code sessions @ `c2c90b59`](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce)
- [Glint/Fable partial Claude home @ `e05c4178`](https://huggingface.co/datasets/Glint-Research/Fable-5-traces/tree/e05c417852fc59fd8da758e68b352732423ca0cb/claude)
- [jkim0731 near-complete Claude home state @ `b5a4615c`](https://github.com/jkim0731/2p-hcr-autocoreg/tree/b5a4615cdb0ffad81650a9c72a54209a202f6337/.claude)
- [NguyenDoCong native Claude project/session tree @ `2c90073c`](https://github.com/NguyenDoCong/bidding/tree/2c90073c8fe98e6c0db4c51e5ee2c47012025f1d/.claude/projects)
- [wjmlong validated Codex Desktop bundles @ `1eceee07`](https://github.com/wjmlong/Codex_Sessions/tree/1eceee0784f155e6cb994210cfc7b02cbc458298)
- [MaxDevv real Pi multi-source corpus @ `8c593252`](https://huggingface.co/datasets/MaxDevv/real-pi-coding-agent-traces-sessions/tree/8c593252ddad7dca08a0afc07896195fa73f2d6e)
- [Trace Commons @ `112ebd4d`](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf)
- [Michaelwaves personal history @ `2ac84737`](https://huggingface.co/datasets/michaelwaves/my-personal-codex-data/tree/2ac84737812defdc1b3a8482c4897205534ab327)
- [DataClaw 0.2.1 privacy and schema documentation](https://pypi.org/project/dataclaw/0.2.1/)
