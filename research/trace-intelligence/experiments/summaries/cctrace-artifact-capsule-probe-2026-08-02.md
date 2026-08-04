# Parameter-aware artifact-capsule probe (2026-08-02)

This probe tests whether the real coding-trace normalizer can emit the fields
needed for reusable tool artifacts, rather than only scenes and actions.

## Protocol

- Same 10 bounded episodes from the MIT-licensed cctrace session.
- Frontier schema required exact action order, input-key names,
  parameterization classification (`safe_template`, `literal_only`,
  `not_replayable`, or `unknown`), a proposed template, and evidence quotes.
- Raw prompts/responses remain in `/private/tmp/cctrace-artifact-capsule-20260802`.
- No commands were replayed and no artifact was released.

## Results

| Measure | Result |
| --- | ---: |
| Valid calls | `10/10` |
| Action count preserved | `1.000` |
| Input-key fidelity | `1.000` |
| Top-level repeated tool sequence preserved | `0.000` |
| Per-action resource sequence preserved | `.300` |
| Evidence substring grounding | `.794118` |
| Fully grounded episodes | `.600` |
| Safe-template actions | `.081967` |
| Literal-only actions | `.918033` |
| Not-replayable actions | `0.000` |

## What failed and why it matters

The model preserved each action's input keys, but the artifact schema created a
collision between identity and resource semantics:

- repeated `Bash` tools collapsed into a top-level `source_tool_names: ["Bash"]`;
- in several actions, `resource` became a concrete file path or conceptual
  object instead of the stable tool name;
- most actions were conservatively classified `literal_only`, which is safer
  than inventing a reusable template, but it yields little artifact reuse;
- proposed templates were grounded only `.327869` of the time under the
  mechanical substring check.

This is a real schema finding. A replayable artifact must not overload one
field with tool identity, resource target, and parameterized command text.
Frankengate should store separate immutable fields:

```text
tool_id / tool_name
action_order
input_schema + parameter_bindings
resource_ref (optional)
parameterized_template (optional)
side_effect / authority claim
evidence and replay validator
```

The promotion gate remains independent replay on the original and changed
system. A model-proposed `safe_template` is only a candidate; `literal_only`
should remain searchable evidence but not a reusable artifact.

## Claim boundary

This measures parameter-field extraction and schema failure modes. It does not
measure command replay, semantic correctness, artifact utility, or enterprise
transfer. The [quality audit](cctrace-artifact-capsule-quality-audit-2026-08-02.md)
separately verifies per-action resource and input-key round-trip properties.

## Receipts

- [machine-readable probe](../results/cctrace-artifact-capsule-probe-2026-08-02.json)
- [probe verification](../results/cctrace-artifact-capsule-probe-verification-2026-08-02.json)
- [quality audit](cctrace-artifact-capsule-quality-audit-2026-08-02.md)
- [quality result](../results/cctrace-artifact-capsule-quality-audit-2026-08-02.json)
- [quality verification](../results/cctrace-artifact-capsule-quality-audit-verification-2026-08-02.json)
- [probe runner](../../cctrace_artifact_capsule_probe.py)
- [probe verifier](../../verify_cctrace_artifact_capsule_probe.py)
