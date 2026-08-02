# TRAJECT-Bench separate-explorer probe (2026-08-09)

This is an independent test of the *separate exploration* idea described by
FastContext. It does not reproduce FastContext's withdrawn code or numerical
claims. A frontier explorer saw the complete domain-scoped public tool pool and
returned a compact ordered shortlist. It did not see target labels, tool
outputs, or execution outcomes, and no endpoint was invoked.

## Protocol

- Eight hard public cases, one each from Education, Email, Finance, Gaming,
  Mapping, Music, News/Media, and Travel.
- Full pool: 70–258 tools per case, mean `126.375`.
- Explorer: Luna (`gpt-5.6-luna`), at most 16 selected tools, with a short
  evidence reason for each selected item.
- Baselines: deterministic name-only and name-plus-description lexical top-16
  shortlists over the same full pool.
- Two independent runs with different run labels; all 16/16 frontier calls
  completed and were independently verified.

## Results

| Arm | Candidate coverage | MRR | Recall@1 | Recall@5 | Recall@10 | Mean selected |
|---|---:|---:|---:|---:|---:|---:|
| Lexical name (both runs) | .500000 | .322917 | .041667 | .250000 | .458333 | 16.0 |
| Lexical name + description (both runs) | .500000 | .373512 | .083333 | .125000 | .375000 | 16.0 |
| Explorer, run 1 | .750000 | .812500 | .250000 | .750000 | .750000 | 3.75 |
| Explorer, run 2 | .708333 | .750000 | .250000 | .708333 | .708333 | 3.875 |
| Explorer mean | **.729167** | **.781250** | **.250000** | **.729167** | **.729167** | **3.8125** |

The explorer improved target coverage by `+.229167` over both lexical arms and
returned roughly four tools instead of sixteen. Mean prompt size was about
45.9k characters because the full pool was supplied; the response itself
averaged about 0.5k characters. Per-call latency and provider billing were not
recorded in this v1 probe, so the compression result is not yet a cost claim.

Shortlist stability was mixed but usable: mean selected-set Jaccard across the
two runs was `0.783036`. Exact agreement occurred on Education, Finance, and
Music; Mapping was the least stable case. This is why the explorer remains a
candidate-generation arm rather than an authority decision.

## Interpretation

This is the first direct evidence in the packet that a separate frontier
explorer can improve **candidate coverage**, not merely reorder an already
covered shortlist. It complements the earlier no-target-append reranker, where
Luna improved MRR but candidate coverage stayed fixed at `.458333`.

The result is still only a public tool-selection proxy:

- benchmark target tool lists are not enterprise intent or semantic-alias
  labels;
- the full-pool prompt is expensive and was not measured in dollars or time;
- no principal, authority epoch, refusal reason, artifact version, or changed
  system is present; and
- no artifact was accepted or replayed.

## Frankengate decision

Keep a separate explorer as an **optional candidate-generation stage** after
scope and authorization filtering. Feed it typed identifiers and compact
metadata, cap its output, retain its evidence spans, and route its shortlist
through deterministic compatibility checks and independent replay. Do not let
it publish a skill, SQL artifact, alias, or memory entry.

The next enterprise experiment should replace public target lists with exposed
tool/SQL candidates and compare:

1. no explorer;
2. lexical/identifier retrieval;
3. explorer shortlist;
4. explorer plus frozen dense recall; and
5. explorer plus replay-validated promotion.

Use principal/project/system/time holdouts, same-surface wrong-system and NIL
cases, changed authority/schema fixtures, and independent human utility labels.

## Receipts

- [run 1 result](../results/traject-bench-explorer-probe-2026-08-09.json)
- [run 1 verification](../results/traject-bench-explorer-probe-verification-2026-08-09.json)
- [run 2 result](../results/traject-bench-explorer-probe-r2-2026-08-09.json)
- [run 2 verification](../results/traject-bench-explorer-probe-r2-verification-2026-08-09.json)
- [repeated-run aggregate](../results/traject-bench-explorer-probe-aggregate-2026-08-09.json)
- [aggregate verification](../results/traject-bench-explorer-probe-aggregate-verification-2026-08-09.json)
- [runner](../../traject_bench_explorer_probe.py)
- [verifier](../../verify_traject_bench_explorer_probe.py)
- [aggregate runner](../../aggregate_traject_bench_explorer_probe.py)
- [aggregate verifier](../../verify_traject_bench_explorer_aggregate.py)

Raw frontier outputs remain external under `/private/tmp`; only hashes and
aggregate metrics are committed.
