# Durable memory and skill-artifact audit

## What appears in real coding-agent histories

The 436-session parseable DataClaw export contains explicit references to
durable harness artifacts:

| Artifact family | Sessions | Mention events | Distinct argument-context hashes |
|---|---:|---:|---:|
| `CLAUDE.md` / `.claude` | 243 | 1,347 | 428 |
| `SKILL.md` / skill paths | 34 | 402 | 92 |
| `memory.md` | 13 | 61 | 19 |
| `AGENTS.md` / `.codex` | 3 | 42 | 14 |

The audit also found 373 read-like artifact references in tool calls across
102 sessions and 343 write-like references across 136 sessions. These are
content-free counts; raw paths, prompts, and file contents stay local.

## What this establishes

Durable memory and skill files are not hypothetical: users really do read and
write them in agent histories. They are therefore valid inputs to a trace-to-
artifact pipeline and should be first-class events in the canonical trajectory
DAG, with provenance linking the user request, file operation, and subsequent
tool/terminal outcome.

## What it does not establish

The marker counts do not prove that a memory is correct, that a skill was
consumed, that a file write improved a later task, or that a `.claude`/`AGENTS`
file is authoritative. The projection has no typed tool-result messages and no
independent semantic outcomes, so read/write detection remains a lifecycle
proxy.

## Design decision

Treat memory/skill references as candidate lifecycle events:

1. capture explicit read/write provenance and content hashes;
2. bind the artifact to principal, project, system, schema/tool version, and
   authority epoch;
3. support contradiction, expiry, deletion, and rollback; and
4. require independent replay or prospective user outcomes before release.

Do not mine `memory.md` or `SKILL.md` text into an embedding index or auto-share
it across users solely because it recurs.

Receipt: [`dataclaw-ronald-memory-skill-artifact-audit-2026-08-02.json`](../results/dataclaw-ronald-memory-skill-artifact-audit-2026-08-02.json)

Audit implementation: [`dataclaw_memory_skill_artifact_audit.rb`](../../dataclaw_memory_skill_artifact_audit.rb)
