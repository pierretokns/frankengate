# EnterpriseRAG-Bench: what it gives us (and what it does not)

Date: 2026-08-02  
Status: research adaptation; no enterprise promotion claim

## Bottom line

[EnterpriseRAG-Bench](https://arxiv.org/abs/2605.05253) is the strongest public
**document-side** companion for our work. It gives us a large, reproducible
enterprise-shaped retrieval substrate and a disciplined question taxonomy. It
does **not** test trace mining, skill discovery, tool reuse, user friction,
cross-user learning, authority epochs, or changed-system outcomes. We should
use it to test candidate retrieval and evidence-selection methods, then join
those methods to our trace/replay pilot. We should not treat a high benchmark
score as evidence that a skill, SQL artifact, or embedding model improves real
enterprise work.

## What the benchmark contains

The [official repository](https://github.com/onyx-dot-app/EnterpriseRAG-Bench)
describes just over 500,000 synthetic documents from Slack, Gmail, Linear,
Google Drive, HubSpot, Fireflies, GitHub, Jira, and Confluence, plus 500
questions. The questions cover basic lookup, low-keyword semantic lookup,
intra-document reasoning, project aggregation, constrained answers, conflicting
facts, completeness, miscellaneous material, high-level synthesis, and
information-not-found cases. A further 100 metadata-dependent questions are
provided separately and excluded from the main leaderboard.

The generation recipe is unusually useful for our purposes:

1. Scaffold a company overview, initiatives, people, and source structure.
2. Generate documents with cross-document awareness and internal codenames.
3. Add realistic distractors: misfiled documents, stale or conflicting
   near-duplicates, drafts, and off-topic material.

The repository's methodology exposes a useful *data-generation* result that
is easy to miss when only looking at the leaderboard: a naive high-volume
generation run produced close siblings for more than 40% of documents. The
authors reduce this collapse with source-specific scaffolds, topic leaves,
document-count targets, and visibility of nearby filenames. The released
corpus then applies 5% random shuffling, 3% LLM-guided local misfiling, and a
separate near-duplicate/update process. These are not measurements of a real
company's noise rate; they are controllable perturbations we can reuse in a
Frankengate fixture. See the [generation methodology](https://github.com/onyx-dot-app/EnterpriseRAG-Bench/blob/main/methodology.md)
for the exact construction stages.

This is a good *controlled world generator*. It is not a sample of real
employee behavior: the corpus is synthetic, the questions are authored, and it
has no user principals, correction histories, tool-call trajectories, or
independent task outcomes. The repository also explicitly warns that benchmark
data must not enter training corpora; keep it evaluation-only.

## What we should adopt

### 1. A document-side hard-negative taxonomy

Use the benchmark's noise and question classes as fixed slices in our retrieval
receipt:

| EnterpriseRAG-Bench slice | Frankengate hypothesis it can test |
| --- | --- |
| Semantic | Do embeddings or term/alias expansion recover company concepts when literal overlap is low? |
| Project related / high level | Can retrieval assemble a coherent initiative view across systems and users? |
| Constrained | Do metadata, time, project, and scope filters beat semantic similarity? |
| Conflicting info | Can the system select the current/authoritative fact rather than the nearest duplicate? |
| Completeness | Does top-k retrieval miss required evidence even when answer generation sounds plausible? |
| Info not found | Does the system abstain instead of hallucinating an answer or promoting a bad artifact? |
| Extra metadata questions | Can authorization, source, owner, and other structured predicates be enforced before ranking? |

These slices map directly to our existing dense/lexical/frontier cascade and
give us a repeatable place to measure identifier-aware retrieval, NIL behavior,
conflict resolution, and evidence completeness.

### 2. Cross-source coherence as a test fixture

The shared company scaffold should become the document half of a Frankengate
synthetic fixture. Add trace records that say which source documents were
retrieved, ignored, rejected, or used in a tool call. This lets us test whether
a proposed skill or artifact is grounded in the evidence actually exposed to
the agent, rather than merely matching a hidden answer.

### 3. Correction-aware evaluation

The benchmark's evaluation process treats retrieved-document pools and gold
evidence as reviewable rather than immutable. We should copy that discipline:
store answer facts, evidence IDs, contradiction/temporal status, and reviewer
decisions separately. A changed gold set must create a new evaluation version;
it must never silently rewrite historical trace results.

The benchmark's answer records also separate `expected_doc_ids`, `gold_answer`,
and atomic `answer_facts`. Its evaluator can revise a gold answer when reviewed
candidate evidence demonstrates that the original answer is incomplete or
incorrect. We should borrow the separation, but make revisions append-only and
reviewer-attributed in Frankengate; an LLM-generated correction is not a
promotion decision by itself.

### 4. Metadata-aware retrieval as a first-class arm

Run the additional metadata-dependent questions as a separate arm. They are a
useful bridge to our governance work, but they are not an RLS proof: the public
benchmark does not model our tenant policy, virtual-key identity, or
authorization epoch. We still need an independent policy-leakage test.

## What it cannot establish

EnterpriseRAG-Bench cannot answer the questions we ultimately care about:

- whether two real users are doing the same work;
- whether a repeated prompt/re-prompt sequence represents friction or merely
  exploration;
- whether a mined SQL/tool artifact is valid in a changed system;
- whether a generated skill improves a later task for the same user or a new
  user;
- whether a recommendation closes a capability gap;
- whether an embedding adapts to a real company's aliases and hard negatives;
- whether a source was authorized, stale, or outside the agent's exposure set.

Those require our trace-side contract: stable principal/scope IDs, exposure
and rejection events, tool inputs/outputs, independent terminal outcomes,
environment/schema epochs, reviewer labels, and prospective replay. A benchmark
answer score is therefore a retrieval sanity check, not an artifact-promotion
gate.

## How it fits the current program

Use two explicitly separate cohorts:

**Document cohort (EnterpriseRAG-Bench).** Compare lexical/termhood, dense,
identifier-aware, metadata-filtered, frontier-reranked, and hybrid retrieval on
the ten core slices plus the metadata set. Report recall/MRR, answer correctness,
completeness, conflict resolution, NIL abstention, stale-source selection, and
metadata leakage.

**Trace cohort (authorized Frankengate traces and the existing public trace
proxies).** Compare strict fingerprint reuse, reviewed semantic artifact reuse,
generated/reviewed skills, and independent replay under changed data and
authority epochs. Report execution success, result correctness, latency/cost,
correction burden, and cross-scope transfer. Do not pool the cohorts or call a
document-only win a skill-learning win.

The useful composition is:

```text
EnterpriseRAG-Bench question
  -> candidate evidence retrieval
  -> trace-shaped evidence/exposure record
  -> artifact/skill proposal
  -> independent replay in a changed environment
  -> promotion only if terminal and semantic gates pass
```

The benchmark supplies the first step and the hard-negative slices. Our pilot
contract supplies the last four steps. A FrankenGate-generated variant should
add tool/API artifacts, session IDs, source exposure states, schema/authority
epochs, and known-good versus rejected actions while retaining the original
question categories.

The first executable trace-side bridge is now recorded in the
[`ontology/action projection receipt`](../results/ontology-action-trace-projection-cohort-2026-08-02.json).
On the pinned WMH-BIRD proxy, schema-first typed identifiers (A1/A7) raised
strict table MRR from 0.8050 (A0 lexical) to 0.9525 and recall@1 from 0.7083 to
0.9167 over 72 held-out tasks. Provenance/alias edges alone (A2) reached only
0.8472 MRR; combining them with typed identifiers (A3) reached 0.9464. The
result is encouraging for schema-first projections, but it is *not* evidence
of corporate ontology quality: all labels are SQL table references from one
public task family, and the receipt explicitly marks authority safety, human
intent, semantic skill transfer, and corporate alias quality as unestablished.
The vector, authority-constrained, and frontier arms remain unavailable rather
than being inferred from this proxy.

## Minimal empirical sequence

1. **Retrieval baseline:** run BM25/lexical, pgvector dense, identifier-aware
   term expansion, and frontier reranking on the 500 core questions. Freeze
   per-category receipts, not just an overall score.
2. **Metadata and safety:** run `extra_questions.jsonl` with explicit scope and
   ACL filters; measure leakage and false-positive retrieval separately from
   answer quality.
3. **Conflict/temporal slice:** add document validity intervals and authority
   labels; test whether structured predicates beat vector similarity on stale
   and conflicting facts.
4. **Trace augmentation:** attach retrieved evidence and exposure/rejection
   events to synthetic tool trajectories, then run our artifact and skill arms.
5. **Replay gate:** only promote a mined artifact or skill when an independent
   changed-environment replay succeeds. Keep a no-skill and formatting-placebo
   arm.
6. **Real-data handoff:** repeat the exact matrix on an authorized internal
   cohort. Until that exists, the result remains a public retrieval benchmark
   and a synthetic integration test.

## Relationship to newer reliability work

[LayerRAG-Bench](https://arxiv.org/abs/2607.27353) is a useful complement: it
focuses on cross-layer agentic-RAG failures such as schema drift, stale
evidence, missing tool output, denied permissions, and wrong-session context.
Those failure classes are closer to our authority/epoch/replay problem than
EnterpriseRAG-Bench alone. We should borrow its fault matrix for the trace
augmentation, while retaining EnterpriseRAG-Bench for broad document retrieval
and question coverage.

## Decision

Adopt EnterpriseRAG-Bench as the **document retrieval and hard-negative
fixture**, not as a trace-learning or skill-improvement benchmark. It is worth
running because it can tell us whether our lexical/dense/frontier/metadata
cascade finds the right evidence under enterprise-like clutter. It cannot tell
us whether Frankengate makes people or agents better. That claim remains gated
on the authorized changed-system replay study already captured in
`enterprise-trace-learning-pilot-v1.json`.
