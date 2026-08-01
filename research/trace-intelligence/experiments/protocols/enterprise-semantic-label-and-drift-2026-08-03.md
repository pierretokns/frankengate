# Enterprise semantic-label and changed-system replay protocol

**Status:** preregistration for the next authorized study; no production
promotion is authorized by this document.

## Purpose

Close the two largest evidence gaps in the current trace-artifact program:

1. deterministic gold-SQL focus objects are not enterprise semantic-alias
   truth; and
2. public/synthetic schema drift does not establish reusable artifact utility
   in a real changed system.

The study must measure retrieval quality, artifact validity, and downstream
task utility separately. A positive retrieval result cannot promote an
artifact, and a successful SQL execution cannot establish semantic
equivalence by itself.

## Cohort and authority

Use only an explicitly authorized internal cohort or a license-cleared public
replacement. Each record receives a stable study ID and contains:

- the user request and bounded evidence spans;
- source tenant/team/project/system and effective time interval;
- candidate schema objects and tools available at request time;
- the executed SQL/tool artifact, parameters, result shape, plan/latency,
  errors, corrections, and independent outcome evidence;
- source, target, and migration-version fingerprints.

Raw prompts, SQL, tool arguments, and rows stay in an access-controlled
external audit store. Committed receipts contain hashes, counts, labels, and
aggregate metrics only.

## Annotation contract

Two domain annotators independently label every query/object or query/tool
pair. They must choose exactly one relevance label:

| Label | Meaning |
|---|---|
| `exact` | The object/tool is explicitly named and is the intended target. |
| `alias` | The request uses an undocumented or organization-specific name that the annotator can justify from evidence. |
| `semantic` | The target is implied by task meaning, not identifier surface. |
| `wrong_scope` | The candidate is plausible but belongs to another system, tenant, project, or authority scope. |
| `stale` | It was valid historically but is invalid for the request's effective time. |
| `nil` | No candidate in the frozen pool is valid. |
| `unclear` | Evidence is insufficient to decide without clarification. |

Annotators also record the canonical concept ID, evidence-span IDs, temporal
validity, and whether the candidate is executable. They may not inspect model
rankings while labeling. Disagreements are adjudicated by a third SME; report
raw agreement and Cohen's κ (or Krippendorff's α for missing labels). Do not
collapse `nil` or `unclear` into a negative retrieval label.

## Frozen retrieval experiment

Freeze candidate generation before labels are unsealed. Include deliberately
balanced hard negatives:

- same normalized identifier in the same database;
- same identifier in a different system or tenant;
- same table with a different join grain or business meaning;
- temporal rename and stale schema versions;
- semantically similar tool with a different authority requirement;
- true NIL and ambiguous pools.

Evaluate these arms on the identical candidate pool:

1. exact identifier plus structured scope;
2. lexical/BM25 plus structured scope;
3. dense embedding plus structured scope;
4. identifier-aware learned ranker;
5. frontier reranker with an explicit retrieve/abstain decision.

Hold out users, teams/projects, systems, and time. Report MRR, Recall@1/5/20,
wrong-scope-before-target, same-scope collision rate, NIL/unclear abstention,
calibration, p50/p95 latency, and cost per 1,000 cases. The primary comparison
is paired per-case delta against exact+scope; no model is promoted on a pooled
metric alone.

## Changed-system artifact factorial

For every artifact with an independent accepted outcome, create a sealed
replay fixture with the original and changed environment. Randomize or
counterbalance these arms:

- no artifact / regenerate;
- strict schema and authority fingerprint;
- name-only adaptation (negative control);
- reviewed semantic-ID mapping;
- reviewed mapping plus result-shape and outcome validation.

Test at least these changes:

1. additive column/tool parameter (benign drift);
2. approved table/column/parameter rename;
3. same-surface semantic collision;
4. changed join grain or result meaning;
5. stale authorization epoch or deleted source;
6. tool contract change with an unsafe or unauthorized alternative.

The independent verifier must check authority, schema/version, parameter
contract, result shape, semantic outcome, deletion, rollback, and absence of
unauthorized observations. The primary safety metric is false semantic
acceptance; the primary utility metric is successful changed-system replay
relative to regeneration. Any false semantic acceptance blocks promotion.

## Release gates

An artifact or embedding adapter remains proposal-only unless all gates pass:

- at least 100 labeled target cases, 50 hard negatives, and 25 NIL/unclear
  cases in the minimum study slice;
- two independent annotators and reported agreement/adjudication;
- user/project/system/time-held-out evaluation;
- no statistically material increase in wrong-scope, stale, or collision
  retrieval;
- changed-system replay with zero false semantic acceptance in the sealed
  safety set;
- independent outcome verification and a cost/latency budget;
- explicit rollback and deletion receipts;
- replication by a second runner or external partner before production use.

These are minimum gates, not evidence that the hypothesis will succeed. A
null result is publishable and should be retained.

## Publication package

Publish the protocol, content-minimized manifests, verifier, aggregate receipts,
and negative results. Keep enterprise raw content behind a sealed replay API or
replace it with a license-cleared public cohort. The paper should report three
separate endpoints: retrieval, artifact validity, and changed-task utility.
The closest venues are ACL Industry/EMNLP Industry for alias retrieval,
SIGMOD/VLDB for governed artifact reuse, and ICSE/FSE for trace-to-replay
lifecycle design.

## Tracking

- Epic: [#118](https://github.com/pierretokns/frankengate/issues/118)
- Governed SQL/tool artifact reuse: [#119](https://github.com/pierretokns/frankengate/issues/119)
- Alias and hard-negative mining: [#120](https://github.com/pierretokns/frankengate/issues/120)
- Domain embedding evaluation: [#121](https://github.com/pierretokns/frankengate/issues/121)
- Curation feedback loop: [#123](https://github.com/pierretokns/frankengate/issues/123)
