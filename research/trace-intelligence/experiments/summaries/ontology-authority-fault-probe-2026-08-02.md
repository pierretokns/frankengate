# Ontology authority-gate fault probe

Date: 2026-08-02  
Status: synthetic policy-mechanics result; not an enterprise authorization claim

The WMH-BIRD traces do not contain principals, teams, tenants, policy epochs,
or reviewed authorization labels. To exercise the A5 gate without inventing
those labels, this probe assigns each held-out task a synthetic scope that
always permits its recorded target table(s) and a deterministic subset of
distractors. It then injects an alias edge to a non-permitted distractor and
compares unconstrained versus policy-filtered ranking.

## Result

Across 68 eligible fault cases (72 held-out tasks total), 68 unauthorized
edges were injected. The unconstrained ranking selected an unauthorized top-1
candidate in 16 cases. The constrained arm selected zero unauthorized top-1
candidates, filtered 243 candidates, and improved target recall@1 from 0.7353
to 0.8676. The run is deterministic on the pinned trace and manifest hashes.

This demonstrates the value of a fail-closed authority filter as a system
mechanic. It does **not** demonstrate real RLS behavior, policy-epoch
correctness, or enterprise safety: the scope is synthetic and target labels
come from public SQL references. Real promotion still requires principal/team
holdouts, policy epochs, stale/revoked edges, and independent authorization
verification.

Receipt: [`ontology-authority-fault-probe-2026-08-02.json`](../results/ontology-authority-fault-probe-2026-08-02.json)  
Runner: [`ontology_authority_fault_probe.py`](../../ontology_authority_fault_probe.py)
