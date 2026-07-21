# Deterministic contract scenario engine

`contractscenario` is an offline test-double primitive. It owns per-cell
identity, synthetic authentication, exact request matching, ordered state
transitions, deterministic faults, budgets, barriers, cancellation/retry
accounting, and canonical request/signature inputs.

It does **not** establish AWS Bedrock or Bedrock Mantle behavior. Callers must
provide the compiled fixture authority, route coverage, protocol framing, and
independent evidence labels. No method in this package performs network I/O,
credential discovery, clock reads, or provider calls.

Integration requirements:

1. Create one engine cell per scenario/project; never share expectations across
   cells.
2. Call `Match` before applying a response or fault and require all expected
   transitions to be consumed before success.
3. Use `CanonicalRequest` and `SigV4Signature` only with pinned fixture inputs;
   these helpers are signing-input utilities, not a service-authority source.
4. Record deterministic diagnostics and evidence confidence separately from
   any AWS observation.
