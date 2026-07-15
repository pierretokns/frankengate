# Agentic Flywheel Safety Profile

Status: proposed; not installed into user-level Codex configuration
Date: 2026-07-14

## Decision

Use a named Codex profile for this project. Keep filesystem writes inside the workspace
and require the user to approve sandbox escapes and state-changing orchestration. Do
not use `danger-full-access` plus `approval_policy = "never"` as the normal operating
mode. DCG is defense in depth, not a sandbox or authorization system.

Suggested `~/.codex/bifrost-flywheel.config.toml`:

```toml
approval_policy = "on-request"
approvals_reviewer = "user"
sandbox_mode = "workspace-write"
web_search = "cached"

[sandbox_workspace_write]
network_access = false

[shell_environment_policy]
inherit = "core"
ignore_default_excludes = false
exclude = ["AWS_*", "AZURE_*", "GCP_*", "*TOKEN*", "*SECRET*", "*PASSWORD*"]
```

Launch it with `codex --profile bifrost-flywheel`. Enable network for a particular run
or approve a specific escape when research or package acquisition requires it. Prefer
destination-constrained network policy when supported by the required tools.

## Command-rule policy

Codex command rules belong in a `.codex/rules/*.rules` layer, not in `config.toml`.
Project rules load only for a trusted project. Rules must match a concrete argv prefix
and carry positive and negative test cases. The proposed policy is:

- allow narrow read-only commands such as version, help, status, list, show, doctor,
  verify, graph inspection, and safety simulation;
- prompt for NTM spawn/send/interrupt, JSM install/update/sync mutations, Beads writes,
  cloud/Kubernetes changes, Git publication, dependency installation, and release work;
- forbid bypass flags, destructive filesystem/Git/database operations, credential
  extraction, and permission weakening unless a separate human-controlled recovery
  procedure explicitly requires them;
- never allow an entire dispatcher or interpreter prefix (`ntm`, `jsm`, `bash`, `zsh`,
  `python`, `node`, `cargo`, `go`, `kubectl`, `helm`, `aws`, `docker`, `terraform`).

Owner exception recorded 2026-07-14: all `ntm` and `jsm` subcommands are blanket-
allowed in the trusted Bifrost project rule layer. The owner explicitly accepted that
both dispatchers may perform arbitrary state-changing orchestration outside the sandbox.
This supersedes the narrower NTM/JSM recommendation above; every other dispatcher
remains approval-gated.

Every rule is tested with `codex execpolicy check` before activation. Compound shell
commands, redirections, substitutions, environment assignments, and wrappers must not
inherit trust from an allowed inner command.

## DCG policy

Enable and test only packs relevant to this repository: core filesystem/Git, strict
Git, PostgreSQL/SQLite, Kubernetes/Helm/Kustomize, Docker, AWS, Terraform, GitHub and
secret-management patterns. Maintain no broad allowlist. Validate project-specific
false positives with `dcg test` and inspect proposed actions with `dcg explain`.

DCG's documented resource-budget/timeout behavior can fail open, so independent
controls remain mandatory: Codex sandbox and approvals, least-privilege cloud and
Kubernetes roles, short-lived credentials, protected branches/environments, signed
artifacts, deployment canaries, and two-person production release approval.

## NTM/JSM operating protocol

Before orchestration, capture versions, capabilities, health, agent/session state,
leases, reservations, and an explicit action plan. Use robot/machine-readable surfaces
and verify resulting state after every mutation. Agents reserve overlapping files or
Beads scopes before editing. Destructive or production-affecting actions use NTM safety
simulation and an independent approval surface where available.

JSM updates are supply-chain changes. List candidates, inspect provenance/diffs and
integrity, update a bounded set, run its validation, and record the resolved versions.
An empty or unauthenticated update response is not evidence that skills are current.

## Verified local state 2026-07-14

- NTM was updated from 1.18.3 to 1.19.1. Its health report is usable, but Agent Mail,
  CASS, `ru`, and `ubs` fail their health checks and several optional tools are absent.
  These are not launch dependencies for the gateway. `s2p` and `xf` became healthy
  after the update.
- JSM 0.3.11 authenticated and reconciled 18 saved skills. It updated the DCG skill to
  v5; the other saved skills were already current. Catalog relationship endpoints and
  the initial upgrade check returned inconsistent authentication errors and need a
  reproducible diagnostic before relying on them for skill selection.
- `jsm tools update --yes` updated all 16 installed tool entries successfully. Material
  version changes included BV 0.18.0, CAAM 0.1.12, CASS 0.6.22, CM 0.2.12, DCG 0.6.6,
  Source2Prompt 0.3.4, and NTM 1.19.1. Several upstream installers contained nested
  `curl|bash` patterns flagged by JSM; success is not a substitute for provenance and
  post-install verification.
- `br` and `bv` are healthy. Graph triage found 136 open issues, 35 actionable issues,
  101 dependency-blocked issues, and no cycles. It ranked the OSS/enterprise seam matrix
  as the highest-impact first task.
- NTM safety simulation allowed the proposed JSM update, NTM planning spawn, and Git
  status steps through implicit no-policy matches. That result is evidence of current
  policy behavior, not proof those actions are intrinsically safe.
