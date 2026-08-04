# Canonical RAG interaction contract (2026)

Status: schema contract and implementation plan; not a runtime API claim.

The gateway must separate the immutable interaction/evidence record from
derived retrieval and reward signals. Raw content is eligible only when the
privacy policy and retention class permit it; hashes and redacted summaries are
the default shared representation.

## Records

| Record | Required identity and lineage | Required governance/evaluation fields |
|---|---|---|
| `RAGInteraction` | interaction ID, tenant, principal, logical request ID, physical attempt ID, trace ID, timestamps | policy revision, privacy receipt, retention class, modality, model/router revision |
| `RetrievalRun` | run ID, interaction ID, query hash, embedding contract, index revision | backend, query plan, candidate count, authorization decision, deletion watermark, latency |
| `RetrievedItem` | source ID, chunk ID, source revision, parent document, rank | ACL scope, classification, score components, citation eligibility, tombstone state |
| `Claim` | claim ID, interaction/run ID, normalized claim hash, source references | support status, contradiction status, reviewer state, evidence lineage |
| `EvaluationResult` | evaluator revision, dataset/cohort ID, sample ID, candidate/model revision | metric, score, confidence, rubric version, evidence-vs-reward class |
| `KnowledgeGap` | cluster ID, query/claim hashes, affected tenant/team scope | gap type, frequency, severity, confidence, privacy class, proposed owner |
| `KBChangeProposal` | proposal ID, source gap IDs, target collection/revision | diff manifest, ACL impact, evaluator bundle, human approval, rollback pointer |

## Invariants

1. Authorization is evaluated before candidate exposure, including progressive,
   reranked, replay, export, and semantic-cache paths.
2. A physical fallback attempt never replaces the logical interaction ID; cost,
   latency, and outcome accounting retain both identities.
3. Evidence quality and reward/feedback are separate fields and stores. A user
   preference cannot silently become proof that a retrieved source was correct.
4. Every derived embedding, index, evaluator, and proposal is reproducible from
   a signed contract containing model/tokenizer/prompt/chunking/ACL revisions.
5. Deletion, legal hold, policy changes, and principal deprovisioning propagate
   through tombstones before a derived result can be returned.
6. Knowledge-gap clustering uses redacted hashes/features by default and emits
   no raw cross-team content without an explicit authorized review operation.

## Minimal evaluation bundle

Each retrieval or RAG change must include lexical, dense, hybrid, reranked, and
adapted arms; finance/jargon and hard-negative cohorts; ACL and deletion oracles;
recall@k, nDCG, MRR, support/contradiction rates; p50/p95 latency and cost; a
frozen holdout; and a human-approved promotion/rollback manifest.
