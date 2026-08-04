# WMH-BIRD aligned cascade cohort

Date: 2026-08-02  
Status: frozen public proxy; not enterprise-semantic or promotion-ready

The next comparison cohort is now frozen as cohort
`07137f114ba210808eaa91daefd57c47125c1deabfc3ecfeb25fff0e59777038`:

- 44 cases, four deterministic odd-half evaluation tasks per database family;
- the exact pinned trace and task-manifest hashes already used by the WMH-BIRD
  replay studies;
- one candidate pool consisting of all tables exposed in each trace;
- content-free case-set and candidate-pool hashes; and
- explicit arms for lexical, schema-first, provenance/alias, dense,
  authority-constrained, replay-backed action, and frontier review.

This freezes the cohort-selection step before any dense vectors, frontier
outputs, or semantic labels are generated. It makes the next cascade study
reproducible and prevents the 44-case dense/frontier receipt from being
silently compared with the separate 72-case ontology projection.

The cohort is still only a public SQL-agent proxy. It has no reviewed
corporate aliases, real principals or policy epochs, human intent labels, or
changed-system outcomes; its receipt is therefore not promotion-eligible.

Manifest: [`wmh-bird-aligned-cascade-cohort-v1.json`](../../configs/experiments/wmh-bird-aligned-cascade-cohort-v1.json)  
Builder: [`wmh_bird_aligned_cohort_manifest.py`](../../wmh_bird_aligned_cohort_manifest.py)
