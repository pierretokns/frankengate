# AgentRx independent static-stage audit (2026-07-31)

This run executed the pinned upstream AgentRx source at commit
`f228165bfec60a801fd5fedd9d8ffe0f9de0c69d` against its seven bundled Tau
retail trajectories and bundled ground-truth labels. The upstream IR
converter validated all seven trajectories. The upstream `AllVerifier` then
ran with the bundled `static_tau.json`, with NL checks disabled and no dynamic
invariant files loaded.

| Measure | Result |
|---|---:|
| Valid IR trajectories | 7/7 |
| Ground-truth failure steps | 10 |
| Failure steps covered by a static trigger | 0/10 |
| Static checker violations | 0 |
| Trajectories with any static trigger | 0/7 |
| Python invariant snippets compiling successfully | 0/8 |

This is a faithful upstream execution, but it is deliberately only a
static-stage compatibility/coverage audit. It does **not** evaluate AgentRx's
LLM invariant generation or judge, and it does not claim that AgentRx's full
method is ineffective. The result does establish that the supplied static
artifact, without dynamic invariants, cannot localize any of the labeled
failure steps in this bundled Tau cohort. A full efficacy test therefore must
run static and dynamic generation, retain the generated artifacts, and compare
the judge's step/category output against blinded ground truth.

The immediate mechanical cause is observable in the receipt: all eight bundled
static invariants use `event_trigger.step_index = 1` and `role_name = assistant`,
while the normalized Tau IR begins with a system step at index 1 and places
assistant/tool events later. The checker therefore skips every static
invariant before evaluating any Python check. This is an upstream artifact/
representation compatibility issue to resolve before interpreting static
checker scores.

There is a second independent failure mode: all eight bundled Python invariant
snippets fail Python compilation (`SyntaxError` at line 2, generally from a
malformed doubled quote in the generated docstring). A trigger-repaired
ablation therefore still produces no violations because the checker catches
these exceptions and returns no `Violation`. The artifact is unsuitable for
efficacy scoring until invariant code generation and exception handling are
repaired and re-verified.

Machine-readable receipt:
[`agentrx-independent-static-audit-2026-07-31.json`](../results/agentrx-independent-static-audit-2026-07-31.json).
