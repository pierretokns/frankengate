# RHO frontier LOCOMO reproduction

Pinned upstream `wbopan/retro-harness` at `e5f2d1a8a06ab3523ab42e0042d2fa13d9acb701`
and ran one upstream `rho evolve` diagnosis round through the Codex
subscription-backed `gpt-5.6-luna` harness on `locomo10.json`.

The run used two train tasks, one optimizer sample, three trajectories per
diagnosis task, and two held-out tasks. RHO accepted one candidate at its
self-preference gate with mean score `1.0`. The independent no-harness control
was then run on the same held-out task IDs using the upstream LOCOMO scorer.

| Arm | Mean score | Tasks | Regressions |
| --- | ---: | ---: | ---: |
| No harness | 0.703 | 2 | — |
| RHO candidate | 0.511 | 2 | 1 |

The candidate delta was `-0.192`; it is not eligible for Frankengate
promotion. This is a small, bounded negative efficacy slice, not a universal
claim that RHO cannot work. It does establish that RHO self-preference is not a
sufficient utility signal for our release gate.

Raw RHO runs remain outside the repository. The machine-readable receipt keeps
only hashes, task IDs, scalar scores, and claim boundaries.
