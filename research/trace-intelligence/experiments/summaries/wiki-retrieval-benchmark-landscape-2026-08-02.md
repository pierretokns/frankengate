# Wiki retrieval and agentic-RAG benchmark landscape — 2026-08-02

## Bottom line

There is still no public, standardized benchmark that compares **Claude Code
or Codex as a harness** against filesystem search, MCP, and a vector database
over the same Karpathy-style wiki. The closest work separates the pieces:

| benchmark or system | what it measures | what it does not settle for Frankengate |
|---|---|---|
| [Agent Retrieval Bench](https://agent-retrieval-bench.github.io/) | 427 repository-context retrieval cases across 25 repositories, with MRR, Recall@20, an 8K-token budget metric, and selective/no-gold cases | coding-repository context, not a maintained wiki, MCP transport, or final answer grounding |
| [MCP-Bench](https://arxiv.org/abs/2508.20453) | 28 live MCP servers/250 tools, fuzzy tool selection, multi-step planning, cross-tool execution, and trajectory-level completion | tool use broadly, not wiki evidence retrieval or corpus-size saturation |
| [VAKRA](https://ibm-research-vakra.hf.space/) | executable API and knowledge-retrieval tasks, 3–7 steps, multi-hop/multi-source reasoning, policy adherence, and replay-based grounded scoring | public API fixtures rather than a persistent, evolving wiki |
| [TREC RAG](https://trec-rag.github.io/) | unified retrieval and grounded-answer tasks with separate retrieval and RAG tracks | not a coding-agent/MCP harness comparison |
| [RAGCap-Bench](https://arxiv.org/abs/2510.13910) | intermediate capabilities and error taxonomy for agentic RAG | does not model a persistent wiki or Claude/Codex tool permissions |
| [AgenticRAG](https://www.microsoft.com/en-us/research/publication/agenticrag-agentic-retrieval-for-enterprise-knowledge-bases/) | enterprise knowledge-base agentic retrieval; its ablations report a large gain from iterative tool use, multi-query search, and in-document navigation | the reported harness/backend are not our wiki or enterprise trace corpus |
| [tau-knowledge](https://sierra.ai/blog/tau-knowledge) | realistic knowledge-base search + multi-step policy execution over 698 documents; reports first-try and reliable-pass rates for frontier agents | support-policy domain, not an open wiki or coding harness |
| [LLM-Wiki / Retrieval as Reasoning](https://arxiv.org/abs/2605.25480) | compiles sources into linked pages, exposes search/read/link-following tools, and maintains an Error Book; reports results on HotpotQA, MuSiQue, 2WikiMultiHopQA, and AuthTrace | the paper does not compare Claude Code/Codex, native MCP transport, or multi-wiki tool routing |

The Karpathy-style wiki is a **knowledge-state and maintenance pattern**, not
an evaluation protocol. A persistent Markdown/wiki layer may improve repeated
cross-document questions, but it adds compilation quality, staleness, alias,
and contradiction failure modes that a flat vector benchmark can hide.

## What we have now tested locally

The branch contains a deterministic 25-wiki fixture and an identical
`search → get_page → expand_links → finish` contract over FTS, TF-IDF, and
hybrid backends. The frontier Codex loop keeps model, question set, five-step
budget, and corpus sizes (1/5/10/25 wikis) fixed.

The same-model backend factorial is recorded in
[`wiki-frontier-gpt55-backend-factorial-2026-08-02.md`](wiki-frontier-gpt55-backend-factorial-2026-08-02.md):

| backend | target answer | gold page loaded | NIL abstention | errors | finished |
|---|---:|---:|---:|---:|---:|
| FTS | 16/16 | 20/20 | 1/4 | 1 | 19/20 |
| TF-IDF | 16/16 | 19/20 | 4/4 | 0 | 20/20 |
| hybrid | 16/16 | 20/20 | 4/4 | 0 | 20/20 |

This does **not** show that all backends are equivalent. It shows that the
frontier model repaired ranking differences on this easy fixture, while
retrieval coverage, NIL safety, and execution reliability still differed.
FTS produced three NIL false accepts and one failed case; TF-IDF and hybrid
abstained on all NILs. The result supports a hybrid/identifier-aware retrieval
cascade with an explicit abstention gate, not a model-only search policy.

The direct transport probe already found ranking parity of 1.0 between the
local retrieval function and the JSON-RPC MCP-shaped server, with only a small
sub-millisecond local protocol overhead. That is a protocol result, not an
end-to-end Claude/Codex result. Native Codex MCP calls were canceled before a
usable score, and Claude Code is installed but unauthenticated in this
environment; neither has a claimed score here.

## What a fair next benchmark must add

1. **Three interfaces, one backend:** raw filesystem search, one federated MCP
   server, and a direct retrieval API. Repeat with FTS, dense, hybrid, and a
   compiled wiki. MCP must not be treated as a retrieval algorithm.
2. **Tool topology:** compare one federated search tool with one tool per wiki;
   record tool-description tokens, selection errors, and wrong-wiki results.
3. **Question strata:** exact identifiers, paraphrases, aliases/acronyms,
   multi-hop link traversal, cross-wiki collisions, stale/conflicting pages,
   enumeration, and NIL/no-gold questions.
4. **Outcome metrics:** page/evidence Recall@1/5/20, MRR, nDCG, evidence
   coverage, final answer correctness, citation correctness, NIL precision and
   recall, valid/invalid calls, turns, truncation, p50/p95 latency, tokens,
   cost, index build/update lag, and stale-answer rate.
5. **Scale curve:** hold the query set and model budget fixed while growing
   from 1 to 5, 10, 25, 50, and 100 wikis. Define saturation as a pre-registered
   quality, tail-latency, token, or cost threshold—not merely a larger index.
6. **Two corpora:** first a public Wikipedia/HotpotQA/MuSiQue-style corpus for
   reproducibility; then a consented enterprise-like wiki with identifiers,
   aliases, versioned facts, and access-controlled pages.
7. **Harness runs:** when authenticated sessions are available, run the same
   manifest through Codex and Claude Code with native MCP. Record model/version,
   reasoning mode, permissions, tool-search settings, and cancellation/error
   semantics. Until then, the structured Codex loop is a useful proxy but must
   not be mislabeled as native MCP evidence.

## Architectural hypothesis to test

The likely smallest useful Frankengate shape is one federated, permission-aware
MCP interface backed by exact/identifier search plus dense or hybrid retrieval,
with explicit page reads, bounded link traversal, citations, version metadata,
and a conservative NIL/staleness gate. A compiled wiki/Error Book layer should
be added only if it improves held-out multi-document and repeated-query tasks
at the same cost and freshness budget. Public results support this hypothesis,
but they do not prove it for our enterprise corpus.

