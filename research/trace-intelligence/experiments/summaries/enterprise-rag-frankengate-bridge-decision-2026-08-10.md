# EnterpriseRAG-Bench to Frankengate bridge decision

Date: 2026-08-10  
Status: decision record; no trace-learning or ontology-promotion claim

## Decision

Use EnterpriseRAG-Bench as a **document-side candidate and hard-negative
fixture**. Do not use it as a proxy for corporate trace mining, skill
improvement, ontology induction, or reusable SQL/tool correctness.

The benchmark supports a staged retrieval boundary:

```text
known source/system scope and time predicates
  -> exact identifiers and lexical candidates
  -> optional dense candidate recall
  -> frontier review/reranking
  -> evidence completeness, conflict, and NIL/abstention checks
  -> trace/artifact proposal only
  -> independent changed-system replay before promotion
```

## Evidence that drives the decision

| Observation | What it establishes | What it does not establish |
| --- | --- | --- |
| Oracle source filtering improved MRR `.511064 -> .593602`, R@1 `.444681 -> .527660`, and evidence R@10 `.584935 -> .690904` on all 500 questions | Scope/system metadata is a high-value first-stage filter | Learned aliases, authorization, or RLS |
| Wrong-source extras fell from `4.851064` to `0`, while same-source non-targets rose to `8.963830` | The remaining problem is semantic identity, not only source routing | That embeddings or an ontology solve the tail |
| Generic MiniLM dense R@20 was `.12`, below lexical candidate-pool recall `.224` | Generic dense retrieval is not a safe default on this synthetic corporate-shaped corpus | Domain-specific adaptation is disproven |
| Luna reranking improved semantic MRR `.1137 -> .1947`, but R@10 stayed at the lexical pool ceiling `.224` | Frontier review can reorder surfaced candidates | A model can recover absent evidence or replace candidate generation |
| All 30 targetless questions returned candidates | NIL/abstention must be a separate gate | A top-k result is an answer, memory, or artifact |

The source-filter arm is an oracle upper bound because the question metadata
provides the expected source types. It must not be described as a learned
metadata retriever or a governance proof.

## How to connect it to trace research

The benchmark should remain a separate document cohort. A future bridge may
attach a synthetic trace envelope to each retrieved evidence event, but the
envelope must add fields absent from the public benchmark:

- principal/team/project and consent scope;
- source exposure, rejection, and authorization-epoch events;
- tool-call inputs, outputs, failures, retries, and terminal outcomes;
- evidence IDs, answer facts, conflict/validity intervals, and reviewer labels;
- schema/environment hashes and changed-system mutations; and
- deletion, retention, replay, and release receipts.

Only after those fields exist should a candidate become an artifact, memory,
or skill proposal. The proposal then enters the existing independent replay
and changed-system gates; EnterpriseRAG scores never substitute for them.

## Required next comparison

On the same 500-question cohort, compare lexical/identifier, dense, hybrid,
and frontier arms while reporting candidate-pool recall separately from
reranker gain. Stratify by semantic, completeness, conflicting, constrained,
project, and targetless questions. Keep source scope fixed and explicit.

Then repeat the same representation matrix on the consented semantic cohort
described by
`configs/studies/enterprise-semantic-cohort-v1.json`, with independent labels
and changed-system replay. That is the first experiment capable of connecting
retrieval quality to reusable artifacts or skill utility.

## Promotion boundary

EnterpriseRAG can justify shipping a retrieval **front end** with exact
identifiers, source scope, optional dense recall, and selective frontier review.
It cannot justify shipping an automatically generated ontology, custom
embedding model, memory write, SQL/tool capsule, or skill. Those require
reviewed semantic/NIL labels, authority and freshness checks, independent
terminal outcomes, and prospective utility.

## Receipts

- [full 500-question source-filter ceiling](enterprise-rag-source-filter-ceiling-full-2026-08-10.md)
- [generic dense baseline](enterprise-rag-dense-baseline-2026-08-02.md)
- [frontier reranking](enterprise-rag-frontier-rerank-2026-08-02.md)
- [document/trace adaptation plan](enterprise-rag-bench-adaptation-2026-08-02.md)
- [objective closure audit](objective-closure-audit-2026-08-10.md)
