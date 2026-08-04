# Wisp longitudinal Claude Code structural pilot

**Status:** complete structural and lifecycle analysis

**Run date:** 2026-07-30

## Question

Can an intentionally published real user's Claude Code project-session tree
exercise Frankengate's longitudinal ingestion and friction/recovery primitives,
and which of the original enterprise questions can it actually support?

## Source and admission

The admitted source is
[`crispwisp/wisp-claude-code-sessions`](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions)
at revision `c2c90b59174318ab0b163ec9c9ac82bb879288ce`.
The contributor describes the corpus as real, unedited, voice-driven Claude
Code work plus nested computer-use benchmark runs. The release is MIT-licensed,
credential-scanned, and intentionally retains the contributor's public
identity.

The repository mirrors the `~/.claude/projects/` session layout. It is not a
complete `~/.claude` home: settings, plugins, credentials, and unrelated
configuration are neither required nor admitted.

Raw transcripts remain outside Git. The checked-in result contains only
structural counts, integrity hashes, and typed limitations; it emits no
prompts, reasoning, tool arguments, tool output, or event paths.

## Reproducible result

The pinned snapshot contains:

- 104 JSONL files across 8 main-user sessions, 9 benchmark-development
  sessions, 44 benchmark-task sessions, and 43 nested-subagent files;
- 10,698 valid records from 2026-06-07 through 2026-07-06;
- 4,247 assistant and 2,558 user records;
- 2,209 tool uses and 2,207 tool results;
- 103 explicit error results across 11 files;
- 84 structural recovery episodes, defined narrowly as a later non-error tool
  result following an explicit error in the same file;
- 20 parent/child branch points and 5 dangling parent references;
- 2 malformed JSONL records in one long main-user session.

`Bash` dominates the tool calls (1,417), followed by `Edit` (257), `Read`
(254), and `Write` (140). This is a real coding/system-work distribution, not
a generic enterprise task distribution.

All counts rebuild with:

```bash
python3 research/trace-intelligence/real_user_trace_pilot.py \
  /path/to/pinned/transcripts \
  --manifest research/trace-intelligence/configs/datasets/wisp-claude-code-sessions.json \
  --output research/trace-intelligence/experiments/results/wisp-longitudinal-structural-pilot-2026-07-30.json
```

## What this proves

This corpus can validate:

- native Claude Code import without flattening tool calls or parent/child
  structure;
- per-user history, project/session navigation, and exact evidence previews;
- cheap error, recovery, retry, branching, and subagent-selection detectors;
- schema-evolution and malformed-record quarantine;
- proposal generation for review-worthy traces, candidate evals, candidate
  memories, and candidate procedures;
- the distinction between a main human session, benchmark task, and nested
  agent execution.

The 103 explicit errors and 84 later non-error transitions create real
candidate friction/recovery slices. They do not establish that the user's task
succeeded, that the later action caused success, or that the user lacks a
skill. Those questions require task outcomes and environment/tool/permission
labels.

## What this does not prove

One intentionally public contributor is not an enterprise. This source cannot
identify:

- population rates, representativeness, or individual productivity;
- which people should collaborate;
- whether two users doing semantically similar work would benefit from contact;
- a causal benefit from a prompt, eval, memory, skill, embedding model, or
  fine-tune;
- whether an observed failure reflects user capability rather than environment,
  access, missing tools, model behavior, or task ambiguity.

Combining unrelated public contributors into a pseudo-enterprise would create a
false organizational relationship and an invalid cross-user estimand.

## Direct enterprise transfer

The source is admitted as the ecological middle tier:

1. benchmark traces qualify representation, retrieval, and detector mechanics;
2. this real-user corpus stress-tests those mechanics on longitudinal,
   imperfect, branched harness data;
3. consented Frankengate users prospectively validate usefulness and harm under
   real RLS, team, classification, purpose, and authorization-epoch policy.

The first Frankengate product claims supported by this pilot are deliberately
personal and proposal-only: “show my history,” “show the evidence for repeated
friction,” “suggest an eval to review,” and “draft a memory or procedure for my
approval.” Team matching, skill-gap education, and organizational intervention
remain prospective experiments with abstention and reciprocal consent.

## Decision

Admit this corpus and build its native adapter. Do not ingest entire home
directories, do not profile the named contributor, and do not call the corpus a
stand-in enterprise. Promote a finding beyond personal proposal-only scope only
after independent outcomes and a consented prospective Frankengate study.
