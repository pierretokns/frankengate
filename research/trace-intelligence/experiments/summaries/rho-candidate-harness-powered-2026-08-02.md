# Powered RHO candidate replay (2026-08-02)

This is the fair follow-up to the bounded RHO reproduction. The upstream
optimizer ran one diagnosis round over eight train tasks and emitted candidate
`h_174d495ed2af`, but its self-preference gate rejected that candidate
(`accepted=false`, mean `0.0`). We nevertheless replayed the rejected candidate
independently on the same eight held-out LOCOMO tasks as the matched initial
harness control, using `gpt-5.6-luna` with high reasoning and the upstream
`score_qa` grader.

| Arm | Mean score | Tasks |
| --- | ---: | ---: |
| Initial-harness control (`h_c8c03d6d0938`) | 0.643 | 8 |
| Rejected RHO candidate (`h_174d495ed2af`) | 0.388 | 8 |

The paired delta was `-0.255`; the candidate won one task, regressed five, and
tied two. The deterministic bootstrap 95% interval for the mean delta was
`[-0.591, 0.025]`; the exact two-sided sign-test p-value was `0.219`. This is
negative bounded evidence with limited power, not a universal RHO rejection.
It is not eligible for Frankengate integration, and it confirms that a
self-preference gate cannot authorize promotion by itself.
