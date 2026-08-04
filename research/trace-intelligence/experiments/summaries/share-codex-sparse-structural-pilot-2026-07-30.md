# share-codex sparse longitudinal structural pilot

**Status:** admitted for content-minimized structural research

**Run date:** 2026-07-30

## Decision

Use
[`nmuendler/share-codex`](https://huggingface.co/datasets/nmuendler/share-codex)
at revision `3d8b1397c72dbfbf8b04f518064e2c99dde84ca0` as the second
real-user longitudinal mechanism corpus. Do not treat its transcript text as
cleared training data, do not redistribute it, and do not infer the
contributor's skill or productivity.

The dataset repository owner intentionally published what the card describes
as local Codex and Claude agent sessions using
[`share-codex`](https://github.com/nielstron/share-codex). The dataset card
declares CC-BY-4.0. Its export manifest records final-row redaction, secret
scanning with 4,476 replacements, exclusion of internal prompts and reasoning,
and review/exclusion of 37 private working-directory prefixes.

Those controls reduce risk; they do not eliminate it. The scanner recorded
findings, and repository-license derivation reported 3,622 sessions as
`not_found` and 56 as `unknown`. Dataset-level CC-BY-4.0 cannot be assumed to
override rights in code or tool output originating in other repositories.
Accordingly, this pilot reads structure only. Raw responses stay in temporary
storage, and no prompt, assistant text, tool arguments, tool output, path,
session identifier, project identifier, or contributor identifier is checked
into Git.

## Candidate qualification

Three ungated candidates were reviewed before trace acquisition:

| Candidate | Strength | Limitation | Decision |
| --- | --- | --- | --- |
| `nmuendler/share-codex` | 4,333 local sessions over about eight months; explicit exporter redaction, secret scan, working-directory review, and removal of internal reasoning | One 437,648,974-byte shard; most embedded repository licenses unresolved | Admit a revision-verified sparse structural sample |
| `peteromallet/my-personal-codex-data` | Explicit personal publication; 1,297 sessions in 63 date shards; paths anonymized, username hashed, 62,661 redactions | Includes model thinking; privacy card does not document an equivalent final secret-scan gate; raw code/tool-output rights remain unclear | Reserve as a replication corpus; no content acquisition needed for this pilot |
| `lelouch0110/claudeset-community` | Explicit contributor push workflow, hashed contributor identity, documented secret/PII redaction, MIT card | Community mixture rather than a strong one-person longitudinal panel; includes thinking and complete tool output | Reserve for multi-contributor parser/privacy stress testing, not as the second longitudinal panel |

This is an admission decision for a particular structural experiment, not a
general declaration that every row is safe for semantic analysis.

## Sample design and integrity

The source file contains all 4,333 rows in one 437,648,974-byte JSONL object.
Downloading it would be disproportionate to the structural question. The
pilot instead requested eight blocks of 16 rows from deterministic positions
across the ordered row range: offsets 0, 617, 1,233, 1,850, 2,467, 3,084,
3,700, and 4,317.

Every response:

- reported 4,333 population rows and `partial=false`;
- carried `x-revision:
  3d8b1397c72dbfbf8b04f518064e2c99dde84ca0`;
- contained exactly the requested consecutive row indices; and
- was hashed in the checked-in result.

The 128-session sample is 2.9541% of the population and spans the card's full
timestamp range, from 2025-10-10 through 2026-06-18. It is a stratified
row-position sample with clustered blocks, not a probability sample. Counts
must not be extrapolated into population rates.

## Structural result

The sample contains:

- 128 sessions from one published corpus, covering 15 distinct project
  identities without retaining any identity value;
- 121 Codex sessions and 7 Claude sessions;
- 611 user, 8,928 assistant, and 6,239 tool messages;
- 6,272 tool-call proposals and 6,239 linked tool results;
- 6,239 exact proposal/result matches, no orphan results, and 33 unresolved
  proposals;
- 47 typed error results, concentrated in 6 sessions;
- 38 error results followed by a later non-error result in the same session;
- 34 error results followed by a later successful result from the same generic
  tool name; and
- 9 project identities with multiple sampled sessions, with a maximum of 80
  sampled sessions attached to one project identity.

Tool names are not emitted verbatim unless they belong to a small generic
allowlist. The aggregate categorizes 4,565 proposals as shell operations, 756
as file changes, 607 as interactive shell continuation, 140 as coordination,
105 as file reads, and 32 as other/custom.

## Enterprise applicability

This result strengthens four Frankengate product mechanisms:

1. **Personal history:** the same subject can have repeated sessions across
   projects and eight months, so a subject-scoped chronological view is
   meaningful beyond a single harness run.
2. **Friction candidate proposals:** exact tool proposal/result linkage and
   typed errors can select evidence without embeddings or an LLM judge.
3. **Recovery candidate proposals:** 38 error-to-later-success transitions
   provide candidates for review; 34 preserve the generic tool identity.
4. **Eval drafting:** unresolved tool proposals and error/recovery slices can
   seed deterministic lifecycle assertions before any semantic eval is added.

The result does **not** identify task success, correctness, capability,
productivity, a missing skill, or the cause of recovery. A later non-error tool
result is not a task outcome. Nor can one contributor establish who in an
enterprise should collaborate or whether a skill, prompt, model, memory, or
fine-tune helps.

For the original enterprise questions, this corpus is therefore an ecological
mechanism check between benchmark data and a consented Frankengate study:

- personal history and evidence selection are directly testable now;
- memory, eval, and skill recommendations remain proposal-only;
- skill-gap and cross-user recommendations require typed task outcomes,
  environment/access-blocker labels, consented organizational scope, and
  prospective intervention/control comparisons;
- employee ranking, inferred competence, and hidden monitoring remain
  prohibited.

## Reproduction

The analyzer and sample manifest are:

- `research/trace-intelligence/share_codex_sparse_pilot.py`
- `research/trace-intelligence/configs/datasets/share-codex-sparse.json`

Given temporary dataset-server responses and their headers:

```bash
python3 research/trace-intelligence/share_codex_sparse_pilot.py \
  /path/to/temporary/sample \
  --manifest \
    research/trace-intelligence/configs/datasets/share-codex-sparse.json \
  --output \
    research/trace-intelligence/experiments/results/share-codex-sparse-structural-pilot-2026-07-30.json
```

The analyzer fails closed if any response revision, row count, population
count, partial flag, or row index differs from the manifest.
