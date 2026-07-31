# Pinned full verification checkpoint (2026-08-01)

The complete research harness was run with the locked environment:

```text
uv run --frozen make verify
research tests: 504 passed, 13 explicit environment skips
NL2SQL tests: 61 passed, 0 skips
aggregate results: 97
dataset manifests: 44
governed fixtures: 12
raw corpus files committed: 0
compileall: passed
```

This is the strongest local reproducibility result. Skips are explicit host or
external-component gates; no skipped test is counted as a pass. It validates
the harness and aggregate artifacts, not the unresolved CMU, Aurora, or causal
enterprise-outcome requirements.
