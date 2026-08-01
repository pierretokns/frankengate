# GLiNER and deterministic term-extraction probe

**Status:** independent capability run; no promotion claim
**Corpus:** 49 non-empty files from the admitted Wisp single-contributor subset
at revision `c2c90b59174318ab0b163ec9c9ac82bb879288ce`
**Raw policy:** extracted strings and candidate spans remain in a disposable
external audit file; the committed receipt stores hashes and aggregates only.

## Result

The deterministic baseline found 15,391 unique normalized terms, 666 acronym
forms, and 191 adjacent user-message reformulation candidates. These counts are
selection signals, not glossary quality.

GLiNER (`urchade/gliner_base`) produced 567 spans:

| Label | Count |
|---|---:|
| project | 318 |
| tool | 196 |
| metric | 26 |
| database | 17 |
| business process | 5 |
| acronym | 3 |
| legacy term | 1 |
| internal system | 1 |

An initial context-free eight-case probe hit `2/8`, which was confounded by
testing isolated strings. The corrected contextual probe hit `7/8` expected
labels. This is still not an enterprise precision estimate: the output is
over-inclusive toward project/tool labels, and thresholding, label definitions,
consensus with a classical extractor, and a blinded enterprise vocabulary set
are required.

Receipt:
[`term-extraction-gliner-wisp-2026-08-04.json`](../results/term-extraction-gliner-wisp-2026-08-04.json)
The current receipt is the contextual v2 run; the original context-free v1
receipt remains auditable in commit
[`ad5d4cf72`](https://github.com/pierretokns/frankengate/commit/ad5d4cf72).
The current receipt's independent verification is
[`term-extraction-gliner-wisp-2026-08-04-verification.json`](../results/term-extraction-gliner-wisp-2026-08-04-verification.json).

## Decision

GLiNER is useful as a candidate-span generator, not as an automatic ontology
or alias writer. The corrected probe shows the model can follow contextual
labels, but does not establish corpus precision. The next independent
comparison should run TermoUD or
Termolator on the same documents, then measure:

- candidate boundary and termhood precision on blinded labels;
- acronym expansion and NIL/ambiguous abstention;
- alias-cluster purity and wrong-system links;
- retrieval impact of approved aliases versus the existing exact/FTS/vector
  lanes; and
- reviewer acceptance, cost, and latency.

The current run supports keeping GLiNER in the Tier-1 candidate queue while
rejecting automatic promotion.
