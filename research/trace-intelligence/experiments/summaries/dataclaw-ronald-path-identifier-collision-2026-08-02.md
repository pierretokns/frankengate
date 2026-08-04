# DataClaw path-identifier collision audit

## Question

Can raw coding traces provide a useful, content-free hard-negative proxy for
corporate identifiers and aliases? In particular, do the same file/path
surfaces recur across projects while referring to different full paths?

## Dataset and method

- Dataset: `ronaldcmz/Claude-Opus-Dataclaw-Unredacted`
- Pinned revision: `918e6fb39c916d3459ef338b4c3645622b9a5126`
- Cohort: 436 sessions, 46 projects, 12,237 command-bearing tool calls
- Raw data remained in `/private/tmp`; no transcript, command, or raw path was
  emitted or committed.
- The audit extracts conservative path-like command tokens, retains only a
  lowercase basename surface and a SHA-256 digest of the normalized full path,
  and groups those by project and session.

Receipt: [dataclaw-ronald-path-identifier-collision-2026-08-02.json](../results/dataclaw-ronald-path-identifier-collision-2026-08-02.json)

## Results

| Measure | Result |
|---|---:|
| Path events | 11,122 |
| Unique basename surfaces | 2,462 |
| Unique normalized full-path digests | 4,025 |
| Basename surfaces seen in multiple projects | 281 (11.41%) |
| Basename surfaces with multiple full-path digests | 661 (26.85%) |
| Cross-project surfaces with multiple full-path digests | 245 |
| Maximum projects sharing one basename | 32 |
| Maximum full-path digests for one basename | 46 |

The cross-project collision proxy is therefore non-trivial: repeated basename
surfaces are often not a unique project identifier. The same surface can map to
multiple path digests and projects, making it a plausible source of false alias
edges or wrong-system retrievals.

## Interpretation

This is useful for the corporate trace program in three ways:

1. **Hard-negative proposal:** create candidate pairs of the same basename with
   different project/path digests, then ask reviewers or a governed resolver
   whether they are the same system, an unrelated convention, or a true alias.
2. **Identifier-aware retrieval:** retain exact surface and scoped path/project
   features alongside dense vectors; a basename match alone must not authorize a
   tool, SQL artifact, or memory edge.
3. **Embedding evaluation:** include collision pairs in training and evaluation
   so a domain adapter is rewarded for separating same-surface/different-system
   cases rather than merely clustering frequent filenames.

## Claim boundary

This does **not** establish that a collision is semantic, that two projects are
unrelated, or that any artifact is correct. Public traces lack reviewed
same-work/NIL labels and terminal task outcomes. The proxy is evidence for a
candidate-generation and labeling queue only. Promotion still requires scope,
authority, temporal validity, reviewed labels, and independent replay.

## Next experiment

Sample collision pairs stratified by project support and path-digest count;
label same-system, alias, unrelated, and NIL outcomes; then compare lexical,
dense, identifier-aware, and frontier-review cascades on a project-held-out
split. Measure alias precision, NIL refusal, wrong-system rate, and downstream
artifact replay—not just retrieval recall.

## Reproduction

```text
ruby dataclaw_path_identifier_collision_audit.rb \
  /private/tmp/ronald-dataclaw-openai.jsonl \
  experiments/results/dataclaw-ronald-path-identifier-collision-2026-08-02.json
```

