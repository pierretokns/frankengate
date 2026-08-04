# Enterprise term-extraction and retrieval-enrichment protocol

**Protocol ID:** `enterprise-term-enrichment-v1`
**Date:** 2026-08-04
**Status:** proposed empirical extension

## Why this is a new test

The linked State of AI article identifies a vocabulary layer that the current
trace-artifact experiments do not measure directly. We currently preserve exact
identifiers and aliases when known, but we do not test whether mining internal
terms, acronyms, legacy names, and query reformulations improves retrieval or
cross-user clustering.

This is especially relevant to the Palantir/Semantica ontology arm: term
extraction supplies candidate names and relations, while the ontology layer
decides whether those candidates become typed, temporal, evidence-linked
objects. Extractors must never silently rewrite authoritative text.

## Tools worth testing

### Tier 1: run first

1. **TermoUD or Termolator** — interpretable candidate-span and termhood
   baseline. This gives us a non-LLM reference for unithood versus termhood.
2. **GLiNER** — few-/zero-shot span challenger for internal project, system,
   metric, acronym, process, and legacy-term labels.
3. **TermSuite** — variant and alias clustering, including morphological,
   syntactic, graphic, and semantic variants.
4. **Deterministic acronym patterns plus AcronymExpansion** — expansion
   candidates with explicit ambiguity/NIL outcomes.
5. **SEQUER-style reformulation mining** — learn original→rephrased pairs from
   user correction chains instead of guessing synonyms from frequency.

These five tools are enough to test the core hypothesis without adding a large
curation platform or a second database.

### Tier 2: add only after Tier 1 shows signal

- **QueryGym** for a reproducible comparison of keyword, pseudo-document,
  answer/entity, and corpus-feedback query expansion across BM25, dense,
  hybrid, and reranked lanes.
- **ConvGQR** for query-time conversational omission/reference resolution.
- **SIRA-style corpus enrichment** for search-only expansion fields after
  candidate approval.
- **Distilabel** for batched critique/disagreement sampling and reviewer queue
  generation; never as the authority for a canonical term.

### Tier 3: scale substrate, not a relevance intervention

**DataTrove, NVIDIA NeMo Curator, AI2 Dolma, and Data-Juicer** should be
benchmarked only for throughput, resumability, deduplication, stable IDs, and
cost on the raw corpus. They are orchestration/curation substrates, not proof
that terminology improves enterprise answers. Start with a local Python worker
and adopt one substrate only if the corpus-scale measurement requires it.

## Ablation matrix

Use the same authorized corpus, source bundle, holdout, and canonical trajectory
IDs. Do not expose held-out glossary labels to candidate generation.

| Arm | Added capability |
|---|---|
| T0 | Existing exact identifiers + FTS/vector baseline |
| T1 | TermoUD/Termolator candidates only |
| T2 | GLiNER candidates only |
| T3 | T1 + T2 consensus candidates |
| T4 | T3 + acronym candidates with NIL/unclear abstention |
| T5 | T4 + TermSuite alias/variant clusters |
| T6 | T5 + approved alias field in BM25/hybrid search |
| T7 | T6 + SEQUER-style user reformulation pairs |
| T8 | T7 + QueryGym/ConvGQR query-time expansion |
| T9 | T8 + Semantica/ontology typed edges and temporal validity |

Keep the original source text and exact identifiers in every arm. Enrichment is
an additional search field, never a replacement for source evidence.

## Required labels and metrics

Create a small blinded enterprise vocabulary set with project/system names,
metrics, acronyms, aliases, same-token/different-system collisions, legacy
names, and NIL cases. Hold out users, teams, projects, systems, and time.

Measure:

- span boundary precision/recall and candidate termhood precision;
- acronym expansion accuracy and ambiguity/NIL recall;
- alias-cluster purity and wrong-system-link rate;
- current-versus-legacy classification and stale-term exposure;
- relation precision with evidence-sentence coverage;
- retrieval Recall@1/3/10, MRR, nDCG, source-hit rate, and citation-span
  precision;
- query reformulation success on real correction chains;
- cross-user cluster purity and unauthorized-node/edge count;
- exact identifier/number/table retrieval regression;
- indexing cost, query latency, reprocessing cost, and reviewer acceptance.

## Promotion gates

Promote an enrichment lane only when it improves the preregistered retrieval or
cluster metric on the sealed holdout and does not increase wrong-system,
stale-term, ambiguity, citation, or authorization failures. A high-recall
extractor with poor alias purity remains a review-only candidate source.

An approved vocabulary record must contain the canonical term, aliases,
validity interval, scope, evidence references, owner/reviewer, confidence,
review status, and extractor/index revisions. The only automatic downstream use
is a search-only alias field; memory, skill, eval, or ontology promotion still
requires the existing evidence and action gates.
