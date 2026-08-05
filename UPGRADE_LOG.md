# Dependency Security Upgrade Log

**Date:** 2026-08-05  |  **Scope:** Go and user-facing JavaScript dependencies

## Summary

- Removed test-only Python SDK dependencies from this remediation scope.
- Updated vulnerable Go module pins across the workspace and examples:
  `google.golang.org/grpc` to `v1.82.1` and `github.com/buger/jsonparser` to `v1.1.2`.
- Updated user-facing JavaScript lockfiles and overrides for the reported high/critical advisories, including Axios, MCP SDK, `fast-uri`, `ip-address`, `path-to-regexp`, `brace-expansion`, `js-yaml`, and PostCSS.
- Local npm advisory checks report **0 high** and **0 critical** findings in every changed JavaScript lockfile.

## Verification

- `go mod verify` passed for `tests/scripts/1millogs`.
- The repository Go compile/race lane passed compilation and focused race tests until the Docker recorder contract; that test is blocked locally because the Docker wrapper delegates to an unavailable Podman binary.
- Local npm audit checks passed the high/critical threshold for `ui`, all changed MCP example servers, and the TypeScript integration.
- Go vulnerability scanning could not run on this macOS runner because the repository wrapper's scanner binary has an invalid Mach-O `LC_UUID` and a separately installed scanner fails during Go package loading. Run the vulnerability lane on Linux/CI before merge.

## Deliberately excluded

The Python integration is CI-only SDK compatibility coverage, not part of the FrankenGate runtime or shipped package. Its lockfile was intentionally left unchanged for this Go/user-facing security pass.
