# cctrace normalized-output quality audit (2026-08-02)

This audit evaluates the 10 bounded real-session normalizations against
source invariants. It is intentionally separate from the frontier receipt:
the frontier call can be valid JSON while still omitting actions or inventing
unsupported structure.

## Checks

- Every observed tool call must have one normalized logical action in the same
  order.
- Tool-name mapping supplies a conservative mechanical action-type reference:
  `Read/Grep/Glob/LS/Search -> READ`, `Edit/Write/NotebookEdit/MultiEdit ->
  WRITE`, and other observed tools -> `CALL`.
- Every action order must appear in at least one scene, with no duplicate scene
  assignments.
- Every transition must reference an emitted scene name.

## Results

| Check | Result |
| --- | ---: |
| Episodes audited | `10` |
| Exact action order | `1.000` |
| Mechanical action-type accuracy | `.983607` |
| Mean scene action coverage | `1.000` |
| All actions covered by scenes | `1.000` |
| Duplicate scene assignments | `0.0` average |
| Valid transition references | `1.000` |

## Interpretation

The normalized output is structurally complete on this bounded session: it
does not drop or reorder observed tool calls, and all scene assignments cover
the action sequence. The small action-type error is expected from the
conservative name-only reference and is not a semantic correctness label.

This is stronger than schema validity and supports using the normalizer as a
reviewable trace projection. It still does not establish that a scene is the
right business phase, that an effect is true, that a command succeeded, or that
the resulting representation improves artifact retrieval or user outcomes.
Those require human adjudication and independent terminal/replay outcomes.

## Receipts

- [machine-readable audit](../results/cctrace-ssl-normalizer-quality-audit-2026-08-02-r2.json)
- [independent verification](../results/cctrace-ssl-normalizer-quality-audit-verification-2026-08-02-r2.json)
- [normalizer probe](cctrace-ssl-normalizer-probe-2026-08-02.md)
- [audit runner](../../cctrace_ssl_normalizer_quality_audit.py)
- [audit verifier](../../verify_cctrace_ssl_normalizer_quality_audit.py)
