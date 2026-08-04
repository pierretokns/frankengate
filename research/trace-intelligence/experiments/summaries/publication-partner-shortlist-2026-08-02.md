# Publication and partner shortlist

This is a fit assessment, not an endorsement or evidence of a collaboration.
The strongest path is a multi-site methods paper with a sealed enterprise
evaluation API and a public synthetic/licensed companion corpus.

## Best-fit groups

| Partner | Evidence of fit | Proposed contribution | What we must bring |
|---|---|---|---|
| **CMU LTI / SkillLearnBench authors** | [SkillLearnBench](https://arxiv.org/abs/2604.20087) evaluates skill quality, trajectories, and task outcomes; its [code is public](https://github.com/cxcscmu/SkillLearnBench). CMU LTI explicitly covers information retrieval, QA, text mining, knowledge representation, and trustworthy language technology ([LTI](https://www.lti.cs.cmu.edu/about-lti/index.html)). | Adapt the three-level benchmark to governed SQL/tool artifacts and study external-teacher versus self-feedback under real schema/authority constraints. | A sealed, content-minimized trace/eval API; Defog/BIRD-derived public tasks; independent verifier and preregistered controls. |
| **MIT DSAIL / database systems community** | MIT's [DSAIL](https://dsg.csail.mit.edu/dsail/) focuses on learned components in data systems and explicitly studies enterprise applications and data preparation. | Measure artifact reuse, schema drift, query-plan changes, RLS/deletion behavior, and workload/latency tradeoffs in PostgreSQL/Aurora-like systems. | Disposable Postgres harness, capsule contract, plan/latency receipts, and a changed-system replay suite. |
| **Harvard CHARM / Variation Lab** | [CHARM](https://charm.seas.harvard.edu/) focuses on human-driven AI and whether people are stronger after using an AI system; the [Variation Lab](https://glassmanlab.seas.harvard.edu/) studies AI-resilient interfaces and human sensemaking. | Study whether trace-derived friction/eval/skill suggestions improve user judgment and learning rather than merely task completion. | A consented UX protocol, user-facing explanations, opt-in controls, and human outcome measures. |
| **Harvard DASlab** | [DASlab](https://daslab.seas.harvard.edu/) works on evolving data systems, repeated access, adaptive indexing, and data-management infrastructure. | Explore the minimal storage/query architecture for trace artifacts, structured metadata, and repeatable retrieval without prematurely adding a separate vector system. | Workload traces, storage/latency benchmarks, and explicit deletion/RLS requirements. |
| **MIT CLEAR / TRAC** | [CLEAR](https://clear.csail.mit.edu/) studies agents learning with people; [TRAC](https://trac.csail.mit.edu/) focuses on trustworthy, robust, intelligible, accountable AI. | Formalize the human-feedback, uncertainty, abstention, and accountability layer around skill promotion and cross-user suggestions. | Human-review packets, audit receipts, threat model, and negative-transfer cases. |

## Recommended first outreach

Start with one CMU LTI/SkillLearnBench contact and one MIT DSAIL contact. The
first joint artifact should be a 6–8 week reproduction package, not a request
for private data:

1. freeze a public or synthetic SQL/tool family with 20–40 tasks;
2. expose the same trajectory-to-artifact API to one-shot, self-feedback,
   teacher-feedback, and Trace2Skill-style methods;
3. require skill-quality, trajectory-quality, and changed-task outcome metrics;
4. add explicit same-surface/wrong-scope hard negatives, schema drift, and
   stale-authority cases;
5. publish hashes, manifests, receipts, and verifiers while keeping any
   enterprise content behind a sealed endpoint.

Only after that should Harvard CHARM/Variation Lab run the human-learning and
user-agency arm. That keeps a productivity or “skill gap” claim from being
smuggled in through offline retrieval metrics.

## Publication framing

The defensible paper claim is not “memory makes agents better.” It is:

> A governed trajectory-to-artifact system can identify reusable procedures,
> expose corporate alias hard negatives, and reject unsafe or non-transferring
> artifacts through independent changed-system replay.

This supports an ACL/EMNLP Industry Track or SIGIR paper for retrieval and
hard negatives, a SIGMOD/MLSys paper for governed data-system execution, and a
CHI/CSCW paper for human feedback and user agency. A single paper should not
claim all three without the corresponding labels and prospective outcomes.
