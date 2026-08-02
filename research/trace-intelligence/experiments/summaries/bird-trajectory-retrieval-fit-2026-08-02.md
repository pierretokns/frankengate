# WMH-BIRD trajectory-retrieval supervision fit audit

## Result

The public WMH-BIRD export is **not exposure-complete** for a Cursor-style
trajectory-distilled retriever:

| Field | Observed |
| --- | ---: |
| step rows | 4,168 |
| task hashes | 222 |
| tool-result edges | 4,168 |
| raw span IDs | 4,168 |
| explicit candidate-exposure rows | 0 |
| search/open/retrieval action rows | 0 |
| stable principal/team/project/system fields | 0 |
| non-null reward fields | 0 |
| error observations | 7 |

Every action is a `bash` call. The corpus is excellent for recorded SQL/tool
trajectory replay and independent SQLite outcomes, but it does not record the
candidate set shown to the agent, later search/open behavior, stable identity or
scope, or a terminal reward. The audit therefore rejects a Cursor-equivalent
trajectory-supervision run rather than treating all unobserved artifacts as
negatives.

## Why this matters

The missing exposure set is not a cosmetic schema gap. Without it, a skipped
candidate may be irrelevant, unavailable, or never shown; those cases cannot be
used to train a retriever. Without stable identity and time/system scope, a
positive replay result cannot establish cross-user or cross-system transfer.
The independent SQL result is useful for validating a candidate after selection,
but it does not reconstruct the agent's historical retrieval decision.

## Decision

Use WMH-BIRD for:

- replay-backed artifact validation;
- structured/lexical/dense candidate-retrieval comparisons;
- trajectory-aware model judgment probes; and
- controlled regeneration and changed-schema experiments.

Do not use it as a trajectory-distilled embedding-training corpus until an
exposure reconstruction is separately justified. The next Cursor-style run
must use a trace source that records candidate exposure, search/open/relevance
events, principal/project/system/time scope, and independent terminal outcomes,
then pass the [exposure-aware supervision contract](trajectory-retrieval-supervision-contract-2026-08-02.md).

Receipt: [`bird-trajectory-retrieval-fit-2026-08-02.json`](../results/bird-trajectory-retrieval-fit-2026-08-02.json)  
Runner: [`bird_trajectory_retrieval_fit_audit.py`](../../bird_trajectory_retrieval_fit_audit.py)
