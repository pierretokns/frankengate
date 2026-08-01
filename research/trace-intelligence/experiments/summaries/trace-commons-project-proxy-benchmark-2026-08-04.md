# Trace Commons project-proxy similarity benchmark (2026-08-04)

## Protocol

We evaluated 28 Claude Code sessions from the Trace Commons export. Labels are
only a normalized first project/workspace path component; generic `Users` and
empty buckets were excluded. Thirteen sessions belonged to repeated project
proxies across `ComparIA`, `BentoFolio`, `DMLS`, `Epilog`, `Yggdrasil`, and
`NephilimOS`. No user identity was available, so this is not a cross-user
benchmark.

Three content-free receipt arms were compared with leave-one-session-out
nearest-neighbor retrieval:

| Arm | Same-project top-1 | Same-project MRR |
| --- | ---: | ---: |
| Event/tool structure | 1/13 (0.077) | 0.276 |
| User-prompt terms | 3/13 (0.231) | 0.337 |
| Structure + prompt terms | 3/13 (0.231) | 0.398 |

Prompts were processed locally; no transcript text or token is present in the
receipt. The verifier passes at
`experiments/results/trace-commons-project-proxy-benchmark-2026-08-04.json`.

## Interpretation

Prompt content provides a modest project/workstream signal beyond event/tool
structure, but the result is weak and underpowered. It does **not** demonstrate
that traces from different users can be clustered, that a skill gap exists, or
that a recommendation would improve work. It does show why the next benchmark
needs explicit task labels and principal-aware, project/time-held-out splits;
the current export cannot answer the enterprise question by itself.
