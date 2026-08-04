# FastContext withdrawn-method audit (2026-08-09)

## Source status

[FastContext: Training Efficient Repository Explorer for Coding Agents](https://arxiv.org/abs/2606.14066)
was submitted in June 2026 and describes a dedicated repository-exploration
subagent. The abstract claims that it:

- separates exploration from solving;
- issues parallel tool calls and returns concise file paths and line ranges;
- bootstraps smaller explorers from strong reference-model trajectories;
- refines them with task-grounded rewards for broad search, evidence gathering,
  and citation precision; and
- improves end-to-end resolution by up to 5.5% while reducing token use by up
  to 60% on several coding benchmarks.

However, the arXiv record explicitly marks the paper **withdrawn** because of
product-IP issues and says the withdrawn version has no license. Its linked
repository, `github.com/microsoft/fastcontext`, currently returns 404. There is
therefore no admissible code, license, stable release, or independently
reproducible result to fork or promote.

## Exact match versus usable evidence

| Claim | Status for Frankengate |
|---|---|
| Separate exploration from task solving | Strong design hypothesis; compatible with our trace-to-artifact architecture. |
| Learn exploration from successful trajectories | Adaptable, but no FastContext implementation or released training data is available. |
| Task-grounded rewards improve enterprise artifact reuse | **Untested.** The withdrawn abstract reports coding benchmark results, not governed SQL/tool replay. |
| Smaller exploration model can replace frontier reasoning | **Not established.** Any such test needs a frontier teacher, cost accounting, and independent replay. |
| Claimed 5.5% / 60% gains | **Not evidence we can cite as a Frankengate result.** The source is withdrawn and the claims have no available verifier. |

## Safe adaptation

The concept is worth a controlled future arm, independent of the withdrawn
paper:

1. train or prompt a small explorer to return candidate artifact/tool IDs and
   evidence spans, not free-form answers;
2. compare it with integrated-agent exploration, exact/identifier retrieval,
   and a frontier teacher;
3. measure candidate coverage, evidence grounding, context tokens, latency,
   and cost;
4. require scope/authority filtering before exposure; and
5. score the resulting artifact through independent replay on both current and
   changed systems.

The explorer should be trained only from candidates that were exposed and later
consumed successfully. “Not selected” is not a negative without a refusal or
redundancy reason. Same-surface/wrong-system, temporal, stale-authority, and
NIL cases must be held out separately.

This is a direct next arm for [artifact reuse #119](https://github.com/pierretokns/frankengate/issues/119),
[embedding/model cascades #122](https://github.com/pierretokns/frankengate/issues/122),
and the changed-system causal cohort [#118](https://github.com/pierretokns/frankengate/issues/118).
It must remain a **proposal**, not a fork or production dependency, until a
licensed implementation or our own independently reproducible version exists.

## Decision

Do not cite FastContext's numerical gains as established evidence, do not clone
or fork the unavailable repository, and do not add a dependency. Preserve the
separation-of-exploration concept in the experiment matrix because it directly
tests whether cheap targeted context acquisition can outperform either raw
embeddings or repeated frontier exploration.
