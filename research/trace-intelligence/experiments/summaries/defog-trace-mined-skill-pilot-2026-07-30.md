# Defog trace-mined skill pilot (2026-07-30)

This is a bounded, visible-selection intervention pilot using four pinned
Defog PostgreSQL tasks from the `car_dealership` database, a real local
Ollama `llama3.2:latest` model, and a constrained `NOSUPERUSER NOBYPASSRLS`
PostgreSQL role. Raw prompts, SQL, rows, and model messages remain outside
Git; the committed result contains hashes and aggregate counts only.

The three paired arms were:

* `no_skill` — baseline tool-loop prompt;
* `formatting_placebo` — a formatting-only addition; and
* `trace_mined_terminal_discipline` — a procedure mined from a successful
  natural coding trace: inspect observations, preserve the successful attempt,
  submit that exact attempt, and stop after the attempt budget.

All 12 runs carried a valid current authorization epoch and produced zero
unauthorized observations. None of the 12 runs reached a terminal submission,
so there were zero policy-accepted or semantically-correct answers. The
trace-mined arm produced one successful SQL execution (1/4 tasks), compared
with zero for both controls, but it also made more SQL attempts (12 versus 8)
and still failed the terminal protocol. This is a diagnostic runtime signal,
not evidence of skill optimization or improved task performance.

| arm | tasks | valid authority | successful SQL attempts | terminal submissions | semantic correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| no skill | 4 | 4 | 0 | 0 | 0 |
| formatting placebo | 4 | 4 | 0 | 0 | 0 |
| trace-mined discipline | 4 | 4 | 1 | 0 | 0 |

The result is therefore a **negative/diagnostic pilot**. It confirms that
trace-derived procedures can be exposed to a real model in the governed SQL
loop, but does not confirm that they optimize skills. The next decisive test
must use family-disjoint held-out tasks, sealed outcomes, an independent
semantic and security verifier, and a repaired terminal protocol. A larger
model or new harness is not a success criterion by itself; success requires a
paired lift in accepted, semantically-correct answers without security,
latency, or tool-call regressions.

Machine-readable result: [`defog-trace-mined-skill-pilot-2026-07-30-r4.json`](../results/defog-trace-mined-skill-pilot-2026-07-30-r4.json).
