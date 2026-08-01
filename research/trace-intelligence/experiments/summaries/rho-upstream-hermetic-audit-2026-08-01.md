# RHO upstream hermetic audit (2026-08-01)

The pinned `wbopan/retro-harness` source at commit
`e5f2d1a8a06ab3523ab42e0042d2fa13d9acb701` was installed in an isolated `uv`
environment and exercised without LLM calls, Docker, or external benchmark
data.

The complete hermetic suite produced **294 passed, 6 failed, 1 collection
error, and 1 skipped**. The failures are retained as typed upstream/runtime
findings:

- `test_azure_auth`: repository default URL is a placeholder rather than the
  Foundry URL asserted by the test;
- `test_codex_agent_no_subprocess`: the test assumes `/bin/true`, which is not
  present on this macOS host;
- three GAIA-2 dataset tests fail closed because the required
  `RHO_GAIA2_ENABLE_JUDGE=1` opt-in is absent;
- `test_gaia2_sidecar` imports `_DEFAULT_JUDGE_MODEL`, which is missing from the
  current sidecar module; and
- the WebUI fixture creates a run directory that the `/api/runs` implementation
  does not return.

A targeted core-mechanics slice covering DPP selection, ReasoningBank storage
and retrieval, primitive evaluation/optimization, and harmful/no-op promotion
gates passed **29/29**. This is strong evidence that the local RHO mechanics
are executable, but it is not a reproduction of the paper's held-out efficacy
numbers or a Frankengate integration.

Machine-readable receipt:
[`rho-upstream-hermetic-audit-2026-08-01.json`](../results/rho-upstream-hermetic-audit-2026-08-01.json).
