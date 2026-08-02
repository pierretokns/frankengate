# Real Claude Code session SSL-style normalization probe (2026-08-02)

This probe applies the grounded Scheduling--Structural--Logical normalizer to
an actual public Claude Code session rather than a synthetic tool benchmark.
The source is the MIT-licensed `jimmc414/cctrace` portable-session example.

## Protocol

- Source: one public Claude Code session (`raw_messages.jsonl`).
- The session contains 15 episodes with at least two tool calls; 12 ordinary
  bounded episodes contain 3--12 calls.
- Sample: the first 10 bounded episodes, preserving original event order.
- Model: `gpt-5.6-luna` through the Codex harness.
- Raw prompts/responses remain in `/private/tmp/cctrace-ssl-normalizer-20260802-r2`.
- Episodes containing 49 tool calls were excluded from this probe to avoid a
  whole-session outlier dominating prompt size; the exclusion is recorded in
  the receipt.

## Results

| Measure | Result |
| --- | ---: |
| Valid calls | `10/10` |
| Exact tool-name/order preservation | `1.000` |
| Exact logical action count/order/resources | `1.000` |
| Evidence substring grounding | `.922619` |
| Fully grounded episodes | `.800` |
| Mean scenes | `1.9` |
| Mean transitions | `.9` |
| Mean actions | `6.1` |
| Mean latency | `19.751s` |

## Interpretation

The normalizer works mechanically on a real coding trace: it preserves the
ordered tool topology and emits structural scenes and transitions instead of
the zero-scene behavior seen on isolated tool descriptions. The evidence
grounding rate is lower than the isolated-tool probe (`.9875`) because coding
episodes contain more claims, tool results, paths, and inferred phase
boundaries. One 11-tool episode contributed most of the ungrounded evidence.

This supports a canonical trace design with deterministic tool/order fields
plus review-only scene/effect proposals. It does **not** establish user intent,
task correctness, skill improvement, artifact reuse, or cross-user transfer:
the cohort is one session from one publisher and has no independent outcome or
capability labels. The next useful step is to run the same receipt on multiple
authorized sessions and add replay/terminal labels, not to train an embedding
model from these normalized fields yet.

## Claim boundary

This measures grounded normalization mechanics on a real public trace bundle.
It does not measure retrieval lift, alias quality, risk classification, skill
utility, or enterprise outcomes.

## Receipts

- [machine-readable result](../results/cctrace-ssl-normalizer-probe-2026-08-02-r2.json)
- [independent verification](../results/cctrace-ssl-normalizer-probe-verification-2026-08-02-r2.json)
- [runner](../../cctrace_ssl_normalizer_probe.py)
- [verifier](../../verify_cctrace_ssl_normalizer_probe.py)
- [dataset manifest](../../configs/datasets/github-cctrace-portable-claude-session.json)
- [multi-tool benchmark probe](traject-bench-ssl-trace-normalizer-probe-2026-08-02.md)
