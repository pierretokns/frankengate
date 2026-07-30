# Trace2Skill governed Stage-0 smoke test

This is a one-task execution-safety and verifier-validity result, not a skill
quality estimate. SpreadsheetBench remains a cross-domain control; NL2SQL is the
primary enterprise replay domain.

| Arm | Pre-recalculation verifier | Post-recalculation verifier | Tool calls | Sandbox violations | Network attempts denied |
| --- | --- | --- | ---: | ---: | ---: |
| no_skill | pass | pass | 3 | 0 | 0 |
| human_skill | fail | pass | 12 | 0 | 0 |

Both arms passed after correct formula handling. The human-skill arm wrote a
formula whose cached value was absent, so the upstream data-only comparison
initially rejected it. LibreOffice recalculation changed that verdict from fail
to pass. A production experiment must therefore pin and run a calculation
engine before workbook comparison.

The sandbox executed real model tool calls with task-only writes, declared-root
reads, stripped API credentials, and network denial. No sandbox escape or
timeout was observed. Content-bearing commands, outputs, workbooks, and logs
remain outside Git; only aggregate counts and hashes are committed.

No skill benefit can be inferred from one task where both arms pass. The useful
result is the execution boundary and the discovery of a verifier failure mode.
