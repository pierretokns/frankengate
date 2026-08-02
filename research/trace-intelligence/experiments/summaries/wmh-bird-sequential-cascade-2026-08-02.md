# WMH-BIRD sequential ontology → frontier cascade

Date: 2026-08-02  
Status: completed, reproducible public proxy; not enterprise promotion evidence

This is the first same-run sequential test of the proposed architecture. On a
frozen 44-case cohort (11 database families, four deterministic evaluation cases
per family), Luna reviewed either the full exposed-table pool or the shortlist
produced by the recorded-schema/schema-first arm. The reviewer saw only the
question and table names: no SQL, replay result, target, or authority metadata.
Both arms made 44 calls (88 total), with zero call failures.

| arm | MRR | R@1 | compatible selected rate | invalid selected count | mean selected |
| --- | ---: | ---: | ---: | ---: | ---: |
| recorded schema-first | 0.9489 | 0.9091 | 0.4054 | 3.614 | 5.545 |
| Luna, full pool | 0.9659 | 0.9318 | 0.9167 | 0.250 | 2.091 |
| schema-first → Luna | **0.9773** | **0.9545** | 0.9167 | 0.250 | **2.045** |

The sequential arm improved over full-pool Luna by +0.0114 MRR and +0.0227
R@1, while selecting 2.045 rather than 2.091 tables on average. It matched
full-pool Luna's compatibility rate and invalid-selection rate. This supports a
small but real interaction effect: cheap recorded schema structure can remove
some distractors before frontier review, without reducing the reviewer's ability
to find a compatible target.

This does **not** establish that a corporate ontology was induced. The schema
terms were recorded DDL identifiers, not human-reviewed aliases; replay was
SQLite-only; there were no principals, policy epochs, changed schemas, human
intent labels, or independent enterprise outcomes. The finding is therefore an
implementation signal for a Frankengate cascade, not evidence that generic
ontology generators work on corporate data. The next decisive test requires a
semantic enterprise cohort with hard negatives, NIL/unclear labels, scope and
authority metadata, and changed-system replay.

Result receipt: [`wmh-bird-sequential-cascade-2026-08-02.json`](../results/wmh-bird-sequential-cascade-2026-08-02.json)  
Runner: [`wmh_bird_sequential_cascade.py`](../../wmh_bird_sequential_cascade.py)
