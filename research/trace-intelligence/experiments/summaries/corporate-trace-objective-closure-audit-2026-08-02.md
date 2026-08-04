# Corporate trace-learning objective closure audit

**Status:** active research; the full enterprise objective is not yet proven.

This audit maps each requested capability to the strongest evidence currently
available. Public datasets, synthetic fixtures, silver labels, and enterprise
outcomes are kept separate. A result is marked **demonstrated** only when the
receipt measures the requested property directly; otherwise it is **partial**
or **open**.

## Requirement-to-evidence map

| Capability | Current status | Strongest evidence | Safe conclusion |
|---|---|---|---|
| Reuse validated SQL/tool artifacts | Partial | Only `76/193` executable BIRD trace queries matched independent gold; controlled typed-parameter replay matched `75/75`; natural leave-one-out reuse matched `1/76`. See [trace-derived reuse](bird-trace-artifact-reuse-2026-08-07.md) and [parameterized retrieval](parameterized-artifact-retrieval-2026-08-06.md). | Store immutable identity, scope, authority, schema/epoch, bindings, and replay evidence. Never promote from recurrence or text similarity alone. |
| Discover corporate concepts and aliases | Candidate generation only | Termhood transfer recall was `.358` within represented vocabulary and `.015` on held-out schemas; acronym extraction passed `8/8` synthetic cases but cross-cohort definitions were local. See [modernization audit](older-tool-modernization-value-audit-2026-08-05.md). | Keep term/acronym candidates scoped and review-gated. No automatic ontology or alias writes. |
| Mine useful hard negatives | Compatibility negatives demonstrated; semantic negatives open | `1,236` exposed-table substitutions produced `1,210` execution errors, `22` result mismatches, and `4` result-preserving substitutions. See [exposure counterfactuals](wmh-bird-exposure-counterfactual-2026-08-09.md). | Replay can establish compatibility boundaries. Human wrong-system, temporal, and NIL labels are still required for semantic training. |
| Adapt domain-specific embeddings | Local reranking signal only | Task-disjoint Nomic adaptation improved MRR `.940152→.947917` and Recall@1 `.909091→.931818`, but reduced Recall@5 and did not reduce invalid selections. Project-held-out lexical adaptation helped one history corpus but hurt tool-only ranking. See [adapter cohort](wmh-bird-sql-embedding-adapter-cohort-2026-08-09.md) and [cascade decision](embedding-model-cascade-decision-2026-08-09.md). | Use a shadow, rollback-capable reranker. Do not claim a universal corporate embedding from unlabelled logs. |
| Compare embeddings with frontier/model mining | Cascade shape demonstrated on public proxies | Dense retrieval supplies broad recall; frontier review compresses noisy shortlists and improves refusal/context handling, but both remain proxy- and label-limited. See [dense/frontier cohort](wmh-bird-sql-dense-frontier-cohort-2026-08-09.md) and [term-context probe](claude-history-term-context-model-probe-2026-08-09.md). | Use exact/scope → lexical/termhood/dense → optional reranker → selective frontier/human review → replay. |
| Preserve identifiers and structured context | Demonstrated as a safety boundary | Identifier-aware ranking reached MRR `.737`, Recall@1 `.647`, and zero collision-before-target on its proxy; scope filtering sharply reduced same-surface collisions. See [identifier-aware reranking](nl2sql-identifier-reranker-2026-08-03.md). | Keep immutable identifiers, resource identity, scope, and time as first-class fields; embeddings cannot replace them. |
| Convert traces into improved skills | Open; no promotion evidence | BIRD skill replays were low-headroom and underpowered; the bounded SkillOpt replication did not beat controls; reviewed human guidance helped one changed-data task but generated composition did not. See [skill replay synthesis](skill-replay-evidence-synthesis-2026-08-09.md). | Keep proposals quarantined behind changed-system replay, semantic verifiers, and rollback. |
| Explain shared work or skill gaps across users | Open | Cross-user dense/lexical agreement was only `6.01%` top-1, with no independent task-equivalence or outcome labels. See [cross-user transfer](dataclaw-cross-user-artifact-transfer-2026-08-09.md). | Candidate similarity is not evidence that users do the same work or need the same skill. Recommendations require consent, labels, and unwanted-contact/negative-transfer checks. |
| Publish a defensible research contribution | Ready as a methods paper, not as a product-efficacy claim | The evidence supports a governed lifecycle: structured identity and scope, hard-negative-aware retrieval, frontier-assisted review, independent replay, and changed-system gates. See [reality check](reality-check-2026-08-10.md) and [partner opportunities](publication-partner-opportunities-2026-08-02.md). | Lead with the evidence-to-artifact protocol, not “memory improves agents.” CMU LTI and MIT DSAIL are the closest first partners; Harvard human-outcome groups and MIT CLEAR/TRAC are complementary. |

## What the combined architecture can answer now

With current evidence, Frankengate can safely answer questions such as:

- Which prior artifacts are exact or scope-compatible candidates?
- Which exposed tables or tools fail independent replay?
- Which identifiers, terms, or acronyms recur inside a project or time scope?
- Which candidates need frontier or human review because retrieval is uncertain?
- Which proposed artifact versions passed source and changed-system gates?

It cannot yet answer, with enterprise-grade validity:

- who is doing the same work across users;
- which cloud or domain skills a person is missing;
- whether a mined skill improves a later task;
- whether an alias is semantically correct across systems or time; or
- whether an embedding update improves real artifact utility.

## Minimum experiment that closes the remaining gap

The next decisive study is not another vector database. It is a consented,
prospective cohort with:

1. `20–40` sequential tasks across several SQL/tool families;
2. principal, team, project, system, schema, and authority-epoch scope;
3. two blinded semantic labels plus adjudicated NIL/unclear cases;
4. same-surface/wrong-system, temporal, result-preserving, and irrelevant
   candidates;
5. source and changed-system replay environments;
6. paired no-skill, neutral-placebo, reviewed-guidance, and mined-skill arms;
7. terminal task outcome, correction burden, latency, cost, unsafe action, and
   rollback measurements; and
8. prospective tests of artifact reuse, skill suggestions, and cross-user
   recommendations.

Until that cohort exists, additional public-proxy model swaps can refine the
cascade but cannot close the enterprise-learning claim.

## Claim boundary

The full objective remains **incomplete but actionable**, not blocked. The
current work has established the mechanics and the safety architecture, while
the missing proof is semantic labels plus prospective changed-system outcomes.
