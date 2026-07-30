# Hugging Face NL2SQL trace audit

This is an aggregate structural and replay-readiness audit over two pinned real
action/observation corpora. Raw prompts, SQL, tool arguments, observations,
answers, task identifiers, and trace identifiers remain outside Git.

## Result

| Corpus | Tasks | Recorded runs | Tool transitions | Mean recorded reward | Replay status |
| --- | ---: | ---: | ---: | ---: | --- |
| WMH BIRD-SQL | 222 train + 20 test over 11 databases | 1,993 | 4,168 | 0.674862 | Reconstructable from the external BIRD mini-dev database archive; not self-contained on Hugging Face |
| WMH CRMArena | 45 train + 18 test over 9 task types in one org | 80 | 553 | 0.734863 | Reconstructable from the official CRMArena SQLite dump; non-commercial research only |

All 222 BIRD and all 45 CRMArena train tasks have recorded runs. Neither
corpus contains a recorded test task. The trace files contain paired tool
arguments and true environment observations with no malformed rows or duplicate
span IDs.

They are not full OpenTelemetry or complete agent-history evidence:

- every one of 9,442 audited spans has an empty `parentSpanId`;
- timestamps are ordinal counters with maxima of 103 and 153 nanoseconds, not
  wall-clock timestamps;
- there is no full assistant narrative/reasoning field; and
- the files use one flattened span object per JSONL row rather than an OTLP
  `resourceSpans` export envelope.

They therefore support ordered action/observation mining after a source-specific
adapter. They do not support latency analysis, distributed-causal reconstruction,
or exact full-conversation replay.

## Experimental role

Use BIRD-SQL as the primary real trace-mining corpus and as a reconstructable
SQLite replay arm. Before candidate generation, partition by database family and
withhold both tasks and traces for the visible-selection and hidden-test
families. The upstream train/test split is task-disjoint but not schema-family
disjoint.

Use CRMArena as a non-commercial enterprise-analytics control. It has realistic
case routing, handle-time, transfer, entity-disambiguation, policy, and knowledge
questions, but only one org and a SQLite substitute for upstream SOQL. It cannot
support a cross-schema-transfer or commercial-training claim.

Use the locally executable Defog/PostgreSQL families for the immediate causal
skill factorial. Defog supplies reproducible databases and gold SQL but no
natural trajectories; the WMH corpora supply real procedures and failures but
need external environments. Combining these evidence classes is stronger than
pretending that either one alone is complete.

MAGIC, the PT-BR distilled tool trajectories, and Analyst Buddy remain candidate
procedure-mining or qualitative controls:

- MAGIC has 48,124 feedback/correction/manager rows but no raw environment
  transitions or database snapshot.
- The PT-BR corpus has 7,442 distilled `get_table_schema`, `execute_sql`, and
  `final_answer` message sequences, but correctness is LLM-selected and the
  environments are absent.
- Analyst Buddy has only six paired base/fine-tuned tasks on one synthetic
  database.

None may serve as the independent outcome oracle for a released Frankengate
skill.

## Reproduce

Download the three pinned BIRD and CRMArena files named in
`configs/datasets/wmh-{bird-sql,crmarena}-traces.json` to external roots. Then run:

```sh
python3 hf_nl2sql_trace_audit.py \
  --bird-root /private/path/bird \
  --bird-manifest configs/datasets/wmh-bird-sql-traces.json \
  --crmarena-root /private/path/crmarena \
  --crmarena-manifest configs/datasets/wmh-crmarena-traces.json \
  --output experiments/results/hf-nl2sql-trace-audit-2026-07-30.json
```

The runner fails closed on any hash mismatch and emits aggregate structure only.
