# ToolQA terminal-format audit

Date: 2026-08-02  
Status: completed and independently verified; conservative formatting only

The prior candidate-breadth experiment used the unchanged ToolQA evaluator.
This audit checks whether a small number of failures are representation
failures rather than wrong task answers. It does **not** use an LLM judge and
does not infer semantic correctness.

## Rules

The existing ToolQA normalized exact match is applied first. Only failures are
then checked for:

- exact numeric equality after removing currency punctuation and `USD`;
- exact time equality across 12-hour, 24-hour, and four-digit clock forms.

Rounding, partial answers, list containment, and prose paraphrases are not
accepted.

## Results

| arm | benchmark correct | conservative format-recovered correct | recoveries |
| --- | ---: | ---: | --- |
| no-skill | `4/14` | `4/14` | none |
| BGE top-1 | `7/14` | `8/14` | currency formatting (`$42,450` vs `$ 42450.0`) |
| BGE top-5 full injection | `6/14` | `7/14` | currency formatting (`42450` vs `$ 42450.0`) |
| BGE progressive disclosure | `7/14` | `8/14` | clock formatting (`9:43 PM` vs `21:43`) |
| gold oracle | `7/14` | `8/14` | currency formatting (`42450` vs `$ 42450.0`) |

## Interpretation

The strict evaluator understates some output-format robustness, but only by one
task in three skill-enabled arms. The oracle still reaches only `8/14` under
this conservative audit, so formatting is a contributor, not the whole
incorporation ceiling. The remaining failures include wrong values, refusal,
partial answers, and malformed/unsupported tool use; they need semantic
adjudication and execution-level instrumentation rather than a looser string
matcher.

This supports adding two separate metrics to future skill studies:

1. benchmark-exact terminal answer;
2. independently defined semantic/typed terminal result.

They must never be silently merged. A skill should not be promoted because a
format-normalized score moved.

## Receipts

- Receipt: [`sra-bench-toolqa-format-audit-2026-08-02.json`](../results/sra-bench-toolqa-format-audit-2026-08-02.json)
- Verification: [`sra-bench-toolqa-format-audit-verification-2026-08-02.json`](../results/sra-bench-toolqa-format-audit-verification-2026-08-02.json)
- Runner: [`sra_bench_toolqa_format_audit.py`](../../sra_bench_toolqa_format_audit.py)
- Verifier: [`verify_sra_bench_toolqa_format_audit.py`](../../verify_sra_bench_toolqa_format_audit.py)
