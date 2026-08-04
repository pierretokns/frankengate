# TermSuite and AcronymExpansion feasibility check

**Status:** not empirically scored; reproducible setup blockers recorded

## TermSuite

The official TermSuite 3.0.10 core JAR starts after adding the Java 23
reflective-access flag, but the CLI then aborts because its required
TreeTagger POS-tagger home/model is absent. The official TreeTagger host was
unavailable from this environment and the mirror returned a forbidden or
certificate-mismatch response. No candidate output was treated as a result.

## AcronymExpansion

The cited `adityathakker/AcronymExpansion` repository is a 2017 research code
base, not a current package. It pins a legacy stack (gensim 2.3, NumPy 1.13,
scikit-learn 0.19, and NLTK 3.2), requires training a Doc2Vec model, and ships
no pretrained model. It is therefore not a fair drop-in comparison on the
current trace corpus. The separate AcX project is a different rule-based
implementation and should not be silently substituted for the cited tool.

## Decision

Keep both items in the research backlog, but do not report them as failed
methods. A fair next run requires a pinned TreeTagger model/container for
TermSuite and a separately reproduced legacy environment plus training corpus
for AcronymExpansion. In the meantime, deterministic acronym patterns and
explicit NIL/ambiguous outcomes remain the executable baseline.

References: [TermSuite getting started](https://termsuite.github.io/getting-started/),
[TermSuite Maven artifact](https://repo1.maven.org/maven2/fr/univ-nantes/termsuite/termsuite-core/3.0.10/termsuite-core-3.0.10.jar),
[AcronymExpansion](https://github.com/adityathakker/AcronymExpansion),
[AcX](https://github.com/joaolmpereira/acx-acronym-expander).
