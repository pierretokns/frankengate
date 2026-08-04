# DataClaw memory/skill-write within-project permutation audit

## Question

The earlier pooled audit found much higher later command-shape recurrence after a
memory/skill-file write. Is that association only a project-mix artifact, or
does it remain unusual after comparing sessions within the same project?

## Method

- Dataset: `ronaldcmz/Claude-Opus-Dataclaw-Unredacted`
- Pinned revision: `918e6fb39c916d3459ef338b4c3645622b9a5126`
- Sessions ordered by `start_time` within each project.
- A write is the same conservative marker + write-like-tool proxy used by the
  prior audit; command shapes and exact command digests are content-free.
- 13 projects had both pre-write and post-write observations, covering 334 of
  390 sessions after each project's first session.
- A fixed-seed 5,000-iteration permutation shuffled the prior-write labels within
  each paired project while preserving each project's number of write-positive
  observations.

Receipt: [dataclaw-ronald-memory-write-within-project-permutation-2026-08-02.json](../results/dataclaw-ronald-memory-write-within-project-permutation-2026-08-02.json)

## Results

| Signal | Pooled prior-minus-no-prior difference | Within-project macro difference | Permutation one-sided p |
|---|---:|---:|---:|
| Command-shape hit rate | `.366` | `.144` | `.0042` |
| Exact-command hit rate | `.114` | `.044` | `.0186` |

The observed pooled differences exceeded the fixed-project-count permutation
95th percentiles (`.336` for shapes and `.110` for exact commands). The null
means were already positive (`.251` and `.089`) because observation counts and
feature exposure differ between projects; therefore the small p-values should
not be read as causal evidence.

## Interpretation

The association is not explained solely by pooling projects: write-positive
sessions still show unusually high recurrence within the same project under
this permutation test. This makes memory/skill writes a useful **study
enrichment signal**—they identify transitions or sessions worth sampling for a
controlled replay.

It does not show that writing a memory or skill caused improvement. Writes are
chosen by users, happen later in a project, and may coincide with increased
activity, repeated work, a new task phase, or a harness setup change. The audit
has no semantic correctness labels, typed tool-result outcomes, or randomized
intervention.

## Decision

Keep memory/skill writes as candidate lifecycle events and sampling strata, not
as release evidence. The decisive next study remains randomized no-memory,
neutral/placebo, reviewed-memory, generated-memory, and composed arms on matched
changed-system tasks with independent replay, stale/unsafe checks, rollback,
and prospective task outcomes.

## Reproduction

```text
ruby dataclaw_memory_write_within_project_permutation_audit.rb \
  /private/tmp/ronald-dataclaw-openai.jsonl \
  experiments/results/dataclaw-ronald-memory-write-within-project-permutation-2026-08-02.json
```

