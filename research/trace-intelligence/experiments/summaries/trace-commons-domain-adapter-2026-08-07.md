# Leave-one-project-out domain-adapter probe

## Protocol

Using the 13 repeated Trace Commons workstream-proxy sessions, we trained a
transparent token-weight adapter on all *other* projects and evaluated each
held-out project. The adapter increases weights for tokens co-occurring within
training workstreams and downweights cross-workstream tokens. It was evaluated
over prompt terms, durable identifiers, and their combination.

This is a representation-transfer probe, not a neural embedding benchmark.
The corpus has no stable principals, semantic intent labels, or prospective
outcomes.

## Result

| Features | Baseline top-1 / MRR | Adapter top-1 / MRR |
|---|---:|---:|
| Prompt | 13/13 / 1.000 | 13/13 / 1.000 |
| Durable identifiers | 13/13 / 1.000 | 13/13 / 1.000 |
| Prompt + identifiers | 13/13 / 1.000 | 13/13 / 1.000 |

## Interpretation

The adapter produced no measurable lift because the workstream proxy is already
at ceiling. This is not evidence that domain-specific embedding adaptation is
useless; it shows that this public cohort is too easy and too small to measure
it. A real corporate adapter test needs entity/project/time holdouts, repeated
intents with paraphrases, same-surface wrong-system negatives, and independent
semantic labels.

The result supports a strict promotion rule: do not train or promote a custom
embedding from unlabelled trace similarity alone. First establish a difficult,
reviewed contrastive dataset where the adapter must improve absolute retrieval
and downstream artifact utility without increasing collision or latency.

Receipt: [`trace-commons-domain-adapter-2026-08-07.json`](../results/trace-commons-domain-adapter-2026-08-07.json).
Independent verification: [`trace-commons-domain-adapter-2026-08-07-verification.json`](../results/trace-commons-domain-adapter-2026-08-07-verification.json).

