# Trace Commons full-cohort content-minimized analysis (2026-08-02)

The 28-session `trace-commons/agent-traces-full-claude-memory-composition`
cohort was first attested against the pinned revision
`112ebd4d03ce852b00e935d523107c3d0c9a65bf`. Inventory, byte counts, record
counts, and SHA-256 values all matched: 57,104,737 bytes, 17,991 records,
4,264 tool calls, and 4,262 tool results. The attestation emitted no raw
content.

The content-minimized analyzer then ran the deterministic Frankengate ladder:

| Stage | Aggregate result |
| --- | ---: |
| S0 sessions / valid records | 28 / 17,991 |
| S1 signal candidates / review queue | 26 / 10 |
| S2 structured candidates / review queue | 27 / 10 |
| S4 temporal candidate episodes / sessions | 263 / 24 |
| S4 high / medium / low tiers | 107 / 73 / 83 |
| S6 eval-review records | 269 |
| S6 procedure-review episodes | 179 |
| S6 memory-review motifs / supporting episodes | 16 / 255 |
| Automatic memory or skill writes | 0 |
| Skill-gap or cross-user recommendations | 0 |

The full cohort has 269 explicit tool errors and 420 repeated tool-family runs.
The temporal constructor found a non-error follow-up for 97.77% of linked error
events; 68.44% of candidate episodes stayed within the same tool family. These
are structural selection proxies, not measured recovery precision: the source
has no independent task outcome, environment state, authorization/classification
labels, or stable multi-user relationship labels. Two orphan tool calls were
preserved as a quality signal.

The near-total overlap of S1, S2, and S4 (S1/S2 Jaccard 0.963; S1/S4 0.923;
S4/S6 1.0) is useful operationally: cheap signals can populate a bounded review
queue before richer episode reconstruction. It does not show that the selected
traces are more important or that a skill would improve them.

The result supports governed ingestion, controlled structural retrieval,
proposal-only eval/procedure queues, provenance, and explicit abstention. It
does not support automatic memory writes, skill-gap claims, cross-user matching,
model fine-tuning, or causal productivity/skill conclusions. Those require
human labels, outcome-bearing traces, multi-user consent, and prospective
intervention with independent evaluation.

Raw JSONL remains external and is not committed.
