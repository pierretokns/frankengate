# Hugging Face native agent-history landscape and admission correction

**Reviewed:** 2026-07-30
**Status:** source-pinned discovery correction, seven-stratum fidelity audit,
and expanded home-tree/session-corpus search

## Correction

Combined Hugging Face API searches returned roughly 180 trace/session
**candidates** across overlapping queries. That number is not 180 unique
datasets, 180 users, or 180 native histories.

The search inventory mixes:

- upstream datasets and mirrors/forks of the same sessions;
- raw native JSONL, scrubbed native records, merged workflows, and flattened
  message tables;
- real user histories, autonomous agent runs, synthetic benchmarks, and
  distilled/SFT conversions;
- full repositories and viewer-generated derivatives; and
- licensed, gated, restricted-training, and `NOASSERTION` sources.

The correct unit for admission is a pinned, deduplicated corpus stratum—not a
search hit. Deduplicate by upstream identity, pinned repository revision,
native session ID, and content hash before counting users or sessions. A mirror
is not another user, and a transformed SFT table is not another trajectory.

The expanded search also corrected a second mistake: searching only dataset
cards tagged `agent-traces` misses raw home-tree subsets, personal exports,
community collectors, and repositories that commit native session files. Those
sources are real, but “many native sessions,” “one complete session bundle,”
“a partial harness home,” and “a complete global harness home” remain different
claims.

The official Hub filter itself now yields **359** agent-trace datasets when
fully paginated. That is discovery scale, not 359 users: many rows are
benchmarks, mirrors, derivatives, test fixtures, or autonomous runs.

## Native baseline

Hugging Face's
[official Agent Traces documentation](https://huggingface.co/docs/hub/en/agent-traces)
says Claude Code, Codex, and Pi Agent raw JSONL files are natively supported.
It identifies their local session directories and says the files can be
uploaded without modification. It also warns that traces may contain prompts,
tool output, paths, screenshots, secrets, private code, and personal data.

For this study:

- **byte-native** means the published bytes are the harness-written JSONL;
- **record-preserving** means event objects and links survive, even if strings
  were scrubbed or an outer envelope was added;
- **session-complete** means the publisher retained the workflow, but may have
  merged agents or flattened events;
- **longitudinal** requires a stable, nonduplicated person/project/time key
  across sessions; and
- **complete harness home** would include settings, memories, skills, caches,
  and account/configuration state in addition to sessions.

These labels are independent. A source may be session-complete but not native,
or native but too small and identity-free for longitudinal analysis.

## Source-pinned landscape

| Source | Pin and rights | What it actually contains | Native/history classification | Admission |
|---|---|---|---|---|
| [Glint-Research/Fable-5-traces](https://huggingface.co/datasets/Glint-Research/Fable-5-traces/tree/e05c417852fc59fd8da758e68b352732423ca0cb/claude) | `e05c4178`, AGPL-3.0 | A published `claude/` subtree with 129 files and 63,184,884 bytes: 115 project/session JSONL files, 36 nested subagent JSONL files, `history.jsonl` with 1,758 records, paste cache, and cache metadata | Strongest partial-home find: native project histories plus several adjacent home-state areas; still omits settings, plugins, plans, todos, credentials/account state, and other global areas | Admit as a partial-home import stratum; never call it a complete `~/.claude` home |
| [crispwisp/wisp-claude-code-sessions](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce) | `c2c90b5`, MIT | 104 credential-replaced Claude JSONL files, including 43 nested-subagent/workflow files; one public contributor plus benchmark strata | Closest project-session tree mirror; not byte-native and not a full harness home | Admit narrowly for native Claude topology and single-user mechanism validation; stratify human and benchmark files |
| [AlinCiocan/fable-5-claude-code-traces](https://huggingface.co/datasets/AlinCiocan/fable-5-claude-code-traces/tree/e33ebbca230ae258b2c28aeee9fe3429e7fbeab6) | `e33ebbca`, CC-BY-4.0 | 18 scrubbed Claude event streams, 9,497 records, exact parent and tool-call/result IDs | Record-preserving native event graph after 35,732 scrub operations | Admit for Claude event/branch/subagent/compaction fidelity; not cross-user or byte-native |
| [cfahlgren1/codex-sessions](https://huggingface.co/datasets/cfahlgren1/codex-sessions/tree/87dcc5b0df77f94b8750772dce7078866d3e6877) | `87dcc5b0`, Hub license `other`; `NOASSERTION` | Two untouched raw Codex rollouts plus two exact duplicate viewer rows | Byte-native Codex control | Admit for parser fidelity only; no redistribution/training claim and no longitudinal inference |
| [Mike0021/codex-sessions](https://huggingface.co/datasets/Mike0021/codex-sessions/tree/29b52c15654087c5c5d0adcd062bfe40f6464d6b) | `29b52c15`, no declared license; `NOASSERTION` | 27 sanitized autonomous Codex files with added schema/session/index envelope; 12,316 observed records | Record-preserving normalized derivative, not byte-native; tool IDs removed | Quarantine for schema tests; count mismatch and secret-shaped candidates require review |
| [RangaPrasath/coding-sessions](https://huggingface.co/datasets/RangaPrasath/coding-sessions/tree/9745612dbb84733bd9da15544e7ca8cebaa82c2a) | `9745612d`, MIT | 73 Codex rows plus 6 OpenCode rows in a pi-brain flattened message export; 22,876 messages | Real harness-derived flattened sessions, not native JSONL | Admit as a longitudinal/flattening negative control; deduplicate nine repeated Codex rows |
| [viktor-shcherb/jobseek-agent-traces](https://huggingface.co/datasets/viktor-shcherb/jobseek-agent-traces/tree/5aae997225724606da9f7d23ada9cd49e81ff177) | `5aae9972`, MIT plus `not-for-AI-training` tag | Approximately 5.155 GB of complete job-monitor workflows; deterministic audit sample has 8 traces and 1,851 records | Complete workflow derivative with headers and merged main/subagents | Admit the sample for merge/reconstruction fidelity; no training, user, or population claim |
| [Edmon02/dataclaw-peteromallet](https://huggingface.co/datasets/Edmon02/dataclaw-peteromallet/tree/96e52d19e236676f323cc41916daab006a6ac2e2) | `96e52d19`, MIT | 549 flattened Claude conversations over 14 projects; 169,168 messages, thinking, and tool inputs, but no tool outputs | Longitudinal flattened mirror; card points to Peter O'Malley's source | Admit for longitudinal retrieval only; deduplicate 46 repeated session rows and never count as an independent user |
| [SALT-NLP/SWE-chat](https://huggingface.co/datasets/SALT-NLP/SWE-chat/tree/f66cca95b14caaa4177f7ed5eaa424608dadcffa) | `f66cca95`, ODC-BY, gated | 5,851 real sessions, 205 public repos, cross-user commit attribution, tools, checkpoints, commits, diffs, and model annotations | Strongest cross-user, outcome-linked candidate; not a harness-home export | Admit only after gated authorization, ethics/privacy review, and separation of observed evidence from model labels |
| [randomanon000/coding-sessions](https://huggingface.co/datasets/randomanon000/coding-sessions/tree/b88601e0410959b14f201e3e00709a155394d701) | `b88601e0`, `NOASSERTION` | 210,679,428-byte Pi-Brain export of one publisher's real Codex work, with JSONL and Parquet derivatives plus a manifest | Large personal longitudinal derivative, not a native Codex home | Admit after native-versus-export loss audit; do not claim redistribution or training rights |
| [cfahlgren1/agent-sessions-list](https://huggingface.co/datasets/cfahlgren1/agent-sessions-list/tree/e40be427ffb9b8a3ef31a7cb22952e4722eaf1a0) | `e40be427`, `NOASSERTION` | Small real-session sampler: two Claude, three Codex, three Pi, one Hermes export, and one Factory/Droid trace | Valuable multi-harness native/schema control, not longitudinal and not a home | Admit for importer breadth and tool-schema fidelity |
| [moikapy/0xKobolds](https://huggingface.co/datasets/moikapy/0xKobolds/tree/50d5828c62757953a90a25328ad2450f646fc987) | `50d5828c`, MIT | Twenty staged real Pi sessions plus a manifest, 12,116,212 bytes | Native/session collection from one publisher, not a Pi home | Admit for Pi adapter and longitudinal mechanism validation |
| [lelouch0110/claudeset-community](https://huggingface.co/datasets/lelouch0110/claudeset-community/tree/fe11da9ac006d5592378a3d284ee2ed81ffb7578) | `fe11da9a`, MIT | A 29,554,738-byte community shard of redacted real Claude Code sessions with full tool calls/outputs, thinking, compactions, project, branch, usage, and hashed contributor | Consent-oriented normalized full-session corpus; not byte-native and not home state | High-priority multi-user ecological stratum after verifying contributor count, redaction, and split leakage |
| [MaxDevv/real-pi-coding-agent-traces-sessions](https://huggingface.co/datasets/MaxDevv/real-pi-coding-agent-traces-sessions/tree/8c593252ddad7dca08a0afc07896195fa73f2d6e) | `8c593252`, per-source license manifest | 1,291 real human Pi sessions from 21 independently published sources, 87 MB, with tool calls/results and thinking | Best independently sourced multi-user Pi corpus found | Admit by per-source license/provenance strata; do not flatten 21 publishers into one source |
| [zhiyaowang/dataclaw-zhiyaowang](https://huggingface.co/datasets/zhiyaowang/dataclaw-zhiyaowang/tree/f5157333cbc22489661122a9bc5347b137144900) | `f5157333`, MIT | 1,013 real sessions/77 projects/7.19 GB across Claude, Codex, Cursor, Gemini, and OpenCode with full tool outputs in the newer DataClaw schema | Large cross-harness longitudinal transformed export | Admit as a transformed ecological arm with schema-version loss receipts |
| [semianalysisai/cc-traces-weka-062126](https://huggingface.co/datasets/semianalysisai/cc-traces-weka-062126/tree/23f152f6f0f9399a85901b89a6458def0ef16729) | `23f152f6`, Apache-2.0 | 393 enterprise proxy traces, 56,798 main turns, 1,697 subagent groups, 42,029 subagent inner requests, and 98,827 total model requests | Best enterprise/proxy workload, cache, latency, and subagent-shape corpus; request-level, not full semantic native histories | Admit for capacity/cache/subagent analysis and as an enterprise-shape transfer arm, not for skill or memory-content claims |

### Card-only corpus that is not currently usable

The [Zen Agentic Dataset](https://huggingface.co/datasets/zenlm/zen-agentic-dataset)
card claims 5,212,393 unique entries, 2,573,471 Claude Code entries, about
12 billion tokens, 408 source JSONL files, and about 10 GB of compressed
shards. At pinned revision `cdc75caa`, however, the Hub API reports exactly
eight documentation/configuration files, zero payload files, zero used storage,
one branch, and no converted data. Its commit history contains documentation
and statistics changes but no retrievable corpus commit. It is therefore a
lead to follow up with the publisher, not an empirical dataset. Corpus claims
must be proven by immutable payload objects, not accepted from a large dataset
card.

## GitHub home-tree and native-archive expansion

The user was correct that repository search surfaces material missed by the
initial Hugging Face-only audit.

Authenticated GitHub path search returned 1,364 indexed
`.claude/projects/**/*.jsonl` matches and 320 indexed
`.codex/sessions/**/*.jsonl` matches. Tree enumeration found far more files
than code search indexed: the top twelve inspected Claude repositories contain
2,362 native JSONL files totaling 2,567,303,953 bytes, while the top ten
inspected Codex repositories contain 329 native rollout files totaling
280,394,087 bytes. Representative blobs retained native parent/session
relationships and matched tool call/result pairs. These are sufficient for a
substantial native-history research arm even before SWE-chat, TraceLab,
DataClaw, or the Hugging Face community corpora are added.

| Source | Verified contents | Classification and use |
|---|---|---|
| [jkim0731/2p-hcr-autocoreg `.claude/`](https://github.com/jkim0731/2p-hcr-autocoreg/tree/b5a4615cdb0ffad81650a9c72a54209a202f6337/.claude) @ `b5a4615c`, `NOASSERTION` | 2,067 blobs/76,385,165 bytes: `history.jsonl` plus two backups, one native project transcript, 1,477 file-history versions, 397 plugin files, 98 tasks, 43 shell snapshots, plans, agents, settings, backups, jobs, paste cache, session metadata, and auth-adjacent state. Missing observed areas include debug, session-env, todos, and skills. | First verified **near-complete public Claude home-state tree**. High-risk and apparently unredacted. Admit the manifest as a threat-model/completeness fixture; trace and context lanes require separate quarantine/authorization. Settings, MCP/auth cache, tokens, credentials, and daemon/account state are excluded from training and normal analysis. |
| [wjmlong/Codex_Sessions](https://github.com/wjmlong/Codex_Sessions/tree/1eceee0784f155e6cb994210cfc7b02cbc458298) @ `1eceee07`, `NOASSERTION` | 33 validated real-device Codex Desktop bundles, 33 native rollouts, 77,101,303 bytes, 24,086 records, 4,252 calls/4,251 outputs, compactions, world state, turn context, web/tool-search and nested-subagent metadata. | Best operational Codex archive. Quarantine first; aggregate scan found unvalidated token-shaped strings. Session archive, not a complete Codex home. |
| [byesngmin/KGA-codex-sessions](https://github.com/byesngmin/KGA-codex-sessions/tree/fe6ce9d6287c48adce3714e47dc561bf4887dde8) @ `fe6ce9d6`, `NOASSERTION` | 37 native Codex rollouts, 44,107,278 bytes, 17,663 records, 2,724 calls/2,722 outputs, MCP, collaboration, web, compaction, and turn-context events. | Strong conditional replication corpus with weaker provenance and token-shaped candidates; session-only. |
| [jimmc414/cctrace](https://github.com/jimmc414/cctrace/tree/4b4d4add0bb3a65359ccf50501c6792e2fc13ba5/.claude-sessions/phase0-investigation) @ `4b4d4add`, MIT | One portable native Claude session: 536 records, 152 tool uses/151 results, 13 file-history snapshots, todos, plan, project configuration, manifest, native threading, and signed-thinking/tool IDs. | Best verified portable Claude session bundle and import/reference format. It is resumable session state, not the user's global home. |
| [NguyenDoCong/bidding](https://github.com/NguyenDoCong/bidding/tree/2c90073c8fe98e6c0db4c51e5ee2c47012025f1d/.claude/projects) @ `2c90073c`, `NOASSERTION` | 1,011 native Claude JSONL files/1,031,877,715 bytes: 177 top-level sessions plus 834 nested `agent-*` files. | Largest inspected native Claude session/subagent tree. Quarantine content and deduplicate agents before longitudinal counts. |
| [bbuchsbaum/brainflow2](https://github.com/bbuchsbaum/brainflow2/tree/1a8ca2e96b3fff1babad9345335aa89c05bae67f/.claude/projects) @ `1a8ca2e9`, `NOASSERTION` | 442 top-level native Claude sessions/998,165,678 bytes. | Second large native Claude replication source. |
| [swcstudiospace/supercompute](https://github.com/swcstudiospace/supercompute/tree/04c49ed8c907f7e5848286f9685cdba532e7fd44/.claude/projects) @ `04c49ed8`, AGPL-3.0 | 223 native Claude sessions/310,261,194 bytes. | Strong licensed native-history stratum. |
| [gc-papa/dotfiles](https://github.com/gc-papa/dotfiles/tree/734df95d469dd3558e89a5abeecc3667335df541/.codex/sessions) @ `734df95d`, `NOASSERTION` | 76 native Codex rollouts/172,711,117 bytes; representative file had 84/84 call/result joins. | Largest inspected Codex session tree, but repository also demonstrates why `.codex/auth*` must be denied by path. |

Several literal `.claude` repositories contain only settings, skills, commands,
or plugins. Several “claude sessions” repositories are explicit fixtures.
Those are useful config/parser tests but must not be counted as real-user
trajectories. Corpus scarcity is no longer a defensible concern; the remaining
problem is governed admission, deduplication, outcome linkage, and correctly
separating top-level human sessions from subagents, autonomous workflows,
fixtures, mirrors, and transformations.

Other valuable sources already in the admission ledger—share-codex, Peter's
original personal history, Claudeset, TraceLab, and Trace Commons—remain
separate strata. Mirrors of those sources must not inflate user counts.

## Native versus transformed SFT

Processed Fable, DataClaw, ShareGPT, instruction, and SFT releases can be useful
for language-model training research. They do not validate native ingestion
unless they retain:

- every ordered event and its original type;
- tool proposal/call/result IDs;
- parent, branch, subagent, retry, and compaction links;
- timestamps, model, usage, project, and permission metadata;
- malformed/missing records rather than silently repairing them; and
- a machine-readable loss receipt for every omitted or synthesized field.

A row containing `messages` and `tools` may reconstruct a plausible chat while
still losing the decisive evidence for diagnosis. Conversely, raw JSONL may
retain encrypted reasoning or opaque provider state that is operationally
faithful but unusable for semantic analysis.

## Empirical audit result

The aggregate-only implementation and result are:

- [`public_native_history_fidelity.py`](../../../research/trace-intelligence/public_native_history_fidelity.py)
- [`public-native-history-fidelity-2026-07-30.json`](../../../research/trace-intelligence/experiments/results/public-native-history-fidelity-2026-07-30.json)
- [academic summary](../../../research/trace-intelligence/experiments/summaries/public-native-history-fidelity-2026-07-30.md)

The study emits no raw text, identifiers, or paths. It found that exact
call-result correlation ranges from complete in Alin and cfahlgren, to nearly
complete after flattening in Ranga and Jobseek, to impossible in Mike and
DataClaw. Only Alin, Wisp, and Jobseek retain meaningful parent/subagent
structure, and Jobseek's original agent file boundaries are already merged.

## Admission consequences

1. Report search-hit counts only as discovery recall.
2. Maintain source/upstream/content-hash deduplication before counting sessions
   or users.
3. Preserve `NOASSERTION` sources for authorized inspection instead of
   pretending that public means licensed.
4. Never count autonomous workflows, benchmark runs, forks, or mirrors as
   independent employees.
5. Run native and flattened sources as separate experimental arms. Their
   disagreement measures information loss.
6. Keep raw histories outside Git and publish aggregate results and synthetic
   fixtures only.
7. Do not train on Jobseek, `NOASSERTION` sources, or embedded third-party
   content without an affirmative rights decision.
8. Use gated SWE-chat—not unrelated public publishers—for the first
   cross-user/outcome-linked study.

## Bottom line

Real and session-rich coding-agent histories are not scarce on Hugging Face.
The expanded audit found byte-native sessions, longitudinal personal exports,
multi-harness samplers, a community-contributed full-session corpus, and a
partial native Claude home tree. The broad search count is still inflated by
mirrors, synthetic traces, transformed SFT, and autonomous workflows, so
source/upstream/session/content deduplication remains mandatory.

We verified one genuine near-complete public `.claude` home-state tree. It is
missing several observed areas, retains only one project transcript, has no
declared license, and includes sensitive/auth-adjacent state, so “near-complete”
does not mean “safe to ingest wholesale.” We did not verify an equivalent
complete `.codex` home containing sessions, archives, history/index, config,
rules/skills, and state together.

Frankengate should support governed imports of near/partial homes, native
session collections, and portable bundles. It must emit an area-by-area
completeness and policy receipt rather than treating “whole home” as a Boolean
or copying credentials/account state. Trace events, versioned context/policy,
and excluded unsafe state are three separate import lanes.
