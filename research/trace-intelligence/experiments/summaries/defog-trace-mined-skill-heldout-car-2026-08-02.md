# Defog trace-mined skill held-out-car replay

This replay used six car-dealership tasks from the pinned enterprise cohort,
separate from the earlier four-task visible pilot. It ran the same Llama 3.2
loopback model, governed PostgreSQL executor, and three paired arms: no-skill,
formatting placebo, and trace-mined terminal discipline.

| arm | tasks | authority-valid | semantic-correct | successful SQL | terminal fallback | unauthorized observations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no-skill | 6 | 6 | 0 | 0 | 6 | 0 |
| formatting placebo | 6 | 6 | 0 | 0 | 6 | 0 |
| trace-mined terminal discipline | 6 | 6 | 0 | 0 | 6 | 0 |

The model exhausted the SQL protocol on every arm before producing a usable
candidate. This is a typed model/protocol null, not evidence for or against
semantic skill benefit. The authority and security path did execute: all 18
runs were authority-valid and had zero unauthorized observations. Raw prompts,
SQL, rows, and model messages remain in the external audit directory; only the
aggregate receipt is committed.

The next required run is protocol remediation followed by the same sealed
task schedule, independent semantic verification, and an independent security
verifier. No skill promotion is authorized.
