# Same-cohort NL2SQL alias cascade audit (2026-08-09)

## Question

What do structured identifiers, lexical retrieval, dense embeddings, and a
frontier model each contribute when evaluated on exactly the same alias/NIL
cohort? This audit composes the existing 22-case Defog alias receipt; it does
not pool incompatible datasets.

## Same-cohort result

The cohort contains 14 target-retrieval cases and 8 constructed
scope-swapped-NIL cases. All four retrieval arms return a top candidate on
every NIL case (`1.0` top-1 candidate rate), so candidate generation alone does
not provide refusal. The frontier decision layer is the separate abstention
mechanism.

| Arm | MRR | Recall@1 | Recall@5 | Wrong-system-before-target | NIL top-1 candidate |
|---|---:|---:|---:|---:|---:|
| Lexical + scope | `.805844` | `.785714` | `.785714` | `0.0` | `1.0` |
| Exact identifier + scope | `.892857` | `.785714` | `1.0` | `0.0` | `1.0` |
| Dense + scope | `.689966` | `.571429` | `.857143` | `0.0` | `1.0` |
| Frontier + scope | `1.0` | `1.0` | `1.0` | `0.0` | `1.0` |

Relative to dense retrieval, exact structured retrieval adds `.202891` MRR
and `.214285` Recall@1; the frontier ordering adds `.310034` MRR and `.428571`
Recall@1 on this small public proxy. These are gold-SQL target-object labels,
not human semantic-alias labels. The frontier arm had 22 completed calls in the
source receipt.

## Separate synthetic capability gate

The 23-case stratified Luna adjudication receipt (11 exact, 6 semantic, 4 NIL,
2 unclear) reached `1.0` surface accuracy, `1.0` candidate accuracy, `1.0`
NIL/unclear abstention, and `1.0` inter-judge surface/candidate agreement.
Those labels are construction-time synthetic truth and therefore test output
format, scope handling, and abstention—not enterprise semantics.

## Interpretation

The fair cascade on this cohort is:

```text
scope / identifiers / compatibility
  -> lexical or exact structured retrieval
  -> optional dense recall
  -> frontier review and explicit abstention
  -> independent replay and human/SME adjudication
```

The decisive negative is that every retrieval arm proposes something for NILs.
Dense vectors are weaker than exact structure here; frontier ranking is strong
only on a small, gold-derived proxy and must not be treated as authority. This
audit supports separating candidate recall, refusal, and semantic validation as
distinct stages.

## Claim boundary and next gate

The audit does not establish corporate alias quality, human agreement, changed
system utility, or a deployable embedding. The next fair experiment needs the
same four arms on independently reviewed aliases, NILs, temporal renames, and
same-surface wrong-system pairs, followed by changed-schema/tool replay.

Tracking: [concept/alias discovery #120](https://github.com/pierretokns/frankengate/issues/120),
[embedding/model cascade #122](https://github.com/pierretokns/frankengate/issues/122),
and [hard-negative mining #123](https://github.com/pierretokns/frankengate/issues/123).

## Receipts

- [content-free composition result](../results/nl2sql-alias-cascade-audit-2026-08-09.json)
- [independent verification](../results/nl2sql-alias-cascade-audit-verification-2026-08-09.json)
- [`nl2sql_alias_cascade_audit.py`](../../nl2sql_alias_cascade_audit.py)
- [`verify_nl2sql_alias_cascade_audit.py`](../../verify_nl2sql_alias_cascade_audit.py)
