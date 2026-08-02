# Corporate trace-artifact learning reality check

**Audit date:** 2026-08-10
**Branch:** `codex/trace-intelligence-academic-program`
**Status:** active research; not product-complete

This is the periodic reality check for the full enterprise objective. It treats
the independent receipts as the evidence authority and keeps public proxies,
silver labels, synthetic fixtures, and enterprise outcomes separate.

## What actually works today

| Capability | Evidence-backed status | What can safely be built |
|---|---|---|
| Personal trace/artifact mechanics | Governed capsules, scope/epoch/schema gates, independent replay, and content-minimized receipts pass | Personal history, review queues, validated artifact capsules, versioned proposals |
| Candidate retrieval | Exact identifiers and structured scope are strongest; Nomic improves broad recall; Luna compresses noisy shortlists | A staged retrieval cascade, not one universal semantic index |
| Changed-system safety | Typed metadata + deterministic gate produced `10/10` safe/correct SQLite replays; naive name-first reuse made `7` unsafe accepts | Never promote by name, embedding score, or matching output alone |
| Subplan composition | Two seeds on five broker tasks reached `10/10` versus `5/10` controls | Keep composable subplans as a quarantined/reviewed arm |
| Older terminology ports | Termhood/acronym ports provide interpretable candidate generation and review signals | Offline scoped term/acronym queues only |
| Local supervised adaptation | Task-disjoint adapter improved Nomic MRR `.940152→.947917` and Recall@1 `.909091→.931818`, but lowered Recall@5 and did not reduce invalid candidates | Labelled shadow reranker with rollback, not a universal custom embedding |
| Finance-specialized embedding | On pinned FinanceBench, BalyasnyAI/multilingual-e5-base reached Recall@20 `1.000` / MRR `.8087` versus Qwen3-Embedding `.9933/.7164` and TF-IDF `.6867/.3005`; the same projection through Ollama Nomic fell to `.4533/.1661` | Strong domain-model and serving-identity signal; keep as a governed shadow lane, not proof of corporate trace transfer |

## One-shot ontology generation: current reality check

The strong social-media claim—“give one tool or document to an ontology
generator and receive the enterprise model”—is not supported by either the
recent literature or our controls. A recent enterprise ontology paper,
[OntoEKG](https://arxiv.org/abs/2602.01276), separates class/property
extraction from hierarchy/entailment and reports exact-match F1 of `.102` for
Data, `0` for Finance, and `.048` for Logistics. Its embedding-based fuzzy F1
looks better (`.724`, `.121`, and `.431` respectively), but the authors still
identify scope and hierarchical-reasoning limitations. Fuzzy string agreement
is therefore not a sufficient ontology-quality metric.

Our own measurements line up with that boundary:

- GLiNER produced useful candidate spans (`7/8` on a corrected contextual
  probe), but its output was dominated by project/tool labels and was not safe
  for automatic glossary promotion.
- Termhood improved a narrow within-schema retrieval slice while transferring
  poorly to held-out schemas (`.015` direct termhood recall); acronym and term
  candidates were cohort-local rather than a global corporate dictionary.
- Full-corpus generic MiniLM retrieval on the 125-question EnterpriseRAG
  semantic slice reached only R@20 `.12` with title/snippet views and `.064`
  with title-only, below lexical top-20 pool recall `.224`.
- A task-disjoint supervised Nomic adapter improved MRR `.940152 → .947917`
  and R@1 `.909091 → .931818`, but reduced R@5 and did not reduce incompatible
  shortlist selections. This is a narrow labelled reranking signal, not a
  universal corporate embedding result.

The correct interpretation is that the tools are complementary stages:
terminology miners find candidates; entity-resolution methods propose
same/different/NIL decisions; frontier models extract schema-constrained
proposals with evidence; SHACL-like checks reject malformed graphs; and
replay/authority gates decide whether anything becomes an artifact or skill.
No stage can infer canonical identity, temporal validity, authority, or task
utility from an isolated tool description. Those are missing variables, not
merely missing model capacity.

Public enterprise tuning guidance follows the same pattern. Databricks puts
hybrid retrieval, metadata, query reformulation, reranking, and evaluation
before embedding tuning and calls tuning a last resort ([retrieval quality
guide](https://docs.databricks.com/gcp/en/ai-search/retrieval-quality)). Its
Genie knowledge store uses curated synonyms, joins, SQL expressions, verified
queries, and feedback-derived updates ([Genie quality tuning](https://docs.databricks.com/aws/en/genie/tune-quality)). Google requires
supervised corpus/query/relevance labels for embedding tuning
([embedding tuning](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tuning/embeddings?hl=en)); Cohere exposes explicit relevant passages and hard negatives for reranker tuning
([rerank tuning](https://docs.cohere.com/v1/docs/rerank-starting-the-training)).
This is evidence for converting traces into reviewed labels and reusable
artifacts first—not pretraining directly on raw logs.

**Decision:** keep ontology generation as a review-queue capability, not a
canonical write path. The smallest defensible implementation is
`typed trace → scoped terms/aliases → reviewed entity links → schema-grounded
relations → evidence/constraint checks → changed-system replay`. A new vector
database or another one-shot generator is not justified until a consented,
entity/time/project-held-out cohort shows downstream utility and lower
wrong-system/NIL error.

## Embedding versus model-based insight mining

The two approaches answer different questions and should not be collapsed into
one score. On a 16-case BIRD trace probe, a frontier model given only the user
question abstained on all cases. Adding the recorded SQL trajectory raised
artifact recall to `87.5%`, but positive precision was only `53.8%` with six
false positives. Tool context adds signal; it does not make model judgment a
release gate. The authoritative check remained independent SQLite replay.

On six blinded Wisp recovery candidates, frontier/local model agreement was
`33.3%` for cause, `16.7%` for outcome, and `0%` for usefulness; all-six-field
agreement was `0%`. This means a structured model pass is a review proposal,
not a stable insight label. On the nine-query MATM cascade, Luna tied lexical
ranking while adding `104.118s` total wall time, whereas embeddings were weaker
on that already-rich candidate pool but had improved candidate recall in a
separate study.

The evidence-backed cascade is therefore:

```text
exact identifiers + scope
  -> lexical/termhood/dense candidate recall
  -> trajectory-aware frontier proposal (only when ambiguous/high-value)
  -> independent replay, authority, and schema checks
  -> human or multi-model adjudication for insight labels
```

Do not use a model to label usefulness, skill gaps, or enterprise patterns from
raw traces without an outcome-bearing rubric. Do not use embeddings to infer
those labels. They are retrieval and prioritization components; the truth
source must be a reviewer, a deterministic verifier, or a prospective outcome.

## Historical retrieval supervision: the strongest adjacent production method

[Cursor's semantic-search report](https://cursor.com/blog/semsearch) describes a
useful method that is adjacent to, but not identical with, governed SQL/tool
learning: later search/open behavior is reviewed by an LLM to create relevance
targets, then distilled into a custom retriever. Its benchmark work also mines
real sessions and pairs them with committed changes before running offline and
online checks ([CursorBench](https://cursor.com/blog/cursorbench)). This is much
stronger supervision than raw term frequency, but it still does not establish
enterprise authority, user intent, or safe artifact reuse.

The adaptable Frankengate version is now specified as a separate method arm:

```text
episode query + exposed candidate set
  -> later inspection/search/open/repair evidence
  -> frontier relevance proposal (positive / negative / unclear)
  -> replay and authority validation
  -> fold-local ranker or embedding adapter
  -> project/time/system-held-out evaluation
```

Important controls are exposure-aware negatives (a candidate not shown is
missing data, not a negative), same-surface/wrong-system pairs, temporal
replacements, stale authority, and a regeneration arm when the artifact pool
has no compatible item. The model-generated relevance label remains silver;
only independent replay, human adjudication, or a prospective outcome can
promote it. This is the next credible route to a corporate retriever trained
from traces, but it must not be described as reproducing Cursor's private model
or internal benchmark.

## What is not proven

The following enterprise claims remain unproven because no current receipt has
independent labels and prospective outcomes at the required scope:

- identifying which users are doing the same work;
- identifying missing cloud/domain skills;
- recommending collaborators without unwanted contact or negative transfer;
- converting traces into useful skills or memories that improve later tasks;
- automatically discovering enterprise aliases or ontology edges;
- fine-tuning a custom corporate embedding that improves downstream artifact
  utility;
- proving that a trace-mined procedure improves multi-step agent success;
- proving that suggested evals change user behavior or production quality.

The local cross-user study makes the boundary sharper: lexical and dense
candidate generators agreed on only `6.01%` of top-1 pairs across 549×38
sessions, but there is no task-equivalence truth. Divergence is not discovery.

## Hard negative and model boundaries

The current architecture should assume these failure modes:

1. Same surface, different semantic system.
2. Same system, temporal replacement or stale authority epoch.
3. Schema-compatible output that is still unauthorized.
4. Dense candidate recall with a noisy incompatible tail.
5. Frontier selection that can rank a candidate but cannot enforce authority.
6. Repeated tool success that reflects process outcome, not semantic correctness.
7. Project/family labels that correlate with work without proving intent.

Therefore the smallest defensible cascade is:

```text
scope + authority + exact identifiers
  -> lexical / termhood / dense candidate recall
  -> optional labelled reranker
  -> selective frontier or human review
  -> deterministic compatibility gate
  -> independent replay / changed-system validation
  -> versioned artifact, eval, or skill proposal
```

## Does the existing plan close the gap?

No. The current beads and research code close substantial mechanics gaps, but
implementing them alone cannot close the enterprise vision. The remaining
blocker is an outcome-bearing cohort, not another vector database or model:

1. 20–40 authorized tasks with principal/team/project/time/system scope;
2. two blinded semantic labels plus adjudicated NIL/unclear cases;
3. same-surface wrong-system, temporal, result-preserving, and irrelevant
   exposed negatives;
4. source and changed-system environments with authority-epoch receipts;
5. independent terminal outcomes and replay validators; and
6. prospective measurements of correction burden, task success, usefulness,
   unwanted contact, negative transfer, cost, and latency.

Without that cohort, further public-proxy model swaps mostly measure benchmark
headroom, not enterprise learning.

The missing-cohort requirement is now machine-gated by the [enterprise
semantic-cohort contract](../configs/studies/enterprise-semantic-cohort-v1.json)
and [validator](../enterprise_semantic_cohort_validator.rb). A two-task fixture
passes structural conformance but remains promotion-ineligible; an incomplete
fixture fails closed on missing consent, holdouts, arms, and tasks. This is a
partner handoff gate, not evidence that the required internal cohort exists.

The [hard-negative strata supply audit](dataclaw-hard-negative-strata-2026-08-02.md)
shows that the parseable public DataClaw export can supply a frozen review pool:
the chronological train half contains 2,610 same-surface/different-path,
1,601 cross-project same-surface/different-path, 306 cross-project exact-path,
and 2,125 same-project exact-identity candidate pairs. This closes the public
candidate-capacity question, but not the semantic-label, consent, changed-system,
or outcome requirements.

## Research and publication path

The publishable claim is narrow and defensible:

> **From agent traces to governed enterprise artifacts: exposure-aware
> supervision, identifier-aware hard negatives, and replay-validated reuse.**

The strongest partner split remains:

- MIT DSAIL / Everest: learned data systems, SQL artifacts, and schema drift;
- MIT CLEAR/TRAC: human feedback, accountability, and negative transfer;
- CMU LTI / SkillLearnBench: sequential skill evaluation and verifier design;
- Harvard CHARM/CRCS/DASlab: human outcomes and data-system boundaries.

The current branch is ready for a reproduction packet, but not for a claim that
Frankengate already learns enterprise skills or identifies collaborators.

The [objective closure audit](corporate-trace-objective-closure-audit-2026-08-02.md)
is the requirement-by-requirement ledger behind this status. It marks each
requested capability as demonstrated, partial, or open and names the missing
evidence, preventing a public proxy from silently standing in for an enterprise
outcome.

## Authoritative receipts

- [Research program status](research-program-status-2026-08-09.md)
- [Embedding/model cascade](embedding-model-cascade-decision-2026-08-09.md)
- [Changed-system replay bridge](changed-system-authority-replay-bridge-2026-08-09.md)
- [Task-disjoint adapter](wmh-bird-sql-embedding-adapter-cohort-2026-08-09.md)
- [Cross-user candidate generation](dataclaw-cross-user-dense-candidates-2026-08-09.md)
- [Next experiments and promotion gates](corporate-trace-artifact-learning-next-experiments-2026-08-06.md)
