# Rust analytics runtime decision

Status: candidate architecture; implementation gate still open.

The first Rust control-plane slice must not assume Axum/Tokio/SQLx simply
because they are familiar. The Asupersync guidance recommends a native
greenfield design around `RuntimeBuilder`, `Cx`, `Scope`, supervision, bounded
channels, deterministic lab tests, and its native web/database surfaces.

## Decision gate

Use native Asupersync for the control plane if the pinned release provides the
required HTTP/service, PostgreSQL, cancellation, supervision, and deterministic
test surfaces. Use SQLx only as a temporary boundary if a required native
database capability is missing; SQLx compile-time `query!` macros are not an
acceptable dependency for the core design. Use Axum/Tokio only as an explicitly
measured compatibility spike, not as the default architecture.

The comparison must measure:

- cancellation and worker-death recovery;
- lease/heartbeat/checkpoint semantics and duplicate delivery;
- PostgreSQL transaction and pool behavior under bounded load;
- deterministic replay and shutdown tests;
- operational dependency count, binary size, and build footprint; and
- maintenance/provenance cost of each upstream component.

The current `analytics-rs` crate remains dependency-free until this gate is
answered from pinned source and executable tests. No ecosystem component is a
runtime dependency merely because it appears promising.
