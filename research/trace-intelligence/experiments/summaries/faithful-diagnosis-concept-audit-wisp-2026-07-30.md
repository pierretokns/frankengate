# Faithful diagnosis-concept audit

**Run date:** 2026-07-30

**Result SHA-256:** `d82c5e0007106e9ae3e319d6d641691cc79ece00c2c79b1e03b7834d8069d454`

This run executes the local Signals and AgentRx concept proxies over the pinned Wisp corpus and audits OpenRCA input sufficiency. It does not claim upstream replication.

- Signals queue: 11 selected; 11 selected traces contain tool errors.
- Length baseline: 7 selected traces contain tool errors.
- Seeded random baseline: 2 selected traces contain tool errors.
- AgentRx-style hypotheses: 11; abstentions: 0; root-cause claims: 0.
- OpenRCA status: not_executable_on_source; metrics/topology/timestamps/environment snapshots are absent from this corpus.

The queue comparison is a screening description, not precision or recall: no independent informative-trace labels or task outcomes were available. A faithful OpenRCA trial requires an aligned OTel/log/metric/topology fixture and is therefore a separate blocked experiment, not a silent proxy.
