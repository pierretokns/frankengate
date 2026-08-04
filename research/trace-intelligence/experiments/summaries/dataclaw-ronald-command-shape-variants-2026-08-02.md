# DataClaw command-shape parameter-diversity audit

## Question

When a trace miner says that a command shape recurs, is it observing one
reusable artifact or a broad prefix that hides many distinct arguments? This
audit uses the same parseable 436-session DataClaw export and compares each
normalized command shape with a digest of the complete command string.

## Results

| Measure | Result |
|---|---:|
| Command events | 12,237 |
| Unique normalized shapes | 4,297 |
| Unique exact-command digests | 9,387 |
| Exact variants per shape | 2.185 on average; median 1 |
| Shapes with multiple exact variants | 1,092 |
| Shapes with at least five exact variants | 312 |
| Maximum exact variants for one shape | 141 |
| Cross-project shapes | 342 |

The command-shape projection therefore collapses substantial parameter
diversity. Some shapes are stable templates, but many recurring prefixes map to
multiple commands and projects. A repeated shape is not itself an artifact,
and cross-project support is an especially useful hard-negative signal.

## Design consequence

Trace mining should emit a **parameterized proposal**, not a copied command:

1. preserve the complete argument schema and typed parameter bindings;
2. attach project/system scope, authority epoch, tool version, and expiry;
3. validate the proposed binding against the current schema/contract; and
4. run independent replay before recording success or promoting an artifact.

This is the same boundary observed for validated SQL capsules: output equality
or command-prefix recurrence cannot replace semantic and authority checks.

## Claim boundary

The audit establishes parameter diversity and hard-negative candidates only. It
does not establish task equivalence, command correctness, alias quality, skill
improvement, or user benefit. Promotion remains disabled.

Receipt: [`dataclaw-ronald-command-shape-variants-2026-08-02.json`](../results/dataclaw-ronald-command-shape-variants-2026-08-02.json)

Audit implementation: [`dataclaw_command_shape_variants_audit.rb`](../../dataclaw_command_shape_variants_audit.rb)
