# Governed trace conformance fixtures

These compact, deterministic fixtures cover enterprise semantics that public
agent-trajectory datasets normally omit: authorization decisions and epochs,
denied tool proposals, retries and provider fallbacks, branch joins,
delegation, cancellation, redaction, deletion lineage, and classification
scope propagation.

The fixtures are synthetic by design. They test whether a representation,
adapter, storage layer, or query preserves security- and control-plane facts.
They **do not** measure model quality, diagnosis quality, retrieval relevance,
or the frequency of these conditions in production. Public and customer trace
corpora remain necessary for those empirical questions.

Each JSON document uses the research canonical trajectory envelope. Expected
invariants and expected projection losses live in `loss_receipt` so the
fixture remains valid under the current canonical schema without expanding
that schema for test-only metadata.
