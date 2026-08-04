# Longitudinal memory cohort expansion

## Outcome

The source-stratified deterministic count gates passed. This unseals an exploratory preregistered model and blinded-human phase; it does **not** establish memory quality, causal benefit, contributor independence, population validity, or enterprise generalization.

## Source strata

| Stratum | Histories | Online reads | Changed cases | Exact cross-session | Exact-transition projects |
|---|---:|---:|---:|---:|---:|
| [Trace Commons](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf) | 28 | 3 | 1 | 1 | 1 |
| [Fable-5 top-level](https://huggingface.co/datasets/Glint-Research/Fable-5-traces/tree/e05c417852fc59fd8da758e68b352732423ca0cb/claude/projects) | 79 | 14 | 9 | 4 | 2 |

## Frozen count gates

| Gate | Observed | Minimum | Status |
|---|---:|---:|---|
| online_queries | 17 | 10 | passed |
| changed_post_observation_cases | 10 | 5 | passed |
| exact_cross_session_write_to_later_read | 5 | 2 | passed |
| exact-transition source-scoped project contexts | 3 | 2 | passed |

## Confirmatory diversity gate

| Gate | Observed | Minimum | Status |
|---|---:|---:|---|
| source families with exact transitions | 2 | 3 | failed |
| exact-transition source-scoped project contexts | 3 | 5 | failed |

This confirmatory gate fails. It blocks architecture-quality and enterprise-transfer claims even though the smaller mechanics count gate passes.

## Concentration and hard boundary

Fable-5 supplies 14 online cases across 2 project contexts with cluster sizes [11, 3]. Its changed cases are distributed [8, 1]; its exact cross-session cases are distributed [2, 2].

Exact source-file, native session, record UUID, session-scoped tool ID, and content-free session-shape overlap controls are all zero. These controls do not rule out re-export, semantic, contributor, or source-family overlap.

The selected Glint archive is a 115/115 byte-exact mirror of the [pinned cfahlgren1 Fable-5 raw archive](https://huggingface.co/datasets/cfahlgren1/Fable-5-traces/tree/0ba6f53852f296f8389290b112054b47cec2dc1f). The mirror is therefore one source-family/publisher-home cluster, never a second independent source. The dataset card tags the corpus as machine-generated/synthetic and provides no explicit donation, consent, or redaction statement.

Therefore the next phase may measure within-corpus model and review behavior, but it may not claim a cross-enterprise effect or enable automatic memory promotion.

Result SHA-256: `33bb7b99f1817d10ab906db02f648df1484be4261e4444e7897c93c2b1f04131`
