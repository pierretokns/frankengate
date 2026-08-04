# Independent verification: Defog held-out car replay

The external raw audit directory for the six-task car replay was independently
checked against the committed aggregate receipt. All 18 task/arm files were
present and matched their recorded SHA-256 hashes. The verifier rebuilt every
attempt-receipt chain, checked task/arm identity, authority and epoch
invariants, policy-status consistency, terminal-tool scheduling, fallback
flags, and unauthorized-observation flags.

| check | result |
| --- | --- |
| raw audit files | 18/18 |
| raw hashes and receipt chains | pass |
| authority/epoch invariants | pass |
| unauthorized observations | 0 |
| policy and terminal scheduling | pass |
| aggregate-to-raw consistency | pass |
| semantic recomputation | not run |

Semantic recomputation is intentionally not claimed: the disposable PostgreSQL
executor used for the original run is not currently available. The verifier
therefore authorizes only the security/protocol result, not the stored
`semantic_correct` booleans. Raw prompts, SQL, rows, and messages remain
external and are not committed.
