# Ontology-induction prior-art refresh

Date: 2026-08-02  
Status: literature and implementation fit audit; no efficacy claim

## New adjacent methods

### Generative Ontology Induction (GOI)

[GOI](https://arxiv.org/abs/2607.16201) is the closest recent paper to the
one-shot claims circulating on social media. It proposes a typed generative
blueprint containing entities, dimensions, properties, relationships, and
constraints, then exports a graph-shaped YAML/JSON representation. Its
controlled validation reports 95–100% structural-backbone coverage across four
contrasting ontologies, while a generic three-field prompt drops to 52.2% on a
job-description ontology, 62.2% on a clinical-visit ontology, and 78.3% on a
professional-services-contract ontology.

This is useful evidence that schema-aware decomposition is better than a
generic “list the concepts” prompt. It is not evidence of a correct corporate
ontology: the reported evaluation is controlled and ontology-structured, not a
real employee trace corpus with unresolved aliases, temporal replacements,
authority, NIL cases, or changed-system outcomes. Structural coverage can be
high while entity identity and business semantics are wrong.

**Frankengate adaptation:** implement GOI as a proposal arm after deterministic
identifier/schema extraction. Require every proposed node/edge to carry source
spans, confidence, temporal validity, and an explicit `unknown/needs-review`
option. Evaluate exact identity, relation evidence, NIL/ambiguity, and replay
utility separately from structural coverage. Do not make GOI output a canonical
write path.

### OntoGPT / SPIRES

[OntoGPT](https://github.com/monarch-initiative/ontogpt) remains a strong
open-source implementation for ontology-grounded extraction. Its SPIRES
workflow uses structured prompts and recursive extraction, and its CLI can
target multiple model providers. The current release line is `v1.1.1`.

Its key boundary is important: OntoGPT is primarily an ontology *population*
and grounding tool. It works best when a target ontology or LinkML template
already exists. It therefore complements GOI but does not solve the discovery
problem. It is a good independent arm for “can a proposed corporate schema be
populated faithfully?” and a poor arm for “infer the canonical schema from a
single tool or raw log.”

## Revised tool matrix

| stage | best-fit method | required gate |
|---|---|---|
| candidate mentions and aliases | deterministic term/identifier mining, GLiNER/Termolator | scoped candidate queue; no automatic identity |
| schema proposal | GOI or a constrained frontier prompt | typed schema, source evidence, NIL/unknown, versioned draft |
| schema population | OntoGPT/SPIRES with a fixed starter schema | span/edge provenance and conformance checks |
| identity resolution | reviewed pair labels plus active-learning resolver | match / non-match / NIL / unsure; temporal and scope splits |
| graph validation | SHACL-like shapes and contradiction checks | fail-closed validation report |
| operational truth | replay and authority/epoch gate | changed-system outcome, authorization, independent verifier |

The new sources strengthen the existing conclusion: the missing capability is
not another single ontology generator. It is a governed loop that joins
proposal, identity resolution, temporal/authority semantics, evidence, and
executable validation. The appropriate empirical comparison is GOI-only,
OntoGPT-with-starter-schema, and the staged Frankengate pipeline—not a single
graph-density or structural-coverage leaderboard.

## Evidence boundary

No current receipt proves that GOI, OntoGPT, GraphRAG, or OntoEKG can discover
Frankengate's real corporate aliases or safely promote ontology edges. The next
partner cohort must include two independent identity labels, same-surface
wrong-system negatives, temporal replacements, NIL/unclear cases, and a
changed-system replay endpoint. Until then these tools remain proposal and
population components, not enterprise truth sources.
