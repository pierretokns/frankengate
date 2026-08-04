# Upstream porting policy

When an older research repository is modernized, Frankengate creates or uses a
GitHub fork, preserves the upstream commit and license/provenance record, and
adds a clean port with a separate dependency lock. The port must include:

1. the concepts and output contract retained from upstream;
2. a current `uv` environment and reproducible command;
3. a compatibility fixture against the old contract where feasible;
4. a claim boundary distinguishing mechanics from efficacy; and
5. a receipt that records the exact upstream commit and current implementation.

The TermSuite and AcronymExpansion ports follow this policy. TermSuite's fork
retains its upstream Apache-licensed history. AcronymExpansion's upstream
repository has no discoverable license file, so the fork records attribution
and the new implementation is kept clean rather than copying source code.

The published branches are:

- `pierretokns/frankengate-termolator-modern:modern-port`
- `pierretokns/frankengate-acronym-expansion-modern:modern-port`
