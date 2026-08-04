# DataClaw identifier-aware retrieval audit

## Question

Do exact path/file identifier surfaces add useful signal beyond prompt words and
normalized command shapes when retrieving related work from a long coding
history? This is a project-recurrence proxy, not a semantic task benchmark.

## Dataset and split

- Dataset: `ronaldcmz/Claude-Opus-Dataclaw-Unredacted`
- Pinned revision: `918e6fb39c916d3459ef338b4c3645622b9a5126`
- 436 sessions, 46 projects
- Per-project chronological 70/30 split: 279 training sessions, 141
  evaluation sessions, 30 projects with both sides; 16 single-session projects
  were excluded.
- Features were content-free: prompt word sets, normalized command-shape sets,
  and conservative lowercase path-basename surfaces. Raw text, paths, and
  project names were not emitted or committed.

Receipt: [dataclaw-ronald-identifier-aware-retrieval-2026-08-02.json](../results/dataclaw-ronald-identifier-aware-retrieval-2026-08-02.json)

For each held-out session, every earlier training session was ranked by binary
Jaccard overlap or a fixed weighted combination. The silver label was whether
the top retrieved session came from the same project. We report candidate
coverage, same-project Recall@1/5, MRR, and wrong-project rate among covered
queries.

## Results

| Arm | Candidate coverage | Same-project R@1 | Same-project R@5 | MRR | Wrong-project top-1 when covered |
|---|---:|---:|---:|---:|---:|
| Prompt terms | .986 | .461 | .652 | .551 | .532 |
| Command shapes | .688 | .340 | .433 | .392 | .505 |
| Path identifiers | .596 | .333 | .426 | .377 | .440 |
| Prompt + identifiers | 1.000 | .496 | .738 | .598 | .504 |
| Prompt + shapes | 1.000 | .511 | .674 | .590 | .489 |
| Prompt + shapes + identifiers | 1.000 | **.567** | **.766** | **.657** | **.433** |

The combined arm improved the project-similarity proxy over prompt-only by
`.106` absolute in both Recall@1 and MRR, and by `.113` in Recall@5. Adding
identifiers alone improved MRR by `.047`; adding shapes alone improved MRR by
`.039`. Path identifiers had lower standalone coverage, but the best standalone
top-1 precision when covered (`.560`) and contributed incremental signal in the
combined arm.

## Interpretation

This supports a concrete representation decision: retain exact identifier
surfaces and scope/project metadata as a separate retrieval lane beside text
and normalized procedure features. A dense vector should not be the only
representation for corporate traces; identifier features can improve recall of
related scoped work and reduce wrong-project top-1 choices in this proxy.

It does **not** show that sessions share business intent, that a path basename
is an alias, or that a retrieved artifact is correct. Project recurrence is a
silver label and may reward repository boilerplate, author habits, or the same
project's unrelated tasks. The fixed Jaccard weights were not tuned on a held-out
label set, and no independent terminal outcome is present.

## Architecture consequence

Use a multi-lane candidate generator:

```text
exact identifiers + scope
        + prompt lexical terms
        + normalized command/tool shapes
        + optional dense retrieval
        -> candidate union
        -> authority/NIL/temporal checks
        -> frontier or human review for ambiguity
        -> independent replay or prospective outcome
```

Do not collapse these fields into one embedding or allow project recurrence to
authorize an artifact. The next required test is a reviewed, task-disjoint
collision set with same-work, alias, unrelated, and NIL labels, followed by
replay and wrong-system measurements.

## Reproduction

```text
ruby dataclaw_identifier_aware_retrieval_audit.rb \
  /private/tmp/ronald-dataclaw-openai.jsonl \
  experiments/results/dataclaw-ronald-identifier-aware-retrieval-2026-08-02.json
```

