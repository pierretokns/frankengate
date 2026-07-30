# Fable-5 aggregate sensitive-token scan

Date: 2026-07-30

Status: **raw external egress blocked**

The fail-closed aggregate scanner verified the 79-file, 58,416,137-byte,
18,770-record content-addressed Fable cohort before inspecting every nested
JSON string leaf. It scanned 338,210 strings and found:

- 65 redaction markers: seven literal markers and 58 scrubbed typed
  placeholders;
- 11 possible secret regex candidates, all in the bearer-token class; and
- zero emitted, retained, hashed, logged, or validated candidate values.

“Candidate” means a regex shape only. The scan does not establish that any
value is live or sensitive. Conversely, public availability and some redaction
markers do not prove the archive safe for external processing.

The source is the pinned
[Glint Fable-5 archive](https://huggingface.co/datasets/Glint-Research/Fable-5-traces/tree/e05c417852fc59fd8da758e68b352732423ca0cb/claude/projects).
Its [dataset card](https://huggingface.co/datasets/Glint-Research/Fable-5-traces)
warns that raw logs contain telemetry, terminal output, and local paths and are
not guaranteed sanitized.

Therefore raw trace text must not be sent to an external model, used for
training, or quoted publicly. A separate sanitizer must replace secret and
high-entropy candidates, preserve only typed within-pack placeholders, rescan
the final evidence pack, and fail closed before the preregistered model phase
can run. Local aggregate mechanics remain allowed.

The machine-readable result is
[`fable5-sensitive-token-scan-2026-07-30.json`](../results/fable5-sensitive-token-scan-2026-07-30.json).
Its internal result SHA-256 is
`561f71287fcc1f9e67d071482a261f60f519dd49076127a2c13bf5629e3f5fd2`.
