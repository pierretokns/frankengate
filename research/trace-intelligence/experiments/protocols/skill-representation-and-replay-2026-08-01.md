# Skill representation and changed-system replay protocol

**Status:** preregistered design; no outcome claim.

## Question

When the same successful trajectories are available, does an executable,
parameterized procedure transfer better than a prose memory, retrieval-only
memory, or no added artifact on a changed SQL/tool environment?

This isolates the representation claim suggested by SKILL-DISCO from the
separate claims about trace quality, model training, retrieval, and human
feedback.

## Arms

Every arm receives the same base model, tool budget, task prompt, schema/tool
surface, and evidence slice. Only the added artifact differs:

1. **No skill:** no artifact beyond the base prompt.
2. **Length-matched prose:** a natural-language summary with the same token
   budget as the executable artifact, but no machine-readable preconditions or
   postconditions.
3. **Retrieval memory:** top-k prior trace snippets selected by a frozen
   lexical+dense candidate generator; snippets cannot execute and carry no
   authority.
4. **Executable procedure:** a parameterized control-flow graph with explicit
   preconditions, postconditions, tool arguments, and deterministic validators.
5. **Executable + evidence packet:** arm 4 plus semantic IDs, scope, temporal
   validity, provenance, schema/tool fingerprint, and an explicit NIL/unknown
   state.

If multimodal resources are available, a sixth exploratory arm may add a
license-cleared tutorial or reference artifact, but it cannot replace arm 5
and cannot enter the primary comparison after candidate selection.

## Splits and construction

- Mine candidates only from successful source tasks.
- Hold out task families, database/tool systems, users, and time windows.
- Freeze candidate generation before opening changed-system outcomes.
- Require at least two independent labels for semantic identity and expected
  artifact; disagreements become `unclear`, not forced positives.
- Include same-surface/wrong-scope, stale-version, renamed-schema, missing-tool,
  and true-NIL tasks.
- Length-match arm 2 to the executable artifact and record tokens, tool calls,
  wall time, and model cost for every episode.

## Primary outcomes

1. Changed-system task success under an independent semantic/result oracle.
2. False semantic acceptance rate on wrong-scope, stale, renamed, and NIL cases.
3. Replay determinism and validator agreement.

Secondary outcomes are first-attempt success, repair count, tool-call count,
latency, token/currency cost, abstention precision, and negative transfer.

## Promotion rule

An artifact representation is promotion-eligible only if it improves the
pre-registered primary success outcome against both no-skill and
length-matched prose, has a confidence interval excluding zero on the paired
effect, has no release-blocking false semantic acceptance, and does not regress
cost or latency beyond the budget. A retrieval hit or valid SQL execution
alone is not sufficient.

## Required receipts

Record dataset/source hashes, candidate and split manifests, artifact hashes,
model/runtime manifests, independent verifier results, denials/abstentions,
cost/latency, and raw-to-redacted lineage. Keep raw prompts, SQL, rows, and
vectors outside the committed repository.

## Interpretation boundaries

- A positive result establishes representation utility only for the measured
  task families and changed systems.
- A null result does not disprove skill-learning papers if their environments
  include training, sequential continuity, stronger verifiers, or different
  task distributions.
- A prose or retrieval win without changed-system replay is not a reusable
  enterprise skill claim.
