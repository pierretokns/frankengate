# NL2SQL solver Linux OCI conformance runbook

This runner tests the actual kernel boundary of the one-episode solver. The
ordinary macOS unit tests validate only the OCI configuration shape.

## Frozen inputs

- Runtime: the `runc` installed in the Colima Linux VM.
- Root filesystem: the already-cached official
  `python@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0`
  image. The runner never pulls an image.
- Staged application files: `dto.py`, `solver_process_worker.py`, and an empty
  package initializer. No repository, dataset, manifest, SQL, database
  credential, evaluator label, or key is mounted.
- OCI configuration: produced and revalidated by the current
  `build_solver_oci_config`.

## Invocation

After merge, run directly from the macOS host through the `/Users/pierre`
virtiofs mount:

```sh
colima ssh -- sudo -n python3 \
  /Users/pierre/dev/bifrost/research/trace-intelligence/nl2sql_linux_oci_conformance.py \
  --raw-output /tmp/fg-nl2sql-oci-raw.json \
  --aggregate-output /Users/pierre/dev/bifrost/research/trace-intelligence/experiments/results/nl2sql-linux-oci-conformance-2026-07-30.json
```

The raw file must remain outside the repository. It contains exact base64
stdio and socket traffic, the complete OCI configuration, and the kernel probe.
The repository-safe aggregate contains hashes, counts, gate decisions, and
limitations only.

Colima does not mount host `/private/tmp`. To run from the dedicated
`/private/tmp/frankengate-trace-research` worktree before merge, copy only the
runner and reviewed dependencies into a disposable VM directory:

```sh
colima ssh -- sudo -n mkdir -p \
  /tmp/fg-oci-conformance-src/research/trace-intelligence/nl2sql_capabilities

tar -C /private/tmp/frankengate-trace-research -cf - \
  research/trace-intelligence/nl2sql_linux_oci_conformance.py \
  research/trace-intelligence/nl2sql_capabilities/dto.py \
  research/trace-intelligence/nl2sql_capabilities/solver_oci.py \
  research/trace-intelligence/nl2sql_capabilities/solver_process_worker.py |
  colima ssh -- sudo -n tar -C /tmp/fg-oci-conformance-src -xf -

colima ssh -- sudo -n python3 \
  /tmp/fg-oci-conformance-src/research/trace-intelligence/nl2sql_linux_oci_conformance.py \
  --raw-output /tmp/fg-nl2sql-oci-raw.json \
  --aggregate-output /tmp/fg-nl2sql-oci-aggregate.json
```

## Gates

The run passes only when the container starts and finishes, both inherited Unix
sockets work, and the probe demonstrates all of the following:

- UID and GID 65532, empty capability sets, `NoNewPrivs: 1`, and active seccomp;
- a read-only root filesystem;
- writable, mode-0700, UID/GID-65532 tmpfs mounts at `/home`, `/tmp`, and
  `/work`;
- `AF_INET` and `AF_INET6` socket creation denied with `EPERM`;
- exactly descriptors 0–4, with 3 and 4 serving the broker and model channels;
- exactly the three staged application files and no named sensitive paths;
- the frozen environment allowlist; and
- no raw, hexadecimal, base64, base64url, or SHA-256 representation of the
  source, gold, hidden-label, adjudication, DSN, or signing-key canaries in any
  child-visible input, argv, environment, staged file, output, or wire bytes.

## Failures found by the real runtime

The first frozen-profile run failed before Python with
`ensure /proc/self/fd is on procfs: operation not permitted`. The preserved-FD
path in `runc` needs read-only `fstatfs`, which was absent from the original
default-deny syscall list. Adding only `fstatfs` advanced startup.

The next run failed at `execve` with `EAGAIN`. A nominally generous
`RLIMIT_NPROC=16` was already exhausted because UID 65532 was also used by
CoreDNS in this VM, and that one process had 17 threads. `RLIMIT_NPROC` counts
threads for the real UID across the host, not processes inside the solver
cgroup. The frozen profile therefore removed `RLIMIT_NPROC` and retains the
container-scoped `pids.limit=16`; seccomp separately denies `clone`, `clone3`,
`fork`, and `vfork`.

After those two profile corrections, the final frozen-profile run passed every
gate. This sequence is why macOS profile-shape tests cannot substitute for an
actual Linux runtime test.

This proves one boundary on one Colima kernel/runtime combination. It does not
prove SQL correctness, model quality, production peer authentication,
cross-kernel portability, crash durability, or signed/WORM evidence.

The frozen Python image is a general-purpose root filesystem, not a minimal
solver image, and it contains executables beyond the three staged Frankengate
files. `execve` remains allowlisted because the OCI process must start; this
profile does not independently prevent a compromised worker from executing a
different binary already present in that read-only image. A production image
should remove unused interpreters, shells, package managers, and utilities.

If the frozen profile cannot start, repeat only for syscall diagnosis with one
or more `--diagnostic-extra-syscall NAME` arguments. Such a run is labeled
`diagnostic_nonrelease` and is forced to fail the release gate even when every
kernel probe succeeds. The diagnostic mode exists to identify startup
requirements; it cannot silently weaken or certify the production profile.
