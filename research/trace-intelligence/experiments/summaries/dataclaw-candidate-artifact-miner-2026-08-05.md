# DataClaw candidate artifact mining (2026-08-05)

The content-free miner scanned 549 MIT-licensed DataClaw sessions and emitted
the top 100 recurring non-trivial tool-call forms. It found 63 candidates with
support across at least two project labels; every candidate also had at least
one broad friction-language context. Commands, prompts, paths, arguments, and
identifiers remain outside the receipt.

This is exactly the right input shape for a review queue, not an automatic
skill library: every candidate is marked `review_required=true` and
`promotion_eligible=false`. Repetition and proximity to friction do not prove
that a command is correct, safe, reusable, or desired by the user. The next
step is an explicitly authorized sealed frontier/SME review (or a locally
redacted review representation), followed by independent replay in a clean
environment and a changed-system outcome gate. Raw tool inputs and preceding
user context were not sent to a frontier endpoint in this study.

Receipt: [`dataclaw-candidate-artifact-miner-2026-08-05.json`](../results/dataclaw-candidate-artifact-miner-2026-08-05.json)

Verifier: [`verify_dataclaw_candidate_artifact_miner.py`](../../verify_dataclaw_candidate_artifact_miner.py)
