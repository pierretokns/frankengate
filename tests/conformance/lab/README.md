# Provider-neutral sealed CLI lab

This directory is the provider-neutral foundation for running pinned coding CLIs against three
gateway pods and deterministic service slots. Provider-specific Bedrock and Mantle doubles plug in
later; this layer makes no AWS-parity claim and contains no LocalStack or GitHub Models path.

Normal validation is offline:

```bash
GOWORK=off go test ./...
```

The committed contract currently proves:

- digest-pinned multi-architecture PostgreSQL, health-stub, CoreDNS, and prefetch bases;
- exact observed Codex and Claude Code npm tarballs plus registry integrity;
- three gateway services with PostgreSQL and no mounted `config.json`;
- synthetic zero-cost `file://` pricing and parameter fixtures so a fresh database can bootstrap
  without remote catalog traffic (these fixtures have no production pricing authority);
- three internal dual-stack networks, no published ports, no Docker socket, and hardened services;
- network-namespace keepers that remove IPv4 and IPv6 default routes, a fail-closed controlled DNS
  policy, and a dual-stack TCP/UDP forbidden-egress sentinel;
- separate digest-required Codex, Claude, and Bifrost runtime images;
- fresh quota-bounded `/cell`, `/tmp`, and gateway data tmpfs mounts;
- a static `cell-init` contract that clears inherited environment, validates strict scenarios and
  bounded/hash-bound seeds, admits only a fixed fake credential and internal gateway base URLs,
  runs only the expected read-only CLI binary, verifies the pinned semantic version from observed
  CLI output, bounds process lifetime, sends CLI output to stderr, emits one JSON evidence record to
  stdout, and removes cell residue;
- a Codex seed selecting `bedrock_mantle/gpt-5.6-sol` through `/openai/v1` with retries and updates
  disabled, and a Claude seed disabling updater, telemetry, error reporting, and nonessential
  traffic.

## Prefetch and runner builds

`Dockerfile.prefetch` is intentionally networked and must run in a separate project. Supply the
exact package/version/integrity triplet from `images.lock.v1.json`, export its `scratch` target to a
content-addressed offline directory, then destroy the prefetch project. `Dockerfile.runner` consumes
only that offline directory and the locally built static `cell-init`; its build must use
`--network=none`. The resulting per-platform images must be assembled into an OCI index and supplied
to Compose by digest as `CODEX_RUNNER_IMAGE` and `CLAUDE_RUNNER_IMAGE`. `BIFROST_IMAGE` is likewise
mandatory and digest pinned.

`Dockerfile.sentinel` similarly consumes only the locally compiled static sentinel binary. Build it
with `--network=none`, assemble its per-platform OCI index, and pass its digest as
`EGRESS_SENTINEL_IMAGE`.

Before Compose interpolation, the isolated build stage must write a
`sealed-lab-runtime-lock/v1` document. The lock contains exactly the Bifrost, Codex runner, Claude
runner, and egress-sentinel OCI references, each digest pinned and carrying observed
`linux/amd64` and `linux/arm64` platform rows. It also binds the SHA-256 of
`images.lock.v1.json` and repeats the exact client version for each runner. The
`contract.DecodeRuntimeLock` validator rejects a floating, incomplete, reordered, source-lock
mismatched, version-mismatched, or single-platform runtime set and produces the only four image
environment variables accepted by the lifecycle runner. Declaring the platform rows is not itself
proof that those manifests or native executions exist; the live runner must inspect and execute
them before the bead can close.

The lifecycle entry point accepts absolute, reviewed inputs and emits a single raw JSON result:

```bash
GOWORK=off go run ./cmd/lab-runner \
  --runtime-lock /absolute/path/runtime-lock.json \
  --source-lock /absolute/path/images.lock.v1.json \
  --compose /absolute/path/compose.yaml \
  --docker /absolute/path/to/docker
```

It inspects the actual OCI indexes for both required architectures, validates resolved Compose,
starts the core topology, executes fresh Codex and Claude version cells, rejects residue or any
sentinel event, removes containers and volumes, and proves the project inventory is empty. The
external orchestrator passes only reviewed Docker connection variables; proxy and cloud/provider
credentials are discarded and none of its HOME or Docker state enters a runner container. This
version-cell result is a raw lab record, not the canonical release evidence defined by the next
bead.

The binary placed at `offline/egress-sentinel` must be a Linux binary for the target platform; a
plain host `go build` on macOS produces an unusable Mach-O file. Build each native row explicitly:

```bash
GOWORK=off GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o offline/egress-sentinel ./cmd/egress-sentinel
docker build --network=none --platform=linux/amd64 -f Dockerfile.sentinel .

GOWORK=off GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o offline/egress-sentinel ./cmd/egress-sentinel
docker build --network=none --platform=linux/arm64 -f Dockerfile.sentinel .
```

The versions currently carry the role `observed-production-candidate`: they match the installed
clients used for characterization, but the later CLI matrix bead must add minimum/boundary rows and
promote production pins through deployment policy. A candidate row cannot certify release support.

## Remaining exit work for the lab bead

Local arm64 smoke execution has exercised the three-pod PostgreSQL topology, fresh Codex and Claude
version cells, the dual-stack DNS/direct-IP/QUIC/proxy-bypass mutants, residue checks, and teardown.
Those local observations are useful debugging evidence only: the ignored local runtime lock and
Docker inventory are not checked release artifacts and must not be cited as portable certification.

The bead remains open until the lifecycle runner records a canonical raw artifact bound to inspected
OCI indexes, demonstrates native execution for both `linux/amd64` and `linux/arm64`, and feeds the
versioned integration-evidence gate. The external bridge-level recorder must independently derive
zero forbidden egress and zero paid inference. None of the architecture, egress, paid-inference,
residue, teardown, or exact-version rows may be inferred from declarations or silently skipped.
