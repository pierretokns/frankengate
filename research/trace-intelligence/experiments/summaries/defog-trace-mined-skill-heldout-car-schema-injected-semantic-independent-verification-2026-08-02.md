# Independent semantic verification: schema-injected car replay

The verifier ran against a fresh governed PostgreSQL executor, not the
runner's stored outcome booleans. It re-executed the two submitted candidates
from each arm and compared their values with independently executed sealed gold
alternatives.

| arm | tasks | stored correct | recomputed correct | candidate errors | mismatches |
| --- | ---: | ---: | ---: | ---: | ---: |
| no-skill | 6 | 1 | 1 | 0 | 0 |
| formatting placebo | 6 | 1 | 1 | 0 | 0 |
| trace-mined terminal discipline | 6 | 1 | 1 | 0 | 0 |

All 18 rows matched. The security/protocol verifier separately passed all raw
audit and authority checks. Raw prompts, SQL, rows, and verifier audit events
remain external; only aggregate counts and hashes are committed.
