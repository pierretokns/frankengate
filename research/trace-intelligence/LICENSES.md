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
| CMU agent trajectories | `configs/datasets/cmu-agent-trajectories.json` | NOASSERTION; access approval required | Explicitly waived on 2026-07-30 because access is gated. It is not on the acquisition or experiment critical path; the committed access audit remains a metadata-only negative receipt. |
| AgentTrace | `configs/datasets/agenttrace-nl2bash.json` | Apache-2.0 | Aggregate measurements and content-free replay receipts only; raw prompts, commands, outputs, and fixture contents remain outside Git. |
| InterCode NL2Bash curated reference | `configs/datasets/agenttrace-nl2bash.json` | MIT | Used only as the pinned command reference for the bounded AgentTrace replay audit; raw rows remain outside Git. |
| Trace2Skill SpreadsheetBench verified 400 | `configs/datasets/trace2skill-spreadsheetbench-verified.json` | Apache-2.0 declared in the upstream README; no license file observed in the pinned snapshot | Aggregate outcomes and hashes only. Initial/golden workbooks, trajectories, model-generated commands, and outputs remain in a disposable external cache. SpreadsheetBench is a controlled sandbox/replay domain, not the primary enterprise-value claim. |
| StateBench finance retrieval/SQL v0 | `configs/datasets/statebench-finance-retrieval-sql-v0.json` | State of AI repository terms; synthetic fixture | Aggregate results and hashes only. The pinned local fixture is a control/adapter seed with four executable SQL tasks, not a statistically adequate skill-learning corpus. |
| WMH BIRD-SQL traces | `configs/datasets/wmh-bird-sql-traces.json` | CC-BY-SA-4.0 | Raw tasks, gold SQL, schemas, database content, tool arguments, and observations stay outside Git. Aggregate structural and replay-readiness results only. Derivatives must preserve attribution/share-alike. |
| WMH CRMArena traces | `configs/datasets/wmh-crmarena-traces.json` | CC-BY-NC-4.0 | Non-commercial research only. Raw org content, tasks, answers, arguments, and observations stay outside Git; aggregate results only. |
| Microsoft MAGIC | `configs/datasets/magic-text-to-sql-trajectories.json` | MIT project license plus dataset-card research-only restriction | Inventory only pending a frozen mining arm. Do not treat it as unrestricted production-training data or an independent outcome oracle. |
| PT-BR agentic Text-to-SQL | `configs/datasets/pt-br-agentic-text-to-sql-trajectories.json` | Apache-2.0 | Inventory only pending a frozen mining arm; raw distilled conversations stay outside Git. |
| Analyst Buddy Text-to-SQL traces | `configs/datasets/analyst-buddy-text-to-sql-traces.json` | CC-BY-SA-4.0 | Qualitative paired-recovery control only; raw trajectories stay outside Git. |
| Defog SQL-Eval + Defog Data | `configs/datasets/defog-sql-eval-enterprise.json` | Apache-2.0 | Hash-pinned external PostgreSQL source and database fixtures. Questions, gold SQL, database rows, candidate SQL, and raw audit events remain outside Git; only the content-free cohort and aggregate receipts are committed. |
| Spider2 local Lite + DBT | `configs/datasets/spider2-local-enterprise-sql.json` | MIT | Source audit only pending curated cohorts and a hardened verifier. Raw tasks, SQL, result files, databases, projects, knowledge files, and transcripts remain outside Git. |

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
