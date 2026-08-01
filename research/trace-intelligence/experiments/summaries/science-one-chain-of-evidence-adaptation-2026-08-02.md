# Science One / Chain-of-Evidence: adaptation for Frankengate trace research

**Reviewed:** 2026-08-02  
**Primary source:** [Google Research: Science One Framework](https://research.google/blog/science-one-framework-a-verifiable-autonomous-research-framework-via-chain-of-evidence/)  
**Paper:** [ScientistOne, arXiv:2605.26340](https://arxiv.org/abs/2605.26340)

## What the framework actually contributes

Science One is an autonomous research prototype, not a corporate trace miner,
embedding model, memory store, or skill optimizer. Its important architectural
contribution is to make evidence provenance an input/output contract rather
than a post-hoc citation pass:

1. A literature-grounding investigator builds a citation graph from a scholarly
   API and full-text papers.
2. An isolated explore/exploit discovery engine runs candidate implementations
   against a task evaluator and retains raw evaluator outputs.
3. A paper writer emits claim records whose evidence tags point to concrete
   workspace artifacts; a claim verifier reconciles claims that exceed their
   evidence.

The post-hoc CoE Audit then independently checks four failure classes: score
reproducibility, specification violations, reference validity, and
method–code alignment. The Google post says the framework is an experimental
prototype, not a production-ready tool. The reported benchmark is 75 generated
papers across five systems-optimization tasks; the post reports zero phantom
references, fully verifiable scores, and the strongest method–code alignment for
Science One, while baselines reached up to 21% phantom references.

## Direct mapping to our trace/eval system

| Science One concept | Frankengate adaptation | Evidence we must persist |
|---|---|---|
| Claim with evidence tag | `insight`, `skill_candidate`, `eval_candidate`, and `enterprise_pattern` records | source trace IDs, span/turn ranges, artifact hashes, extractor version |
| Isolated discovery branch | one disposable DB/tenant/authority epoch per replay arm and seed | container image, schema hash, seed, model/harness, prompt and skill hashes |
| Raw evaluator record | immutable replay receipt, SQL/result validator receipt, tool-call receipt | exact evaluator output, exit code, timing, validator version |
| Score verification | independent semantic + security + authority re-run | verifier role, RLS state, gold artifact, replay inputs |
| Specification violation | check that a proposed SQL/tool artifact did not bypass schema, policy, or gold-answer constraints | query plan/allowlist, forbidden-table checks, policy decision |
| Reference verification | verify aliases, tools, skills, and source traces resolve to real retained artifacts | canonical IDs, source hashes, validity interval, deletion/tombstone state |
| Method–code alignment | compare skill/eval prose with the actually executed prompt, tool sequence, and implementation | normalized skill, rendered prompt, tool DAG, code/SQL hash |

This is directly relevant to the current artifact-reuse experiment: an
observed pass rate is not a promotable skill result unless it can be rerun from
the sealed task, and the released skill text matches the skill that was actually
injected. Separate databases are therefore not merely an operational detail;
they are part of the causal and provenance boundary.

## What it does **not** solve

Science One does not establish that a trace-mined artifact improves a new user,
discover hidden enterprise intent, learn a corporate embedding space, or infer
competence from repeated prompts. Its explore/exploit loop assumes a task
evaluator; our hard problems are often evaluator construction and latent intent
identification. Its literature API is unsuitable as a source of truth for
private corporate systems. LLM method–code alignment is a useful detector, but
not a substitute for deterministic SQL, tool-authority, or outcome validators.

The framework also does not prove independence automatically. A shared model,
shared database, shared prompt mutation, or leaked artifact can make an
apparently independent branch a correlated trial. We must record and audit the
isolation dimensions explicitly.

## Required Frankengate evidence contract

Every generated recommendation should be a typed record with:

```text
claim_id, claim_kind, tenant_scope, subject_scope,
evidence_refs[], evidence_hashes[], source_time_bounds,
extractor_version, model_and_harness, prompt_or_skill_hash,
replay_manifest, validator_refs[], confidence,
unknown_reason, reviewer_state, release_state
```

Release states should be monotonic (`candidate -> reviewed -> replayed ->
released -> superseded`) and never infer success from a prose explanation. A
claim with no sufficient evidence becomes `unknown/needs_user`, not a guessed
enterprise fact. This preserves individual-user privacy while allowing admins
to inspect the complete evidence chain for internal research.

## Next empirical gate

Add a CoE-style audit to the native/proxy artifact-transfer study, without
changing its treatment arms:

1. independently replay every arm from its sealed manifest;
2. verify semantic correctness, authorization, and no forbidden-table access;
3. verify that the injected skill text, model transcript, and claimed artifact
   are byte/hash aligned;
4. emit a claim-level receipt for each pass/fail and aggregate only after all
   receipts are present;
5. compare the same claim under shared versus disposable databases and under
   proxy versus direct native harnesses.

The result should be reported as artifact-transfer effect size plus evidence
integrity rates, not as a single “agent quality” score. Until balanced native
multiseed runs agree with the proxy runs, no trace-mined skill should be
promoted.

## Sources

- [Google Research announcement](https://research.google/blog/science-one-framework-a-verifiable-autonomous-research-framework-via-chain-of-evidence/)
- [ScientistOne paper](https://arxiv.org/abs/2605.26340)
- [ScientistOne project page](https://scientist-one.github.io/)
