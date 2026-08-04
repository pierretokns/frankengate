# Public DataClaw friction-signal calibration (2026-08-09)

This is a frontier silver-label calibration on the cached public
[DataClaw conversation dataset](https://huggingface.co/datasets/peteromallet/dataclaw-peteromallet).
It is separate from the private Codex archive: no private archive content was
sent to a frontier service.

## Protocol

- 12 messages selected from 549 public sessions.
- Stratified selection: lexical friction markers, re-prompt overlap, and a
  neutral slice.
- Two independent `gpt-5.6-luna` classifications per message.
- Labels: `friction`, `productive_iteration`, or `unclear`.
- The model saw only the current and immediately previous user message; it did
  not see user identity, project identity, or tool outputs.

## Result

- 24/24 calls returned valid structured labels.
- 11/12 rows had repeat-label agreement; one row split between
  `productive_iteration` and `unclear`.
- Silver labels: 10 friction, 13 productive iteration, 1 unclear.
- Among the deliberately sampled lexical-marker rows, 6/12 calls were labeled
  friction: the marker detector over-flagged productive iteration and one
  unclear case.
- Re-prompt-overlap rows were labeled friction on 4/6 calls; the remaining 2
  were productive iteration.

Because the cohort is intentionally stratified, these are calibration counts,
not population precision/recall estimates. Frontier labels are silver labels,
not independent truth. They do support a practical mining design: use
re-prompt/correction structure to prioritize review, retain lexical markers as
weak features, and require tool/result/outcome evidence before promoting a
friction episode into an eval or skill candidate.

## Boundary

This run does not establish user dissatisfaction, intent, employee skill,
causal benefit, or enterprise transfer. The private 622-session Codex archive
was analyzed locally with deterministic counters only; the frontier request for
that private payload was rejected and not retried.

## Receipts

- [content-minimized calibration receipt](../results/dataclaw-friction-luna-calibration-2026-08-09.json)
- [existing receipt verifier](../../verify_dataclaw_friction_luna_calibration.py)
- [native Codex archive adapter](../../codex_archive_to_friction_luna.py)
