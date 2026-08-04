# Parameterized artifact retrieval probe (2026-08-06)

## Question

Does a validated SQL artifact become useful when the next request has the same
query shape but different literal parameters, and can the system abstain when
no stored template exists?

## Protocol

The probe uses the pinned public Defog PostgreSQL CSVs for the `broker` and
`car_dealership` databases. Source artifacts come only from the basic and
advanced instruction files. Positive targets are deterministic mutations of
source questions and SQL literals (dates, intervals, limits, and equivalent
surface phrasing). A source SQL AST is normalized by replacing literals with
placeholders. Explicit proxy-NIL targets are held-out generated questions whose
normalized template is absent from the same-database source pool.

The three retrieval arms are:

1. lexical question-token overlap;
2. template-first ranking with lexical tie-breaking; and
3. template-gated retrieval, which abstains when no exact normalized template
   exists.

## Result

| Arm | Positive targets | Top-1 | MRR | NIL false accepts | NIL abstentions |
|---|---:|---:|---:|---:|---:|
| lexical | 52 | 52/52 | 1.000 | 10/10 | 0/10 |
| template-first | 52 | 52/52 | 1.000 | 10/10 | 0/10 |
| template-gated | 52 | 52/52 | 1.000 | **0/10** | **10/10** |

## Interpretation

This is the missing middle case between the earlier natural-library coverage
null and the controlled paraphrase upper bound. Parameterized templates can
recover a known reusable shape, and a hard template gate prevents the lexical
system from manufacturing an artifact for a query whose shape is absent.

The result is **not** evidence of enterprise semantic quality: positive targets
inherit intent from their source SQL, NILs are template-absence proxies rather
than SME labels, and no SQL execution or changed-schema replay was performed.
The lexical and template arms tying at 52/52 also show that this fixture does
not measure ranking difficulty; its value is the explicit abstention boundary.

## Engineering consequence

Store validated SQL/tool artifacts as parameterized, typed templates with a
strict structural compatibility gate. Use lexical/dense retrieval only inside
the compatible-template set; if the set is empty, abstain or invoke fresh
frontier regeneration. Do not reuse a nearest whole-query artifact solely
because its wording is similar.

Receipt: [`parameterized-artifact-retrieval-2026-08-06.json`](../results/parameterized-artifact-retrieval-2026-08-06.json)

Verifier: `verify_parameterized_artifact_retrieval_probe.py` (receipt hash
`626419c94f9fe46526575f6afe515a0e7b4072304d565f5645a919402a0c8592`).

Raw questions and SQL remain outside the repository.
