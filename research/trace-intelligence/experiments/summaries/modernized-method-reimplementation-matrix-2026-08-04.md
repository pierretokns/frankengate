# Modernized method reimplementation matrix

The older papers and repositories are useful as hypotheses, but their original
software is often stale, model-dependent, or tied to a different dataset. This
matrix separates current-tool execution from efficacy evidence.

| Concept | Current implementation/evidence | Current status | Correct next dataset/test |
|---|---|---|---|
| AgentRx failure localization | Pinned upstream static stage executed on seven Tau trajectories; IR conversion passed, but static artifacts covered 0/10 labeled failures. A repaired ablation covered 3/10 with false positives. | Mechanics/representation blocker; full method untested | Agent trajectories with dynamic invariants, blinded decisive-step labels, and full generation/judge arms |
| Signals detectors | Current deterministic signal chain and changed-system tests pass mechanics; labels and outcome calibration remain absent. | Detector mechanics only | Complete trajectories with corrections, abandonment, terminal outcome, and human friction labels |
| AgentEvals | Upstream `agentevals-cli==0.9.7` interoperability is pinned and tested on stored traces; it scores traces but does not rerun tools or agents. | Reproduced evaluator mechanics | Tool-rich trajectories with independent side-effect/outcome verification and changed-system replay |
| SkillGen | Pinned upstream mechanics compile; persistence, routing, and paired promotion gates pass. No held-out efficacy run. | Mechanics reproduced | Replayable agent tasks with before/after trajectories, family/time holdouts, and negative-transfer controls |
| RHO/ReasoningBank | Hermetic upstream run had 294 pass, 6 fail, 1 collection error; targeted mechanics slice passed 29/29. No paper-efficacy replication. | Mechanics reproduced; runtime findings recorded | Current frontier/local harness with real task outcomes and fixed cost/horizon |
| Term extraction | GLiNER and Termolator run on the 49-document Wisp cohort; both remain candidate generators. | Modern candidate pipeline only | Reviewed enterprise spans, aliases, NILs, temporal replacements, and retrieval lift |
| TermSuite | 3.0.10 CLI requires external TreeTagger/Mate models unavailable in the environment. | Setup-blocked, not disproven | Pinned container/model bundle, then same corpus and blinded labels |
| AcronymExpansion | Cited repository requires a 2017 dependency stack and trained Doc2Vec model; no pretrained model. | Setup-blocked, not disproven | Reproducible legacy environment plus training corpus, or modern rule-based replacement as a separate arm |
| QueryGym/ConvGQR/SIRA | Transparent proxy fixture improves lexical omissions, but is not an implementation replication. | Mechanics-only proxy | Real implementations on reviewed reformulation chains and same-scope hard negatives |
| LangMem/Graphiti/Memory Palace-style memory | Current Frankengate projections preserve evidence, validity, provenance, and influence exclusion; prior natural memory arms were model/protocol sensitive. | Architecture/mechanics supported; utility open | Multi-session traces with query-independent release, deletion, time/user holdouts, and prospective outcome replay |

## Modernization rule

An old implementation is never silently upgraded and called equivalent. Each
row needs a concept receipt, a pinned current implementation receipt, and a
fit-for-claim dataset receipt. A mechanics pass cannot be promoted to efficacy,
and an upstream setup failure cannot be reported as a negative result.
