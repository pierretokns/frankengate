# Governed hypothesis reproducibility check (2026-07-31)

Both committed hypothesis experiments were executed again from the research branch. Their complete JSON outputs matched the recorded artifacts byte-for-byte after parsing, including result hashes.

| Experiment | Result hash | Match |
|---|---|---|
| Policy controls (conservative / pooled / none) | `9c03514a9af32f5799ca937e3ce1f8db70e1ba9f2ad96dc344c0390ac59c0e63` | yes |
| Resettable family-disjoint intervention replay | `01cb325436ecc69f580e1f6f19cd6851acfccbb9c53350388a1287bd117d98b3` | yes |

This closes a reproducibility risk in the local mechanics. It does not close the scientific gate: the experiments remain synthetic, without independent human adjudication, real trace outcomes, or changed-system enterprise replay.
