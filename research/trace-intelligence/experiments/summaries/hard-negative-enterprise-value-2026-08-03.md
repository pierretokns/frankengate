# What the paper reproduction buys Frankengate

## The narrow question it can answer

Given a query and a known-good page/artifact, does a diverse encoder ensemble
find a *nearby but wrong* candidate that is useful for training a reranker?
The reproduction makes that question falsifiable by comparing the paper's
two-inequality selector against random, lexical/BM25, single-encoder, and
modern-model controls under the same candidate pool and training budget.

It does **not** directly answer who is doing similar work, what skill a person
is missing, or what a team should learn. Those are downstream analyses. This
method supplies one high-value primitive for them: reliable contrastive
examples in which the wrong result is plausibly relevant, not an arbitrary
unrelated document.

## Enterprise mapping

| Enterprise question | Contribution of this method | Additional component required |
| --- | --- | --- |
| Find reusable SQL/tool artifacts | Mine a prior artifact that is semantically close but wrong, then train/evaluate against the accepted artifact | Artifact registry, execution/outcome labels, schema/version metadata |
| Detect repeated user friction | Turn failed/rephrased attempts into query-positive and hard-negative pairs | Trace friction detector and intent reconstruction |
| Find people doing similar work | Improve retrieval of equivalent task traces despite different wording | Session/task clustering, identity and time joins |
| Suggest missing skills | Retrieve validated examples and contrast them with the user's failed path | Skill taxonomy, gap classifier, human review |
| Build evals from history | Convert accepted/rejected artifacts into regression cases with adversarial distractors | Replay harness, deterministic fixtures, evaluator and promotion policy |
| Adapt embeddings to a company | Produce hard negatives for contrastive/domain adaptation training | Curated aliases, collision labels, held-out changed-system cohort |

## Maximum upside

If the selector plus triplet-trained reranker wins on enterprise-like,
family-disjoint slices, the upside is substantial: every accepted SQL query,
tool trajectory, runbook, or answer can generate a compact regression/eval
case with a realistic failure neighbor. That can improve artifact reuse,
friction diagnosis, skill recommendations, and domain-embedding training with
one shared data primitive. It also gives us a principled test of whether the
six-model ensemble is buying anything over a single modern embedding model.

## Why it is worth pursuing, but not as a production dependency yet

The implementation is now close enough to run the actual algorithm on public
fixtures, and five of the six exact checkpoints execute on CPU. The remaining
unknowns are the ones that determine value: selection rate, false-negative
rate, reranker lift, transfer across task families, and cost. We should spend
one bounded evaluation cycle on those gates. If it does not beat a modern
single encoder plus lexical hard negatives on enterprise slices, we should
drop the ensemble and keep only the evaluation methodology. If it wins, it
becomes a trace-to-eval/artifact-mining service rather than a generic vector
search feature.

The current evidence is therefore: **high strategic upside, no production
claim yet**.
