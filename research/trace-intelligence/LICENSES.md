# Dataset and artifact rights

This research artifact is Apache-2.0 software, as declared by the repository
root `LICENSE`. Dataset manifests and aggregate measurements do not change the
license of their source datasets. No raw third-party or enterprise trace corpus
is committed here.

| Source | Pinned manifest | Declared terms | Artifact policy |
| --- | --- | --- | --- |
| Nebius SWE-agent trajectories | `configs/datasets/nebius-swe-agent-trajectories.json` | CC-BY-4.0 | Aggregate results and source-neutral fixtures only; attribute the dataset when reusing results. |
| Wisp Claude Code sessions | `configs/datasets/wisp-claude-code-sessions.json` | MIT | Aggregate results only; raw transcripts remain in a private external cache. |
| share-codex | `configs/datasets/share-codex-sparse.json` | CC-BY-4.0 | Aggregate results only. Individual records can include embedded repository material with separate upstream rights, so the dataset declaration is not a blanket license for that material. |
| CodeTraceBench | `configs/datasets/codetracebench.json` | MIT | Aggregate results only; raw archives and Parquet files are not redistributed. |
| MATM ALFWorld population runs | `configs/datasets/matm-alfworld-population-runs.json` | Apache-2.0 | Aggregate results and schema-derived fixtures only. |
| MAST-Data | `configs/datasets/mast_data.json` | CC-BY-4.0 | Aggregate results only; attribute the dataset when reusing results. |
| CMU agent trajectories | `configs/datasets/cmu-agent-trajectories.json` | NOASSERTION; access approval required | No download, redistribution, or empirical trajectory claim until access and reuse terms are explicitly accepted by an authorized person. The committed access audit uses public metadata only. |
| AgentTrace | `configs/datasets/agenttrace-nl2bash.json` | Apache-2.0 | Aggregate measurements and content-free replay receipts only; raw prompts, commands, outputs, and fixture contents remain outside Git. |
| InterCode NL2Bash curated reference | `configs/datasets/agenttrace-nl2bash.json` | MIT | Used only as the pinned command reference for the bounded AgentTrace replay audit; raw rows remain outside Git. |

Each manifest pins the upstream revision and records the specific files or
published schema used by an experiment. The source repository and dataset card
remain authoritative for notices, attribution requirements, and any embedded
third-party material.

The committed canonical fixtures are synthetic or content-minimized research
fixtures. They are not excerpts from a user's private harness directory. Public
availability is also not treated as consent to infer an identifiable person's
competence, productivity, health, intent, or collaboration needs.

Before adding another corpus:

1. record its immutable revision, file hashes where practical, declared license,
   access conditions, and provenance in `configs/datasets/`;
2. keep raw records outside Git;
3. emit only aggregate or explicitly synthetic fixtures;
4. scan outputs for secrets and direct identifiers; and
5. distinguish observed, reconstructed, inferred, and model-judged evidence.

Public Hugging Face corpora without declared license metadata are admissible for
analysis and are recorded as `NOASSERTION`; absence of a declaration is not
treated as an analysis veto or as permission to redistribute or train on the
raw corpus. Both redacted and unredacted corpora are admissible. Unredacted
sources receive the same content-minimization controls plus aggregate secret
pattern scanning, and no raw transcript, identifier, path, prompt, tool
argument, tool output, or extracted secret is committed.
