# WMH-BIRD step-fault attribution audit (2026-08-09)

## Question

Can SkillAdaptor/AgentRx-style step-attributed diagnosis be grounded in the
recorded SQL-agent traces before attempting a targeted skill revision?

## Protocol

- Use the 1,993-trace WMH-BIRD corpus, but select at most one deterministic
  reward-1 and one reward-0 trace per base task to avoid repeated-run weighting.
- This yields 247 traces: 154 reward-1 and 93 reward-0.
- Extract SQL tool calls in trajectory order and independently execute them on
  the pinned BIRD mini-dev SQLite databases.
- Compare each result with the gold SQL sidecar. For the first non-correct SQL,
  classify the AST/result discrepancy as table selection, projection/column,
  predicate, join/aggregation, ordering/limit, literal/other, or execution
  error. This is a gold-diff proxy, not a causal diagnosis.
- Bound every SQLite query at 200,000 VM instructions so pathological queries
  cannot dominate the audit.

## Results

| Measure | Result |
|---|---:|
| Source traces | 1,993 |
| Selected traces | 247 |
| Reward-1 / reward-0 | 154 / 93 |
| Traces containing SQL | 194 |
| Extracted SQL steps | 289 |
| Traces with a gold-matching SQL step | 73 |
| First-step correct | 53 |
| Recovered after an initial fault | 20 |

First-fault categories across selected traces:

| Category | Count |
|---|---:|
| No SQL extracted | 53 |
| Table selection | 59 |
| Predicate | 36 |
| Projection/column | 26 |
| Execution error | 12 |
| Literal/other | 5 |
| Ordering/limit | 2 |
| Aggregation | 1 |
| First step already correct | 53 |

Among reward-0 traces specifically, the largest first-fault categories were
table selection (`34/93`), no SQL (`19/93`), projection/column (`16/93`), and
predicate (`14/93`). Twenty traces eventually recovered with a later correct
SQL call, which is the observable substrate for a targeted revision study.

The benchmark reward and replay result are not identical: two selected
reward-0 traces contained a gold-matching SQL step, and seven reward-1 traces
started with an execution error before later recovery. That is a concrete
warning against using the aggregate reward as the sole fault label.

## Interpretation

The corpus is sufficient to prototype a step-attributed diagnosis interface:
identify the first failing SQL step, link it to a typed fault category, and
record whether a later tool call recovered. It is not sufficient to claim that
the category is the true model/user cause or that a targeted skill revision
improves future tasks.

The next intervention should compare no revision, a neutral formatting
placebo, and a category-specific guard/revision. The revision must be replayed
on task-disjoint and changed-schema tasks, with independent execution outcomes,
latency/tool cost, and regression/rollback checks. A gold SQL replacement is an
oracle upper bound and must not be presented as a deployable skill.

## Claim boundary

This audit measures a replay-backed gold-diff proxy. It does not establish
causal fault attribution, SkillAdaptor/HASP efficacy, enterprise transfer,
human intent, or skill utility. No skill or guard was promoted.

## Receipts and code

- [content-free result](../results/wmh-bird-step-fault-audit-2026-08-09.json)
- [independent verification](../results/wmh-bird-step-fault-audit-verification-2026-08-09.json)
- [`wmh_bird_step_fault_audit.py`](../../wmh_bird_step_fault_audit.py)
- [`verify_wmh_bird_step_fault_audit.py`](../../verify_wmh_bird_step_fault_audit.py)
