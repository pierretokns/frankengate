# Independent raw-audit verification: schema-injected car replay

The content-free verifier checked all 18 external raw audits from the
schema-injected replay. Raw-file hashes and attempt chains matched the
aggregate receipt; task/arm identity, authority and epoch bindings, policy
status, terminal-tool scheduling, fallback flags, and unauthorized-observation
invariants all passed. The separate semantic verifier independently reran the
candidate/gold comparisons; its result is recorded alongside this receipt.

Semantic quality is not inferred from this security receipt alone. Raw prompts,
SQL, rows, and audit events remain external.
