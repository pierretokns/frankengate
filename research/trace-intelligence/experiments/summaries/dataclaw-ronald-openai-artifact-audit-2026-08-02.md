# DataClaw OpenAI-format artifact audit

## Cohort

The pinned `ronaldcmz/Claude-Opus-Dataclaw-Unredacted` export is a parseable
MIT-claimed OpenAI-format projection of Claude coding-agent histories. The
local file contains **436 sessions**, **46 project labels**, and **48,779 tool
calls**. Raw transcript content remains in the temporary cache and was not
sent to an external model or committed.

## Recurrence and candidate signals

| Projection | Result | Interpretation |
|---|---:|---|
| Tool-call signatures | 59 unique; 40 repeated; 37 repeated across projects | Tool name plus argument shape is a broad candidate generator, not a semantic artifact identity |
| Normalized command shapes | 4,297 unique; 622 repeated; 342 repeated across projects | Command-shape recurrence is common enough for review queues and hard-negative mining |
| Prompt lexical retrieval | 416/420 eligible queries had a positive candidate; same-project top-1 proxy rate **0.637** | User wording carries more project-local signal than generic tool signatures in this corpus |
| Tool-signature retrieval | 412/420 eligible queries had a positive candidate; same-project top-1 proxy rate **0.308** | Tool overlap alone is a poor work-equivalence proxy and is dominated by shared harness vocabulary |

The retrieval comparison uses project identity only as a **silver provenance
proxy**. A same-project top-1 result is not a same-task label, artifact
correctness, skill-gap label, or collaboration recommendation. The corpus has
no independent semantic-intent or terminal-outcome labels for these questions.

## What this adds to the program

1. **Parseability matters:** this export can support local experiments, unlike
   the malformed MRiabov export, but its OpenAI projection still needs a
   loss/field audit before treating tool outputs as authoritative.
2. **Tool names are not enough:** 37 of 59 recurring tool signatures cross
   project boundaries, and tool-signature retrieval is materially weaker than
   prompt lexical retrieval on the project proxy.
3. **Command shapes are promising review features:** 342 recurring shapes cross
   projects. They are suitable for candidate generation and hard-negative
   mining, but require parameter binding, authority, schema/tool-version
   contracts, and independent replay before reuse.
4. **The next representation test should be hybrid:** compare prompt terms,
   normalized command shapes, exact identifiers, and dense embeddings on the
   same reviewed task-equivalence set. Do not infer that a project proxy will
   transfer to enterprise work.

## Admission and next gate

Admit this corpus to **local mechanics and candidate-generation experiments**.
Do not use it to train or promote an embedding, skill, memory, alias, or
cross-user recommendation. The next fair test needs reviewed same-work/NIL
labels, temporal/project-held-out splits, and an independent artifact or task
outcome.

Receipt: [`dataclaw-ronald-openai-artifact-audit-2026-08-02.json`](../results/dataclaw-ronald-openai-artifact-audit-2026-08-02.json)

Audit implementation: [`dataclaw_openai_artifact_audit.rb`](../../dataclaw_openai_artifact_audit.rb)
