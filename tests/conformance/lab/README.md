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
- exact observed Codex and Claude Code top-level npm tarballs plus their registry-published integrity;
- three gateway services with PostgreSQL and no mounted `config.json`;
- synthetic zero-cost `file://` pricing and parameter fixtures so a fresh database can bootstrap
  without remote catalog traffic (these fixtures have no production pricing authority);
- three internal dual-stack networks, no published ports, no Docker socket, and hardened services;
- deterministic run-scoped subnet and unique per-network static-address derivation. This is not a
  claim of global collision freedom across concurrent runs on one Docker daemon: hosted jobs use
  isolated daemons, and Docker network creation fails closed if independently derived ranges overlap;
- network-namespace keepers that remove IPv4 and IPv6 default routes, a fail-closed controlled DNS
  policy, and a dual-stack TCP/UDP forbidden-egress sentinel;
- separate digest-required Codex, Claude, and Bifrost runtime images;
- fresh quota-bounded `/cell`, `/tmp`, and gateway data tmpfs mounts;
- a static `cell-init` contract that clears inherited environment, validates strict scenarios and
  bounded/hash-bound seeds, admits only a fixed fake credential and internal gateway base URLs,
  runs only the expected read-only CLI binary, verifies the pinned semantic version from observed
  CLI output, bounds process lifetime, sends CLI output to stderr, emits one JSON evidence record to
  stdout, and removes cell residue;
- a Codex seed selecting `bedrock_mantle/gpt-5.5` through `/openai/v1` with retries and updates
  disabled, and a Claude seed disabling updater, telemetry, error reporting, and nonessential
  traffic.

The optional `scenario/codex-inference-boundary.json` cell runs the pinned Codex executable with a
fixed noninteractive `codex exec` argument vector, a fixed no-tools prompt, read-only sandboxing,
an ephemeral session, the sealed fake credential, and one validated internal Bifrost URL. Scenario
data cannot supply arguments or a prompt. The cell first observes `codex --version`, then validates
the CLI's stdout as bounded JSONL. It records `process_started` separately from
`request_initiated`; the latter requires `thread.started` followed immediately by `turn.started`
and a valid terminal event. Evidence accepted by the lifecycle requires exit zero,
`turn.completed` with usage, and the exact deterministic Mantle response marker. Failed
post-initiation turns, including `transport_failure_after_turn_start`, are rejected. Plain-text
configuration errors, malformed JSONL, reordered events, missing usage, timeouts, and truncated
output cannot earn request-initiation evidence. The lifecycle semantically correlates the completed
Codex turn with the run-bound deterministic Mantle transcript; it does not independently capture a
Bifrost ingress receipt.

The `exec`, `--strict-config`, `--ephemeral`, `--sandbox`, `--color`, and `--json` syntax is derived from the exact
`@openai/codex` 0.144.5 artifact locked by `images.lock.v1.json` (its `codex exec --help` surface).
The request serialization authority remains the independently pinned
`codex-cli-responses-lite-fd3c1dc1` row in
`tests/conformance/bedrock/sources/source-lock.v1.json`; its authority ceiling is client emission,
not gateway translation or AWS acceptance.

## Prefetch and runner builds

`Dockerfile.prefetch` is intentionally networked and must run in a separate project. Supply the
exact package/version/integrity triplet from `images.lock.v1.json`, export its `scratch` target to a
content-addressed offline directory, then destroy the prefetch project. Prefetch computes the packed
top-level tarball's SHA-512 SRI and matches the locked registry integrity byte-for-byte. It generates
one package lock from the exact registry package/version and materializes `/opt/client` only through
`npm ci`. Before materialization, the exact top-level install-path lock row must repeat the requested
version and the same top-level SRI, closing the tarball-to-lock provenance join. Lock SRIs then authorize installed bytes while npm resolves compatible platform-optional
packages. The installed-tree verifier additionally binds every observed coordinate. The tarball is
preserved provenance evidence, not a second installation source. `Dockerfile.runner` consumes
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

The external recorder work uses a separate `sealed-lab-runtime-lock/v2` contract rather than
silently changing v1. V2 declares a fifth digest-pinned multi-architecture `network-recorder`
image, an immutable recorder source revision, separate recorder binary SHA-256 values for
`linux/amd64` and `linux/arm64`, and the compiled
recorder-policy SHA-256. Before recorder capability is used, `VerifyRecorderArtifacts` must hash
the reviewed policy and extracted recorder binary bytes and match both declarations. The later host
capture lifecycle must perform that verification against bytes obtained from the pinned image; a
syntactically valid lock alone is not execution or recorder evidence. The recorder reference is
not exported into Compose: it belongs to the host-side capture lifecycle and must never enter a
runner or service environment. V1 remains decodable for existing smoke evidence but is explicitly
not recorder-capable and cannot satisfy the final network-evidence gate.

The lifecycle entry point accepts absolute, reviewed inputs and emits a single raw JSON result:

```bash
GOWORK=off go run ./cmd/lab-runner \
  --runtime-lock /absolute/path/runtime-lock.json \
  --source-lock /absolute/path/images.lock.v1.json \
  --compose /absolute/path/compose.yaml \
  --docker /absolute/path/to/docker \
  --failure-diagnostics-artifact /absolute/new/path/failure-diagnostics.json
```

When supplied, the runner captures bounded metadata for an allowlisted service set before every
runner-controlled teardown, including failure teardown. Each diagnostic command has a five-second
deadline within a twenty-second aggregate budget. Raw status and log bytes never enter the artifact;
only classifications, byte counts, and SHA-256 digests are retained. Publication uses a mode-0600
temporary regular file and an atomic fresh hard-link; stale targets, symlinked/nonregular/hardlinked
directory entries, and unsafe directories fail closed. Diagnostics never share stdout with the
single lifecycle JSON record. They are troubleshooting metadata, not proof of request delivery,
network isolation, or lifecycle success; process termination outside runner-controlled teardown may
prevent capture.

The lifecycle accepts the database bootstrap only after observing config-seed revision
`sealed-lab-c9-gpt55-v1`; that revision is repeated in successful lifecycle evidence. It binds this
specific synthetic GPT-5.5 provider/key/alias/TLS seed contract, not arbitrary production database
contents or later configuration convergence.

The gateway replicas declare a mode-0444 mount of `fixtures/bootstrap-config.json`. That fixture
selects the PostgreSQL config store and disables the otherwise implicit SQLite log store; it
intentionally has no provider, governance, MCP, client, or plugin sections. In split-authority mode
the serving pods therefore load provider data seeded in PostgreSQL without making the fixture the
authority for mutable configuration. Only a successful sealed lifecycle with runtime evidence bound
to provider `bedrock_mantle` and config revision `sealed-lab-c9-gpt55-v1` proves that this bootstrap
worked for the tested build. The Compose declaration alone does not prove runtime immutability. This
slice also does not prove config-file-free production bootstrap, connection-secret rotation,
change-notification convergence, or general high availability.

The PR-triggered `sealed-mantle-lab.yml` GitHub Actions workflow builds both platform variants from
the reviewed tracked source and top-level integrity-locked npm artifacts, publishes them only to an ephemeral runner-local
registry, constructs the runtime lock from the resulting OCI digests, and runs this entry point on
the hosted Linux Docker daemon. It uploads bounded lifecycle and Compose diagnostics on both success
and failure and performs an additional unconditional teardown. The tracked source archive excludes
the ignored generated web UI, so the lab gateway embeds one reviewed deterministic placeholder file
instead of downloading or building UI assets. Consequently this evidence covers the gateway API,
provider routing, and Mantle/Codex protocol path only; it provides no UI build or serving evidence.

A v2 run additionally requires `--recorder-policy /absolute/path/policy.bin` plus the complete
`--recorder-expectations`, `--recorder-transcript`, `--recorder-pcapng`, and `--recorder-ledger`
absolute-path set. Partial, relative, empty, oversized, non-regular, or symlinked evidence fails
closed. Before Compose creates
or starts any service, the runner creates a non-running, networkless, read-only container from the
exact pinned recorder image, copies `/network-recorder` through Docker's bounded tar stream, and
recomputes the policy and binary hashes declared by the v2 runtime lock. Selecting the exact path
avoids treating daemon-injected container entries such as device nodes as image payload.
The temporary extraction container is labeled with the run identity plus a cryptographically unique
invocation token. Docker's canonical returned container ID—not its reusable name—is used for copying
and normal cleanup. After an ambiguous create failure, cleanup occurs only when inspection proves the
unique token and exact pinned image identity; otherwise the run fails without deleting an unowned
container. Missing, empty, oversized, non-executable, duplicate, or hash-mismatched artifacts fail
the run. CI also characterizes the accepted artifact archive using a real Docker
import/create/copy cycle. This verifies selected image contents before capture; it still does not prove capture
readiness or completeness until the recorder process is launched and acknowledges all three bridge
interfaces. After teardown, the runner decodes the bounded control transcript, derives immutable
bindings from the runtime lock, policy, and observed platform, then verifies the exact PCAPNG and
canonical ledger bytes. PCAPNG interfaces must declare decimal `if_tsresol=9`; implicit
microsecond timestamps cannot be compared with the recorder's monotonic-nanosecond lifecycle. A
structurally valid `aborted` transcript remains diagnostic evidence only and fails the runner; only
a fully verified `complete` recorder outcome may reach lifecycle result emission.

It first normalizes the Docker daemon's reported Linux architecture and requires both independent
CLI cell binaries to report the same Go runtime architecture. The raw result binds that observed
cell platform, the source-lock digest, lifecycle timestamps, and runtime-lock digest. Non-Linux,
ambiguous, or unreviewed values fail closed. This proves the CLI cell-init binaries actually ran on
the selected architecture; it does not yet prove every service image ran natively. It then inspects the
actual OCI indexes for both required architectures, validates resolved Compose,
starts the core topology, executes a fresh Codex inference-boundary cell and a Claude version cell,
rejects residue or any
sentinel event, removes containers and volumes, and proves the project inventory is empty. The
external orchestrator passes only reviewed Docker connection variables; proxy and cloud/provider
credentials are discarded and none of its HOME or Docker state enters a runner container. This
boundary result is a raw lab record, not canonical release evidence. No aggregate certification
gate is provided yet: it would be unsafe until it independently binds raw per-cell evidence and
proves the provider-side observation boundary. The current runner deliberately emits
`unproven-external-recorder-required` even after structural recorder verification. Structural
capture evidence does not by itself prove that no paid provider request occurred, and the runner
does not yet own recorder launch or nonce generation; OCI declarations, replayable input files, or
edited JSON cannot certify the lab.
The lifecycle record is `sealed-lab-lifecycle-result/v2`; unlike v1 it embeds the validated Codex
inference-boundary cell record so its exit status and bounded output digest are not discarded.

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

Earlier local arm64 smoke execution exercised the three-pod PostgreSQL topology, fresh Codex and
Claude version cells, the dual-stack DNS/direct-IP/QUIC/proxy-bypass mutants, residue checks, and
teardown. It predates the inference-boundary scenario and therefore does not prove that scenario ran.
Those local observations are useful debugging evidence only: the ignored local runtime lock and
Docker inventory are not checked release artifacts and must not be cited as portable certification.

The bead remains open until the lifecycle runner records a canonical raw artifact bound to inspected
OCI indexes, demonstrates native execution for both `linux/amd64` and `linux/arm64`, and feeds the
versioned integration-evidence gate. The external bridge-level recorder must independently derive
zero forbidden egress and zero paid inference. None of the architecture, egress, paid-inference,
residue, teardown, or exact-version rows may be inferred from declarations or silently skipped.
