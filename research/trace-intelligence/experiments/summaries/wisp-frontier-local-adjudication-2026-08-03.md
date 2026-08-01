# Frontier versus local trace-insight adjudication

## Question

Do frontier and local models produce interchangeable insight labels when they
see the same blinded trace evidence and the same rubric?

## Protocol

Six Wisp recovery candidates were selected from the existing blinded packet and
the existing local-model `rubric_first` pass. Luna received compact
candidate-local evidence, the exact Wisp label contract, and no local labels.
The output schema required all six fields and candidate-local evidence
references. This is a model-agreement study: neither model is treated as gold.

## Result

| Field | Frontier/local agreement |
| --- | ---: |
| cause | 33.3% |
| evidence strength | 33.3% |
| outcome | 16.7% |
| productive exploration | 16.7% |
| relation | 16.7% |
| usefulness | 0.0% |
| all six fields on the same candidate | 0.0% |

Luna produced valid structured output for all six candidates and every evidence
reference was candidate-local. Agreement was nevertheless low, especially on
`usefulness`, `relation`, and `outcome`.

## Interpretation

Embedding retrieval and model extraction should not be treated as interchangeable
insight pipelines. A model pass can produce a structured review proposal, but
low cross-model agreement means it should enter an adjudication queue rather
than automatically become a memory, skill-gap label, eval, or enterprise
pattern. The result is not evidence that either model is wrong; it is evidence
that the rubric fields lack stable truth under this small public sample.

The cascade should therefore use deterministic/embedding retrieval to select
evidence, then require independent model or human agreement for high-impact
claims. Larger multi-model, human-labelled, and prospective-outcome studies
remain required.

Receipts: [`../results/wisp-frontier-local-adjudication-2026-08-03.json`](../results/wisp-frontier-local-adjudication-2026-08-03.json) and
[`../results/wisp-frontier-local-adjudication-2026-08-03-verification.json`](../results/wisp-frontier-local-adjudication-2026-08-03-verification.json).
