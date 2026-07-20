# FrankenGate domain glossary

## FrankenGate

The fork-owned AI gateway and its separately deployed analytics/control-plane
surfaces. Bifrost remains a compatibility reference, not the product name.

## Gateway plane

The latency-sensitive Go request path that authenticates, routes, executes, and
returns inference or MCP traffic. Analytics jobs do not run in this plane.

## Analytics plane

The separately deployed control plane for experiments, runs, evaluations,
replay, artifact lineage, and governed workers.

## Experiment

A tenant-owned definition of an evaluation or learning activity, anchored to an
explicit revision and actor.

## Run

A concrete execution of an experiment. A reproducible run names the dataset,
evaluator, model, and prompt revisions used by that execution.

## Job

A leased unit of analytics work. Jobs have tenant ownership, monotonic delivery
attempts, checkpoints, terminal outcomes, and explicit cancellation or retry.

## Artifact manifest

Metadata describing an immutable run output. Artifact bytes live in object
storage; the manifest carries the digest, media type, run, and approved URI.

## Governed worker

A separately managed worker that acts within a tenant and lease boundary, with
bounded progress, cancellation, retry, and shutdown-drain behavior.

## Stable release

A versioned FrankenGate release whose clean-checkout binary, Helm, OCI image,
changelog, and runtime evidence have passed the release checklist. Local gates
alone do not constitute a stable release.
