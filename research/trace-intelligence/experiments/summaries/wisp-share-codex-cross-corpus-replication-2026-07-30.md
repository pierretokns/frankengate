# Wisp and share-codex cross-corpus structural replication

**Status:** aggregate-only replication complete

**Run date:** 2026-07-30

## Question

Do the lifecycle and friction-candidate mechanisms observed in the Wisp Claude
Code corpus appear again in the independent share-codex longitudinal corpus,
and which measurements survive schema and selection differences?

This analysis reads only two committed content-minimized result JSON files. It
does not download or open either transcript corpus. Input hashes are recorded
in the output.

## Method

Every rate names its numerator and denominator. Two-sided 95% Wilson score
intervals are reported for proportions.

These intervals are descriptive compatibility intervals, not enterprise
population confidence intervals. Tool events cluster heavily within sessions;
Wisp is the complete released 104-file snapshot; and share-codex is a
non-probability sample of eight 16-row blocks from a 4,333-row corpus. No
hypothesis test, employee-level inference, or population extrapolation is
performed.

Comparability is classified before examining differences:

- **aligned:** the two adapters measure the same structural relation;
- **limited:** denominators align, but export, harness, or unit differences can
  explain the observed difference; or
- **not aligned:** the constructors define different estimands, so no
  cross-corpus difference is calculated.

## Results

| Measurement | Wisp | share-codex sparse | Comparability |
| --- | ---: | ---: | --- |
| Linked result / tool result | 2,207 / 2,207 = 100% (95% Wilson 99.8262–100%) | 6,239 / 6,239 = 100% (99.9385–100%) | Aligned |
| Observed result / tool proposal | 2,207 / 2,209 = 99.9095% (99.6705–99.9752%) | 6,239 / 6,272 = 99.4739% (99.2620–99.6251%) | Limited |
| Explicit error / tool result | 103 / 2,207 = 4.6670% (3.8630–5.6285%) | 47 / 6,239 = 0.7533% (0.5670–1.0002%) | Limited |
| Error-bearing analyzed unit | 11 / 104 = 10.5769% (6.0093–17.9531%) | 6 / 128 = 4.6875% (2.1658–9.8498%) | Limited |
| Error with candidate later success | 92 / 103 = 89.3204% (81.8820–93.9313%) | 38 / 47 = 80.8511% (67.4560–89.5841%) | Not aligned |
| Same family/name among candidates | 84 / 92 = 91.3043% (83.7697–95.5279%) | 34 / 38 = 89.4737% (75.8695–95.8297%) | Not aligned |

### What replicated

Both adapters linked every observed tool result to an explicit proposal
identifier. That is the strongest replication result: Frankengate can preserve
tool lifecycle evidence across native Claude Code content blocks and
share-codex's normalized OpenAI-style function calls.

Both corpora also contain typed explicit errors concentrated in a small set of
analyzed units:

- Wisp: 103 errors in 11 of 104 files/sessions, averaging 9.36 errors per
  error-bearing unit;
- share-codex: 47 errors in 6 of 128 sessions, averaging 7.83 errors per
  error-bearing session.

This supports a bounded review queue rather than scanning every trace with an
LLM judge. It does not mean those sessions failed.

Finally, both corpora contain error-to-later-non-error structures. That
replicates the **presence** of proposal-worthy recovery evidence, not a recovery
rate or the correctness of any recovery.

### What did not replicate as a common estimand

The Wisp episode constructor greedily assigns each explicit error to one newly
proposed, linked, non-error result within 24 records. It groups tools into
families. The share-codex pilot asks whether each error has any later non-error
result, without a record window; one later result can satisfy multiple errors,
and same-tool means the exact generic tool name.

Therefore:

- 92/103 and 38/47 are not estimates of the same event;
- 84/92 same-family and 34/38 same-name are not the same predicate; and
- overlapping Wilson intervals do not establish equivalence.

The result intentionally emits no difference, ratio, or significance test for
either recovery measurement.

## Schema and selection sensitivity

The much lower explicit-error share in share-codex—0.75% versus 4.67%—cannot
be read as better user or model performance. At least four factors are
confounded:

1. Wisp includes main-user work, benchmark development, benchmark executions,
   nested subagents, and workflow journals; share-codex rows are exported
   conversation sessions.
2. Wisp is native Claude Code; the share sample contains 121 Codex and 7 Claude
   sessions.
3. Wisp is the full released snapshot; share-codex is a clustered
   row-position sample whose event volume is dominated by a few large blocks.
4. Native and normalized exporters may differ in which failed operations
   receive an explicit `is_error` flag.

This is a useful negative result: raw error prevalence is not portable enough
to compare users, harnesses, or teams without a canonical error taxonomy and
an export-conformance study.

## Direct enterprise interpretation

The replication justifies three Frankengate mechanisms:

- ingest and correlate tool proposal/result lifecycles across harnesses;
- run cheap typed-error and incompleteness selectors before semantic models;
- create evidence-backed, proposal-only eval/recovery review queues.

It does not justify:

- deciding that a user lacks a skill;
- ranking competence or productivity;
- treating a non-error result as task success;
- recommending that unrelated users collaborate;
- automatically writing a memory, skill, or eval; or
- estimating enterprise prevalence from two unrelated public contributors.

Those questions require consented Frankengate users, common policy-aware
session units, independent task outcomes, environment/access/tool-availability
labels, human validation, and prospective interventions.

## Required next experiment

Run one canonical bounded episode constructor over both native adapters:

1. explicit proposal and result identifiers;
2. one-to-one matching;
3. fixed event/time horizon;
4. exact tool and normalized-family labels retained separately;
5. parallel-branch exclusions;
6. termination and truncation state; and
7. independent outcome/human labels.

Only then should Frankengate compare recovery precision, recall, or prevalence
across harnesses. Cross-user recommendations remain a separate prospective,
consented study even after the constructor is aligned.

## Reproduction

```bash
python3 research/trace-intelligence/cross_corpus_replication.py \
  --wisp \
    research/trace-intelligence/experiments/results/wisp-content-minimized-analysis-arms-2026-07-30.json \
  --share-codex \
    research/trace-intelligence/experiments/results/share-codex-sparse-structural-pilot-2026-07-30.json \
  --output \
    research/trace-intelligence/experiments/results/wisp-share-codex-cross-corpus-replication-2026-07-30.json
```
