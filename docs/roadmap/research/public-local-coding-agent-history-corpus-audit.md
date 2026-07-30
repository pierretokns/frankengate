# Public local coding-agent history corpus audit

**Date:** 2026-07-30
**Question:** Are complete, real-user Claude Code, Codex, Cursor, Cline, Aider, or
similar local histories publicly available and suitable for Frankengate's
enterprise trace-intelligence study?

## Executive finding

We found real public coding-agent histories, but not a paper-ready corpus of
consenting users' complete `~/.claude`, `~/.codex`, Cursor, or equivalent
working directories.

The useful sources divide into four materially different classes:

1. **Local importers and search tools** such as `claude-history`, CASS, and the
   AI data-extraction toolkit read a user's own private files. Their public
   repositories contain code and synthetic fixtures, not their users' histories.
2. **Conformance fixtures** such as AgentLogs' Claude Code, Codex, Cline,
   OpenCode, and Pi recordings are complete enough to exercise parsers and tool
   events, but are short scripted development tasks rather than natural user
   work.
3. **Intentionally repository-local histories** such as SpecStory's own seven
   top-level `.specstory/history/*.md` files are genuine examples. They are
   lossy Markdown projections and not complete harness directories.
4. **A large, unusually valuable public checkpoint collection** exists in
   `entireio/cli-checkpoints`: at the pinned revision it contains 6,926
   `full.jsonl` files, 810 normalized `transcript.jsonl` files, 12,648 metadata
   files, and about 17.16 GB of blobs. It appears to be real sessions produced
   while developing Entire. The repository has no declared license and its own
   security documentation warns that public checkpoint branches expose prompts,
   responses, tool calls, file contents, and MCP data. It is therefore a
   **permission-request candidate, not an admissible research corpus yet**.

Public GitHub search also finds isolated `.aider.chat.history.md`,
`.specstory/history`, `claude-session.jsonl`, and `.claude/agent-*.jsonl`
artifacts. Public visibility is not evidence of informed consent. Some are very
likely accidental. We should not mirror, train on, or publish analyses of those
files without contacting their maintainers.

The answer to “can we evaluate real people as if they were enterprise users?” is
therefore **yes, after an opt-in donation/recruitment step; not by silently
scraping exposed home-directory artifacts**.

## Evidence table

| Source, pinned revision | What it actually contains | Completeness | License/consent status | Paper use |
|---|---|---|---|---|
| [raine/claude-history v0.1.71](https://github.com/raine/claude-history/tree/24183a06e9e6c7fe6fb71bcae66d1cfa83778e5f) | Rust parser, viewer, local lexical/semantic search, and programmatic test fixtures | Reads raw `~/.claude/projects` JSONL when run by a user; repo does not bundle users' logs | MIT for software; no user corpus | Use importer and retrieval design; no natural-user observations |
| [CASS v0.6.23](https://github.com/Dicklesworthstone/coding_agent_session_search/tree/8844ba66e24d18c54ece51d06fd6fede6002a60e) | Connectors for 23 local agents, SQLite canonical store, BM25, optional local embeddings, fixtures/goldens | Can ingest raw local histories including Claude, Codex, Cursor, Aider, Hermes, and others; repository is not a user corpus | Software license has an OpenAI/Anthropic rider; no donated data license | Use connector/schema/search concepts, subject to license review; do not treat its repo as user evidence |
| [0xSero/ai-data-extraction](https://github.com/0xSero/ai-data-extraction/tree/b7520c48b2bb46d5a0d3257e80ca1a59670d5e37) | Extraction scripts for Claude, Codex, Cursor, Windsurf, Trae, Continue, Gemini, and OpenCode | Attempts complete messages, context, diffs, and tool results from the operator's machine | Repository has no license file despite a README statement; README says “YOUR OWN data,” warns of secrets/proprietary code, and says not to commit exports | Source-location cross-check only; not a corpus and not a dependable production importer without validation |
| [AgentLogs](https://github.com/agentlogs/agentlogs/tree/466af1b68c50b53752cda7584c383cccf41d94b6) | 14 recorded JSON/JSONL fixtures across Claude Code, Codex, Cline, OpenCode, and Pi; upload and team-sharing implementation | Tool-rich but small scripted CRUD/image/subagent cases; not longitudinal natural work | Functional Source License 1.1 with future Apache grant; hosted example transcript has no dataset license | Excellent parser/tool-call conformance material; unsuitable for claims about user behavior |
| [SpecStory](https://github.com/specstoryai/getspecstory/tree/c3e0a173512c597dd6cf861fbccb5ee000a39f92) | Seven top-level, apparently genuine `.specstory/history/*.md` sessions plus synthetic Lore fixtures | Markdown includes conversation/tool evidence, but is a projection rather than raw provider logs or a complete harness folder | GitHub reports Apache-2.0, but the checked-out root has no license file; publication does not establish research consent | Cite and manually analyze as product-authored examples only after confirming file license; recruit other repository owners rather than scrape |
| [Entire CLI](https://github.com/entireio/cli/tree/279b988597f1037c14cdd4c46765a5552e067d17) | Capture pipeline for prompts, responses, tool calls, touched files, token usage, commits, and checkpoint branches | Strong session/checkpoint representation across Claude, Codex, Gemini, Cursor, Pi, and others | MIT software; documentation explicitly warns that public repositories expose checkpoint content | Use schema, capture, and redaction design |
| [Entire public checkpoints](https://github.com/entireio/cli-checkpoints/tree/620170f3b452114e04bd1870a4d4dd29c1ceb65c) | 6,926 full JSONL session artifacts, 810 transcript JSONLs, 12,648 metadata files, approximately 17.16 GB | The closest source found to a large natural coding-agent trace corpus; checkpoint-level prompts, transcripts, token usage, and file links, but not whole home directories | **No repository license.** No participant statement or research consent found | Do not download or analyze content yet. Request a dataset license, provenance statement, participant authority, deletion process, and permission for aggregate publication |
| Public `.aider.chat.history.md` gists and repositories | Human/assistant edit dialogue committed or explicitly shared by individual developers | Usually one project/session; tool/environment state is partial | Varies or absent; public visibility is not research consent | Discovery and recruitment pool only |
| Public `.claude/agent-*.jsonl`, `claude-session.jsonl`, or copied `.codex` artifacts | Sometimes raw or nearly raw session records | Potentially detailed, but isolated and frequently lacks surrounding config/outcome context | Often no explicit intent to publish the trace; high risk of secrets, code, personal paths, and third-party data | Exclude unless the repository owner explicitly opts in and signs the study release |

## What each tool proves—and does not prove

### `claude-history`

The project confirms that Claude Code's local project history can be parsed into
conversation turns, tool events, working directories, titles, subagent content,
and semantic chunks. Its semantic search embeds chunks locally and combines
semantic and lexical evidence. This is directly reusable for Frankengate's
private per-user history experience.

It does **not** publish a population. The test fixtures construct conversations
in code. A study based on the repository would test retrieval software, not
human work patterns.

### CASS

CASS is the strongest connector inventory found. Its documented inputs include:

- Codex rollout JSONL under `~/.codex/sessions`;
- Claude Code session JSONL under `~/.claude/projects`;
- Cursor global/workspace SQLite stores;
- per-project and home-level Aider Markdown histories;
- Hermes state databases; and
- numerous other agent-specific JSON, JSONL, Markdown, and SQLite formats.

Its central design choice—normalized conversations/messages/snippets in SQLite
as canonical data, BM25 as the required path, and embeddings as rebuildable
optional enrichment—is highly aligned with Frankengate.

However, it is still an **operator-owned local index**, not a shared research
dataset. Its software license also includes a restrictive rider, so copying
implementation code requires separate legal review even though the conceptual
architecture can be independently implemented.

### AgentLogs

AgentLogs proves that transcript capture, commit linkage, per-member dashboards,
session sharing, and multi-agent normalization can be combined. The repository
does bundle raw-looking recordings with tool inputs/results and local file
paths. Inspection shows they are bounded fixtures—CRUD, image, todo, compact,
subagent, and all-tools scenarios—not a sample of everyday developer behavior.

These fixtures are useful for:

- provider-parser conformance;
- preserving proposal/result pairing;
- branch/subagent and image edge cases; and
- secret-redaction regression tests.

They cannot support conclusions about repeated friction, missing skills,
collaboration opportunities, or intervention effectiveness.

### SpecStory

SpecStory deliberately writes project-local Markdown into
`.specstory/history/`. Its own repository commits seven non-fixture histories,
making it the clearest small example of intentionally co-locating real
conversation evidence with source code. SpecStory's Lore also demonstrates the
“history → evidence → proposed skill → user approval” workflow.

The history projection is not equivalent to the original raw session:

- provider-native event identity and exact ordering may be normalized;
- retry, interruption, branch, authorization, and deletion events may be lost;
- the surrounding `~/.claude`, `~/.codex`, Cursor database, installed skills,
  hooks, and tool registry are absent; and
- an outcome is not independently measured merely because the source changed.

It is a useful case-study format, not the sole canonical trace.

### Entire

Entire is the closest match to a longitudinal, git-linked real-work corpus.
The CLI places checkpoint metadata on `entire/checkpoints/v1` and links prompts,
transcripts, token use, files touched, and commits. Its public checkpoint
repository is large enough to support meaningful sampling once permission and
licensing are resolved.

The same architecture exposes why “it is public” is not a sufficient admission
rule. Entire's security documentation states that anyone with repository access
can see full prompt/response history and tool interactions, including file
contents and MCP calls. Secrets receive always-on best-effort redaction, but PII
redaction is opt-in. The project recommends a private checkpoint repository for
public source repositories.

Accordingly, the public checkpoint repository should be handled as a
**responsible-disclosure-style contact opportunity**, not bulk-downloaded first
and justified later.

## Did we find complete `~/.claude` or `~/.codex` folders?

No intentionally published, licensed, consented corpus of complete home-level
harness directories was identified.

That is desirable. Those directories can include:

- raw session JSONL and deleted/archived session remnants;
- absolute paths, usernames, repository names, and personal prompts;
- configuration, hooks, MCP server definitions, and tool outputs;
- credentials, OAuth material, environment-derived secrets, and connection
  details;
- proprietary source or customer content copied into tool results; and
- memories/skills that mention people who did not consent.

Frankengate should never ask a participant to upload an unfiltered tarball of
the whole directory. It should ship an allowlist-based study exporter that
extracts only the research envelope, runs secret/PII/proprietary-path detectors,
shows a local manifest and preview, and requires an explicit final release.

## Paper-admissible study design

### Admission tiers

| Tier | Material | Permitted claims |
|---|---|---|
| A: conformance | Synthetic and scripted fixtures from AgentLogs, CASS, parser repositories, and Frankengate | Parser correctness, schema coverage, redaction, RLS, retrieval mechanics |
| B: creator-published case study | SpecStory's own histories, Entire samples, or Aider histories whose author confirms permission and license | Qualitative failure taxonomy and method demonstration; no population claims |
| C: recruited natural-work cohort | Explicitly consenting developers or teams export selected real histories plus outcomes and context | Individual friction, repeated attempts, intervention hypotheses, within-user comparisons |
| D: prospective enterprise study | Consenting employees with governance, purpose limitation, independent outcomes, and opt-out/deletion | Cross-user patterns, skill suggestions, memory/eval interventions, team-level effects |

### Required consent and provenance fields

Every admitted natural trace must carry:

- subject pseudonym and separately stored consent receipt;
- trace owner, repository owner, and employer/customer authority;
- allowed purposes: parser testing, aggregate analysis, quotation, model fitting,
  embedding training, and/or artifact release;
- provider/tool terms review and declared third-party data;
- data interval, harness/version, exporter version, and completeness statement;
- code/content release scope, classification, retention, and deletion deadline;
- whether model messages, tool outputs, paths, commit links, and memory/skills may
  be retained;
- whether the participant may be recontacted for outcome validation; and
- a revocation route that removes raw evidence and rebuilds derived artifacts.

### Minimal opt-in export package

Do not collect the entire home directory. Export:

1. selected raw session logs;
2. a sanitized manifest of harness version, enabled tools, skills, memory files,
   and configuration hashes;
3. allowed tool calls/results with code/file content replaced by content-addressed
   protected artifacts or redacted summaries;
4. git commit/diff identifiers where the repository owner permits them;
5. user-supplied task, outcome, confidence, and “did this help?” labels;
6. a local redaction report and known-missingness receipt; and
7. signed consent/purpose/retention metadata.

This preserves enough context to test enterprise questions without normalizing
surveillance or ingesting credentials.

## Direct connection to the enterprise questions

Public histories alone are sufficient only for method development. They do not
establish the truth of the original enterprise hypotheses.

| Enterprise question | What public histories can test | What a real study still needs |
|---|---|---|
| Where does one user repeatedly get stuck before succeeding? | Detector validity on ordered attempts, loops, errors, and eventual code changes | Stable pseudonymous user identity, task linkage across sessions, and independent success labels |
| Which prompt, skill, or tool would help this user? | Generate candidate interventions from contrastive traces | Prospective consented A/B or crossover evaluation; never infer competence from trace style alone |
| Who is doing similar work? | Task/topic clustering and exact-identifier retrieval | Current organizational scope, classification, role context, and reciprocal opt-in before naming or introducing people |
| What skills are missing across a team? | Create a hypothesis taxonomy from observed friction | Task requirements, expected capability rubric, manager/user validation, and protections against performance surveillance |
| What should become `MEMORY.md` or a harness skill? | Extract evidence-backed candidate facts/procedures | User review, provenance, time validity, contradiction handling, rollback, and measured downstream utility |
| Does a shared lesson improve the enterprise? | Replay candidate procedures on public benchmark tasks | Prospective real-work outcomes, contamination controls, cohort boundaries, and privacy-safe aggregate reporting |

The paper should explicitly separate:

- **description**: what events occurred;
- **hypothesis generation**: what may explain the pattern;
- **intervention**: what the system suggests or changes; and
- **causal evidence**: whether the intervention improves an independently
  measured outcome.

## Recommended next actions

1. Contact Entire before accessing transcript contents. Ask for a dataset license,
   provenance/participant statement, confirmation that the public repository is
   intentional, a deletion process, and permission to publish aggregate results.
2. Ask SpecStory whether its seven project histories are intentionally licensed
   research examples and whether it will provide raw-plus-projection pairs.
3. Invite maintainers of clearly intentional Aider/SpecStory history repositories
   into an opt-in pilot instead of scraping them.
4. Use AgentLogs and importer fixtures immediately for conformance testing.
5. Implement a Frankengate local study exporter with preview, allowlists,
   redaction, consent receipts, and derived-artifact deletion.
6. Run the first natural-work study as a small within-user cohort. Validate
   friction detection and candidate memory/eval suggestions before any
   cross-user inference.
7. Permit cross-user matching only over reviewed, scoped artifacts. Require
   reciprocal opt-in for introductions and prohibit named employee ranking.

## Reproducibility notes

The public inventory was measured from repository trees without bulk-downloading
the 17 GB checkpoint collection or inspecting unrelated people's transcript
text. At `entireio/cli-checkpoints@620170f3...`, the recursive tree contained:

- 34,925 blobs;
- 6,926 paths ending in `/full.jsonl`;
- 810 paths ending in `/transcript.jsonl`;
- 12,648 paths ending in `metadata.json`; and
- 17,158,402,743 aggregate blob bytes.

At `specstoryai/getspecstory@c3e0a173...`, the project root contained seven
top-level `.specstory/history/*.md` files; Lore's separate fixture trees were
not counted as natural histories. At `agentlogs/agentlogs@466af1b...`, there
were 14 JSON/JSONL fixture files across five agent families.

Counts are inventory evidence, not an assertion that every file represents a
distinct person, task, or independently successful outcome.

## Primary sources

- [Claude History source and README, pinned](https://github.com/raine/claude-history/tree/24183a06e9e6c7fe6fb71bcae66d1cfa83778e5f)
- [CASS source and connector inventory, pinned](https://github.com/Dicklesworthstone/coding_agent_session_search/tree/8844ba66e24d18c54ece51d06fd6fede6002a60e)
- [AI data-extraction toolkit, pinned](https://github.com/0xSero/ai-data-extraction/tree/b7520c48b2bb46d5a0d3257e80ca1a59670d5e37)
- [AgentLogs source and fixtures, pinned](https://github.com/agentlogs/agentlogs/tree/466af1b68c50b53752cda7584c383cccf41d94b6)
- [SpecStory local-history and Lore implementation, pinned](https://github.com/specstoryai/getspecstory/tree/c3e0a173512c597dd6cf861fbccb5ee000a39f92)
- [Entire CLI capture implementation, pinned](https://github.com/entireio/cli/tree/279b988597f1037c14cdd4c46765a5552e067d17)
- [Entire security and privacy documentation, pinned](https://github.com/entireio/cli/blob/279b988597f1037c14cdd4c46765a5552e067d17/docs/security-and-privacy.md)
- [Entire public checkpoint tree, pinned; content not analyzed](https://github.com/entireio/cli-checkpoints/tree/620170f3b452114e04bd1870a4d4dd29c1ceb65c)
