# Hugging Face agent-trace discovery audit (2026-07-31)

This is a discovery inventory, not an admission decision and not a download of
raw traces. It records public candidates that can expand the independent and
composed experiments. Raw material remains outside Git until revision, license,
provenance, and adapter checks pass.

## Candidates found

| Candidate | What it adds | Initial research use | Boundary |
|---|---|---|---|
| [trace-commons/agent-traces](https://huggingface.co/datasets/trace-commons/agent-traces) | Voluntarily contributed Claude Code, Codex, and Pi sessions with prompts, responses, tool calls, and command output | Native-history, memory-file, tool-correlation, and user-history import | Public contribution does not imply enterprise representativeness; use the pinned Trace Commons cohorts already admitted in the manifests |
| [thoughtworks/agentic-coding-trajectories](https://huggingface.co/datasets/thoughtworks/agentic-coding-trajectories) | Long coding trajectories with tool calls embedded in `messages_json` | Cross-harness schema comparison and cheap-signal replication | Generated trajectories and model/provider usage policy require a separate rights review |
| [DiscoPosse/agent-llm-traces](https://huggingface.co/datasets/DiscoPosse/agent-llm-traces) | OpenTelemetry traces across multiple agent frameworks and providers | OTel-to-canonical retention, tool-span coverage, and backend parity | Synthetic/benchmark mixture; do not treat as real-user behavior without provenance strata |
| [NJU-LINK/CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench) | 4,316 coding-agent trajectories with step-level diagnosis annotations | AgentRx/Signals/AgentEvals comparison and decisive-step labels | Curated benchmark selection is not natural failure prevalence; existing pinned analysis remains the authority |
| [juliensimon/agent-traces-code-review-pipeline](https://huggingface.co/datasets/juliensimon/agent-traces-code-review-pipeline) | Multi-agent workflow traces with deviation labels such as wrong tool, repeated activity, timeout, and missing handoff | Ordered/unordered assertions, OpenRCA-style event analysis, and collaboration failure taxonomy | Workflow simulation labels are not human productivity or skill labels |
| [HF agent-trace dataset index](https://huggingface.co/datasets?format=format%3Aagent-traces) | Additional Claude Code, Codex, Pi, Fable, and personal-session candidates | Discovery queue for real-user and researcher strata | Each item still needs independent revision/license/PII/provenance admission; index presence is not permission to ingest |

## What this changes

The previous program already contains admitted Trace Commons, Fable, CodeTraceBench,
NL2SQL, RL, and researcher-oriented cohorts. This audit adds a prioritized queue,
not a new architecture or a PII-centered policy. The next empirical batch should
run the same canonical projection and deterministic Signals/AgentRx/AgentEvals
contracts across three strata:

1. native user sessions (Trace Commons/Fable and any rights-cleared personal
   uploads);
2. OTel-native multi-framework traces (DiscoPosse);
3. labeled workflow/diagnosis benchmarks (CodeTraceBench and the code-review
   pipeline).

Metrics must remain separate for schema retention, selector precision at fixed
review budget, diagnosis/eval construct validity, memory/skill intervention
outcomes, RLS/deletion closure, and operational cost. No dataset in this inventory
supports claims about employee skill, intent, collaboration fit, or enterprise
causality by itself.

## Admission gate

Before any download or model call, freeze the dataset revision and license text,
record source and contributor provenance, run the existing manifest validator and
native adapter, hash the raw cache outside Git, and produce only aggregate results.
Candidates lacking a clear license or provenance remain discovery-only rather than
being treated as implicitly approved.

## Metadata follow-up

The live dataset cards provide two useful admission refinements. DiscoPosse is
listed as CDLA-Permissive-2.0, has 1,780 rows, and exposes nested OTel spans with
harness, benchmark, model, token, session, and collection-time fields. It is the
best next candidate for a schema/projection experiment, but its revision and
provenance hash still need freezing before download. ThoughtWorks is listed as a
15,000-row derivative, multi-source corpus; its card explicitly says the traces
are synthetic/replay data, no live tools are present, and each row inherits its
upstream license. It is therefore useful for context-growth and schema stress,
but not a real-user or enterprise-behavior cohort. The code-review pipeline
remains a labeled workflow stratum pending the same revision/license freeze.
