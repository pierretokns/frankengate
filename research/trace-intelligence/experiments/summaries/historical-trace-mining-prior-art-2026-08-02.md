# Historical Claude/Codex trace mining: prior art and research contract

This note records the sub-agent survey that complements the executable native
Claude/Codex screens. The exact integrated system is still an open empirical
question.

## Closest adjacent work

The closest direct precedents found in the independent survey are older
enterprise skill-mining and process-mining systems rather than modern agent
memory libraries:

- [IBM Cross-training and its application to skill mining](https://research.ibm.com/publications/cross-training-and-its-application-to-skill-mining)
  learns organization skills from electronic communications under train/test
  distribution shift and explicitly requires a continuously maintained skill
  catalog.
- [Mining resource profiles from event logs](https://research.tue.nl/en/publications/mining-resource-profiles-from-event-logs/)
  mines employee skills, preferences, productivity, and collaboration from
  event logs and validates the profiles against an industrial organization.
- [From digital traces to competences](https://www.sciencedirect.com/science/article/pii/S2405896322020018)
  maps industrial activity traces to mobilized competences. It is direct
  precedent for trace-to-skill inference, but not for agent trajectories or
  replayable evals.
- [Nalanda: a socio-technical graph for enterprise software analytics](https://arxiv.org/abs/2110.08403)
  links artifacts, repositories, and experts at enterprise scale and reports
  top-three recommendation accuracy. It is a strong artifact/expert graph
  building block, not a cross-source chat-trace learning loop.

These works mean Frankengate should not claim first corporate skill mining.
The plausible gap is narrower and more defensible: a provenance-preserving
loop that aligns heterogeneous agent traces, artifacts, latent intent and
friction, temporal skill updates, domain-specific retrieval, and replayable
evaluation with human/SME adjudication.

### New adjacent system: Google Science One / ScientistOne

[Science One](https://research.google/blog/science-one-framework-a-verifiable-autonomous-research-framework-via-chain-of-evidence/)
and its [ScientistOne paper](https://arxiv.org/abs/2605.26340) are the closest
recent reference for the *evidence layer*, not for corporate trace mining. They
make every research claim point to a concrete source artifact, retain raw
evaluator outputs from isolated explore/exploit branches, and audit score
reproducibility, specification violations, reference validity, and
method–code alignment. We should adapt that contract to trace-derived insights,
skill candidates, and eval candidates. It does not solve latent enterprise
intent, corporate alias discovery, embedding adaptation, or prove that a
trace-mined skill transfers; those remain our empirical questions. The detailed
mapping and required receipt fields are in
`experiments/summaries/science-one-chain-of-evidence-adaptation-2026-08-02.md`.

- [Anthropic Claude Code expertise analysis](https://www.anthropic.com/research/claude-code-expertise)
  and [Anthropic internal usage analysis](https://www.anthropic.com/research/how-ai-is-transforming-work-at-anthropic)
  infer task expertise/modes and trouble from transcript structure, prompts,
  files, errors, failed tests, repeated attempts, and frustration signals.
- [Cursor semantic search](https://cursor.com/blog/semsearch) and
  [CursorBench](https://cursor.com/blog/cursorbench) use historical sessions
  to label what should have been retrieved earlier, then train a custom
  embedding model from those labels.
- [Follow-up/reformulation mining](https://arxiv.org/abs/2407.13166) defines
  18 reformulation/friction categories and finds dissatisfaction-correlated
  clarifying, excluding-condition, and substituting-condition follow-ups.
- [IBM weak supervision](https://research.ibm.com/publications/bootstrapping-conversational-agents-with-weak-supervision),
  [intent mining](https://arxiv.org/abs/2005.11014), and
  [NAACL intent discovery](https://aclanthology.org/2022.naacl-main.134/)
  support clustering and weak labels, with SME sampling needed for naming and
  calibration.
- [SWE-bench](https://arxiv.org/abs/2310.06770) and
  [SWE-Gym](https://arxiv.org/abs/2412.21139) show how descriptions, repository
  state, patches, tests, and trajectories become replayable eval packets.
- [OpenAI’s benchmark audit](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)
  demonstrates why generated cases need automatic and human validity gates.
- [TraceLab](https://tracelab.cs.washington.edu/) is a useful public proxy
  corpus: 665k Claude/Codex steps, 8,058 sessions, and 743k tool calls.
- Process-mining work ([discovery](https://arxiv.org/abs/1705.02288),
  [trace encoding](https://arxiv.org/abs/2301.02167),
  [multi-perspective clustering](https://emisa-journal.org/emisa/article/view/204))
  contributes deterministic segmentation, workflow variants, conformance, and
  anomaly detection, but cannot recover hidden business intent by itself.

## Research contract

1. Normalize provider-specific JSONL/events into session → turn → action DAGs,
   preserving tool calls, outputs, files, diffs, tests, branches, timestamps,
   and provenance.
2. Segment episodes with deterministic process-mining boundaries plus frontier
   adjudication; expose boundary confidence and an explicit
   `unknown/needs-user` state.
3. Infer intent, constraints, target systems, expected artifacts, and missing
   information with evidence spans and confidence.
4. Separate productive iteration (scope refinement, clarification,
   exploration) from friction (repair loops, failed assertions, denials,
   stagnation, overrides, reverts, abandonment, latency, and dissatisfaction).
   Repeated prompts alone are not failure truth.
5. Produce eval work packets with an evidence slice, normalized intent,
   expected artifact, deterministic validators, counterfactual/negative cases,
   replay inputs, and source provenance.
6. Use weak labels and small-model screening for triage only; use frontier
   adjudication and stratified SME review for intent naming, ambiguity, and
   benchmark validity.
7. Replay failure/recovery/benign pairs under user, repository, time, and
   task-family holdouts. Measure friction precision, intent agreement, eval
   validity, replay determinism, and improvement over baseline.
8. Promote only validated evals or validated repairs/skills. Do not auto-release
   raw summaries or uncertain inferred intent.
9. Measure what logs cannot establish without the user: hidden business
   objective, acceptable trade-offs, undocumented success criteria, and whether
   a repeated prompt reflects dissatisfaction or deliberate refinement.

Every inferred intent/eval must carry `intent_basis`, confidence, evidence
references, source hashes, episode-boundary confidence, validator type, reviewer
provenance, and an `unknown/needs-user` reason when evidence is insufficient.

## Publication and partnership path

The work is best split across established communities rather than pitched as
one generic “agent memory” paper:

1. **ICPM/BPM or ACM TMIS:** event abstraction, resource/skill profiles,
   process variants, conformance, and friction detection. The primary result
   should be trace-to-competence and friction precision with SME validation.
2. **ACL/EMNLP Industry Track or SIGDIAL:** intent discovery, corporate alias
   and hard-negative mining, domain-specific embeddings, and the
   embedding-versus-model cascade. Report human agreement, transfer recall,
   calibration, and deletion/tenant-stratified checks.
3. **MSR or CHI/CSCW:** developer/worker trace interpretation, friction
   dashboards, user agency, and whether suggested skills/evals actually help
   people. Include interviews or controlled human review rather than inferring
   competence from activity volume.

The collaboration ask should be a reproducible benchmark and methods study,
not access to private employee logs: publish content-minimized receipts,
synthetic or licensed traces, task/family holdouts, mutation generators,
independent verifiers, and a schema/lineage contract. Keep raw enterprise
content private and offer partner researchers a sealed evaluation API or
derived, license-cleared corpus.

This note is linked to issues #125–#129 and is a research design, not a claim
that any one detector, embedding model, or memory system solves intent mining.

The 2025–2026 literature update adds a particularly relevant enterprise
hard-negative precedent and several full skill-lifecycle systems. See
`experiments/summaries/skill-hard-negative-prior-art-update-2026-08-02.md` for
the exact/adjacent split and the revised frozen alias/embedding/replay protocol.

The newer lifecycle comparison is recorded in
`experiments/summaries/skill-library-prior-art-update-2026-08-02.md`. SkillFlow
and SkillLearnBench are especially useful controls because they report both
positive transfer and model/task-dependent failure; SkillFoundry and
MUSE-Autoskill contribute tested, provenance-carrying, per-skill lifecycle
ideas. None combines private multi-user traces, corporate alias collisions,
governed artifact capsules, and changed-system replay.

The partner and publication mapping is in
`experiments/summaries/publication-partner-opportunities-2026-08-02.md`. It
prioritizes the CMU SkillLearnBench team for continual-learning protocol work,
MIT DSAIL for learned enterprise data systems, Harvard CHARM/CRCS/DASlab for
human outcomes and data-system boundaries, and MIT CLEAR/TRAC for trustworthy
agent evaluation. These are fit recommendations, not commitments.

The partner and publication shortlist is in
`experiments/summaries/publication-partner-opportunities-2026-08-02.md`. It
recommends CMU LTI/SkillLearnBench and MIT DSAIL for the first methods/data
systems reproduction, followed by Harvard CHARM/Variation Lab for human
agency and learning outcomes, with MIT CLEAR/TRAC for accountability and
feedback design.
