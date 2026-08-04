# Legacy TermSuite and AcronymExpansion availability audit (2026-08-06)

The older upstream stacks were checked independently so that setup problems
would not be misreported as quality failures.

| Upstream | Observed result | Interpretation |
|---|---|---|
| TermSuite `3.0.10` | The 2017 Java distribution starts, but the corpus extraction probe stops with `NoSuchElementException` while resolving the indexed corpus/tagger resource. The jar manifest identifies a Java 8-era build and the documented flow requires external POS-tagger/model assets. | Setup-blocked upstream run; not a term-extraction quality result. |
| AcronymExpansion | The pinned repository requires a 2017-era `gensim 2.3`/NumPy/SciPy/scikit-learn stack and a trained Doc2Vec model. The checkout has no usable pretrained model and no discoverable license file in the probe source. | Setup/license/model blocked; not an acronym-quality result. |

This reinforces the modernization decision: retain clean current-Python
concept ports behind review, preserve attribution and provenance, and do not
make the obsolete upstream stacks gateway dependencies. The modern ports have
bounded candidate-generation value; these upstream attempts do not establish
equivalence or enterprise efficacy.

Receipt: [`legacy-term-acronym-upstream-availability-2026-08-06.json`](../results/legacy-term-acronym-upstream-availability-2026-08-06.json)

Related: [`older-tool-modernization-value-audit-2026-08-05.md`](older-tool-modernization-value-audit-2026-08-05.md)
