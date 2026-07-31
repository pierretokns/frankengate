# CRMArena recorded-trace replay (2026-07-31)

The pinned `experiential-labs/wmh-crmarena-traces` training traces were replayed
against the official SalesforceAIResearch CRMArena SQLite org dump. The runner
is `research/trace-intelligence/crmarena_trace_replay.py`; the aggregate receipt
is `experiments/results/crmarena-trace-replay-2026-07-31.json`.

## Receipt

- All 80 trace metadata records were loaded.
- 468 recorded SQL tool calls were extracted from the native shell commands.
- 420 replayed tool results matched the recorded JSON result exactly.
- 20 replayed JSON results differed from the recorded result.
- 28 observations were not complete JSON (truncated “showing first 50 rows”,
  concatenated output, or plain-text answers) and are explicitly classified as
  non-replayable rather than scored as failures.
- 85 tool results were schema/setup/non-query operations and were not treated as
  SQL result comparisons.

## Interpretation boundary

This closes a bounded replay check for CRMArena's captured SQL interactions. It
does not establish skill improvement, causal memory utility, natural enterprise
prevalence, or commercial training rights: the corpus is one CRM organization,
CC-BY-NC-4.0, and its OTel spans lack real parentage and latency. The incomplete
observations are a measured format-loss boundary, not zero-quality outcomes.
