# Trace Commons feature ablation for repeated-work discovery

## Protocol and boundary

Trace Commons contains 28 Claude Code sessions. It does not expose stable
principal identity, semantic task labels, or prospective outcomes, so the
repeated first project/workspace component of `cwd` is used only as a
workstream proxy. Thirteen sessions are eligible after excluding generic home
directory buckets and requiring a repeated project proxy.

We compared leave-one-session-out TF-IDF retrieval using:

- event/tool structure only;
- user prompt terms;
- durable identifiers from tool metadata such as file paths, queries, and
  commands; and
- a prompt + identifier + structure combination.

Each arm also has a label-token-masked version to check whether the result is
just the project name appearing verbatim. Raw sessions remain external; the
receipt contains a manifest hash and aggregates only.

## Result

| Arm | Same-project top-1 | MRR |
|---|---:|---:|
| Structure | 1/13 (7.7%) | 0.215 |
| Prompt | 13/13 (100%) | 1.000 |
| Identifier | 12/13 (92.3%) | 0.938 |
| Combined | 13/13 (100%) | 1.000 |

The masked variants had the same aggregate scores in this cohort. This means
the signal is not explained solely by the literal first project path token,
but it may still reflect repeated prompts, project-specific vocabulary, or
other leakage from the public workstream proxy.

## Interpretation

Prompt and durable identifier features carry much more workstream signal than
event/tool structure. This supports preserving prompt text, exact identifiers,
file/tool provenance, and durable artifact references as first-class trace
fields. It does **not** establish cross-user similarity, a skill gap, or a
recommendation benefit: the proxy can reward repeated wording, and no human
intent or outcome labels exist.

The next test should use principal/time-disjoint, consented enterprise tasks
with blinded same-work labels, same-surface wrong-system negatives, and a
prospective next-task outcome. Only then can prompt/identifier similarity be
translated into a user or team recommendation.

Receipt: [`trace-commons-feature-ablation-2026-08-07.json`](../results/trace-commons-feature-ablation-2026-08-07.json).
Independent verification: [`trace-commons-feature-ablation-2026-08-07-verification.json`](../results/trace-commons-feature-ablation-2026-08-07-verification.json).

