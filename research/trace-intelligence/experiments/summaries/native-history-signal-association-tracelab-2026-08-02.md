# Native history signal association — 2026-08-02

This descriptive analysis uses the 28-session Claude screen. It compares
session-level structured executor-error rate with counts of language-level
signals. It has no gold friction, satisfaction, task-success, or intent labels.

| Language signal | Sessions with signal | Also structured-error session | Spearman(error rate, signal count) |
| --- | ---: | ---: | ---: |
| dissatisfaction | 10 | 8 | -0.265 |
| correction | 20 | 16 | -0.248 |
| retry/repair | 21 | 18 | -0.234 |
| clarification | 9 | 6 | -0.443 |

The negative associations are not evidence that errors improve outcomes. They
show that error density alone is a poor friction detector in this cohort:
longer, productive exploratory sessions can contain more tool activity and
more successful recovery. A serious detector therefore needs episode-local
ordering, terminal outcome, correction/recovery transitions, abandonment, and
human-adjudicated labels rather than a global “number of errors” score.

