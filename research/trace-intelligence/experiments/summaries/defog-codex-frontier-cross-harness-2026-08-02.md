# Cross-harness paraphrase transfer screen (2026-08-02)

## Harnesses

The same four broker tasks, paraphrase mutation, governed database contract,
arms, and independent verifier were run through two implementations:

- `codex-subscription-loopback-proxy`: HTTP Chat Completions adapter whose
  proxy serializes bracketed role/tool transcripts.
- `codex-cli-native-json-v1`: direct Codex CLI adapter that serializes the
  conversation and tool schema as canonical JSON and does not use an HTTP
  server.

The harness-comparison receipt confirms identical task and arm sets and
independent semantic verification. Raw prompts, SQL, and rows remain outside
the repository.

## Results

The proxy harness's three-seed paraphrase aggregate scored:

| arm | correct |
| --- | ---: |
| no skill | 6 / 12 |
| formatting placebo | 7 / 12 |
| length-matched neutral | 7 / 12 |
| trace-mined | 8 / 12 |

The native harness's independent four-task seed scored:

| arm | correct |
| --- | ---: |
| no skill | 2 / 4 |
| formatting placebo | 3 / 4 |
| length-matched neutral | 3 / 4 |
| trace-mined | 2 / 4 |

The trace artifact therefore does not reproduce a positive advantage across
harnesses: it is directionally above neutral in the proxy aggregate but below
neutral in the native run. The native run also ties no-skill (2/4 vs 2/4).
This is a descriptive cross-harness screen, not a harness ranking or causal
skill estimate because the native arm has one seed and the proxy arm has three.

## Decision

Do not promote the artifact. The minimum next gate is a balanced, preregistered
multi-seed run on both harnesses with family-held-out tasks, source-literal
redaction, independent semantic/security verification, and cost/latency/
abstention regression limits.
