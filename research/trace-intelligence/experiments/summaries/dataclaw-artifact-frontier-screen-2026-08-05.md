# Frontier screen of recurring DataClaw artifacts (2026-08-05)

Eight recurring normalized tool-input candidates from the multi-harness
DataClaw sample were shown to `gpt-5.6-luna` through the Codex harness. Each
candidate was reviewed twice with a strict JSON schema. Prompts were bounded
and credential-scrubbed; raw examples and model reasons remain outside the
repository.

## Results

| measure | value |
|---|---:|
| candidates screened | 8 |
| frontier calls | 16/16 valid |
| repeat agreement | 5/8 candidates |
| labels: reusable procedure | 7 |
| labels: context-specific | 6 |
| labels: unsafe or sensitive | 2 |
| labels: insufficient evidence | 1 |
| mean call latency | ~8.9 seconds |

Coverage-conditioned labels were more informative than frequency alone:

- The two candidates spanning multiple project labels produced two reusable
  and two unsafe judgments. Cross-project recurrence therefore does not imply
  safe portability.
- Single-project candidates produced six context-specific, five reusable, and
  one insufficient-evidence judgments.
- Three candidates changed label across repeated reviews. The model is useful
  for generating a review queue, but not stable enough for autonomous release.

## Interpretation

This is the first empirical comparison in the program where deterministic
recurrence and frontier semantic review are applied to the same real,
multi-harness trace candidates. The result supports a layered pipeline:

1. deterministic recurrence and error/recovery signals select candidates;
2. scope, project, model, and provenance metadata constrain the candidate;
3. a frontier model proposes a reusable/context-specific/unsafe label;
4. a human and governed replay must validate correctness, safety, and changed
   system behavior before release.

It does **not** establish task correctness, productivity benefit, skill
transfer, or safety certification. A repeated command may be consistently
wrong, destructive, or harmless only in its original environment.

Receipt: [`dataclaw-artifact-frontier-screen-2026-08-05.json`](../results/dataclaw-artifact-frontier-screen-2026-08-05.json).
