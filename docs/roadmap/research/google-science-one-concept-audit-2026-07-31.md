# Google “Science One” / Gemini for Science concept audit (2026-07-31)

## Identification

I could not verify a Google product literally named **Science One** in the
current Google Research/DeepMind material. The closest current releases are
**Gemini for Science**, its **Computational Discovery** tool, and the
Google DeepMind **Co-Scientist** system. “ScienceOne” also refers to a
separate Chinese Academy of Sciences platform and to the independent
ScienceOne-AI model family; those are not Google products.

Google describes Co-Scientist as a multi-agent system that generates, debates,
and evolves hypotheses, with researcher participation and experimental
validation. Gemini for Science combines research-oriented tools and “Science
Skills” around computational discovery. These are workflow/orchestration
concepts, not trace schemas or memory databases.

## Relevance to Frankengate

| Science concept | Frankengate analogue | What must be added to the evidence model |
|---|---|---|
| Hypothesis generation | Trace → diagnosis/eval proposal | Explicit hypothesis ID, source evidence IDs, alternatives, confidence, and abstention |
| Multi-agent debate | Independent selectors/judges | Agent-role identity, disagreement graph, model/version, and no self-confirming release path |
| Evolution/refinement | Memory/skill candidate lifecycle | Versioned candidate lineage, exposure assignment, rollback, and held-out outcome |
| Experiment design | AgentEvals + changed-system replay | Preregistered intervention, control, environment snapshot, tool/menu state, and evaluator authority |
| Literature/tool grounding | Enterprise trace + exact search | Source provenance, retrieval query, citation/evidence links, and authorization scope |
| Human scientist loop | Admin/user review queue | Human decision, correction, ownership, and feedback influence receipt |

## Hard boundary

The scientific-workflow framing does not justify autonomous “dreaming,” memory
promotion, skill release, or enterprise recommendations. A proposed hypothesis
is not a diagnosis; debate is not independent evidence when the agents share the
same trace and model; and a later success is not a causal intervention result if
the generated skill or memory influenced it. Frankengate should therefore import
the workflow lifecycle—hypothesis → evidence packet → controlled experiment →
human decision → versioned outcome—without importing an autonomous self-improvement
loop before the existing influence-quarantine and held-out gates pass.

## Research action

Add a future C7 study using the existing governed PostgreSQL authority:

1. generate competing trace-derived hypotheses with deterministic evidence IDs;
2. run two independent proposal policies plus a no-proposal control;
3. adjudicate novelty, evidence sufficiency, and alternative explanations;
4. execute only preregistered changed-system experiments;
5. measure held-out outcome, human correction, cost, latency, deletion closure,
   and whether the proposal influenced the evaluation data.

This is a compositional extension of Signals → AgentRx → AgentEvals, not a new
database or a reason to expose raw traces to a third party.

## Sources

- [Google DeepMind: Co-Scientist](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/)
- [Google Research: Gemini for Science / Computational Discovery](https://research.google/blog/a-new-era-of-innovation-google-research-at-io-2026/)
- [Google: new AI tools for science](https://blog.google/innovation-and-ai/technology/research/gemini-for-science-io-2026/)
- [Nature coverage of Co-Scientist and Robin](https://www.natureasia.com/en/info/press-releases/detail/9330)

