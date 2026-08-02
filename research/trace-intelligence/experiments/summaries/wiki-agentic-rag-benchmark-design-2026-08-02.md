# Wiki and agentic-RAG benchmark design — 2026-08-02

## Short answer

Yes, this is testable, but there is not currently a canonical benchmark that
does the exact comparison “Claude Code/Codex filesystem search vs MCP vs vector
database over a Karpathy-style wiki.” The study must separate two variables
that are often conflated:

1. **Interface/orchestration:** filesystem tools, one MCP server, one MCP tool
   per wiki, or a direct retrieval function.
2. **Retrieval backend:** exact/lexical, dense, hybrid, graph expansion, or a
   maintained compiled wiki.

MCP is not a retrieval algorithm. Comparing “MCP” with “vectors” without
holding the backend constant would measure interface and backend together and
would not identify the cause of an outcome.

## What the public work gives us

- Karpathy’s LLM-wiki design treats an interlinked Markdown wiki as a persistent
  compiled memory, with an index/log and optional qmd hybrid BM25/vector/MCP
  retrieval at larger scale. It reports good behavior at roughly 100 sources
  and hundreds of pages, but does not provide a controlled agent benchmark:
  [original gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
- The implementation-oriented pattern describes compilation, source lineage,
  context-size limits, and an optional MCP endpoint, again without a
  Claude-Code-versus-vector causal comparison:
  [LLM wiki pattern](https://limecloud.github.io/agentknowledge/en/reference/llm-wiki-pattern).
- Agent Retrieval Bench is the closest repository-context retrieval benchmark:
  427 samples over 25 repositories with MRR, Recall@20, context-budget, and
  no-gold/abstention measures. Its strongest embedding models beat BM25, but
  no-gold selection remains difficult:
  [Agent Retrieval Bench](https://agent-retrieval-bench.github.io/).
- USTC-CMI lists a Wiki Live Challenge and WildGraphBench, which provide
  Wikipedia-style live and external-reference QA fixtures, but not a coding
  harness or MCP comparison:
  [benchmark catalog](https://agentresearchlab.com/benchmarks/index.html).
- MCPVerse and MCPMark provide the missing tool-use dimensions—large tool
  inventories, executable tools, outcome verification, and multi-turn CRUD
  execution. They show degradation as action spaces and turns grow, but are
  not wiki-retrieval benchmarks:
  [MCPVerse](https://arxiv.org/abs/2508.16260),
  [MCPMark](https://arxiv.org/abs/2509.24002).
- MinerU Document Explorer is a useful reproducible architecture reference:
  MCP tools over a persistent document explorer with BM25, vectors, reranking,
  and wikification. It is a system reference, not evidence that the combined
  design wins on a held-out agent benchmark:
  [MinerU Document Explorer](https://github.com/OpenDataLab/MinerU-Document-Explorer).
- A recent agentic keyword-search study reports more than 90% of its RAG
  baseline performance without a standing vector database, which makes
  lexical/tool-use a required control rather than a straw man:
  [Keyword search is all you need](https://arxiv.org/abs/2602.23368).
- AWS reports a tool-selection study in which vector filtering reduced a 422
  tool inventory to 20 candidates and improved accuracy and latency, but the
  benchmark evaluates selection rather than final wiki answers:
  [S3 Vectors tool selection](https://aws.amazon.com/blogs/storage/optimize-agent-tool-selection-using-s3-vectors-and-bedrock-knowledge-bases/).

## Reproduction matrix

Use the same page snapshot, page IDs, links, aliases, versions, question set,
model, system prompt, temperature, context budget, and maximum turns. Run
corpus sizes 1, 5, 10, and 25 wikis. At minimum, run the nine arms in
`configs/studies/wiki-agentic-rag-matrix-v1.json`.

The most important controls are:

- raw Markdown filesystem search versus a Karpathy-style compiled wiki;
- MCP over FTS, vectors, and hybrid retrieval with identical `search` and
  `get_page` semantics;
- one federated MCP tool versus one tool per wiki;
- direct retrieval API versus the same retrieval behind MCP, isolating protocol
  overhead;
- full-context at one wiki only, to expose the small-corpus ceiling;
- NIL questions and intentionally ambiguous aliases, so the agent is rewarded
  for abstaining instead of selecting a plausible page.

## What to measure

Retrieval metrics alone are insufficient. A result can retrieve the right page
and still fail to use it, cite it, or abstain when it is absent. Record:

1. page/evidence Recall@k, MRR, nDCG, wrong-wiki rate, and evidence coverage;
2. final answer correctness and citation correctness;
3. NIL abstention precision/recall and stale/conflict handling;
4. valid/invalid tool calls, turns, retries, and tool-result truncation;
5. p50/p95 total latency and retrieval latency, tokens, cost, index build time,
   and update lag;
6. quality, latency, token, and wrong-wiki curves as the number of wikis grows.

The primary result should be paired per-question deltas at a fixed cost and
latency budget. “Saturation” means a pre-registered degradation in answer or
evidence quality, or an unacceptable tail-latency/cost increase—not merely a
larger candidate list.

## Expected hard edges

- A Karpathy wiki is a maintained compilation artifact, so it may win on
  repeated navigational queries while losing on freshness, contradiction, or
  pages not yet compiled. Measure update lag and stale-answer rate.
- Vectors can improve paraphrase recall but can erase exact identifiers and
  acronyms. Keep exact/identifier search in every hybrid arm.
- One MCP tool per wiki increases descriptions and routing choices; one
  federated tool may hide provenance. Measure both tool-description tokens and
  wrong-wiki errors.
- MCP adds a protocol boundary, not magical evidence. A direct API and MCP arm
  with the same backend are required before claiming MCP helps or hurts.
- Coding-agent harnesses have tool-result and context limits. Claude Code’s MCP
  documentation explicitly warns about large tool outputs and configurable
  tool-search behavior; therefore result truncation and tool-search decisions
  must be recorded, not silently treated as retrieval failures:
  [Claude Code MCP docs](https://code.claude.com/docs/en/mcp).

## Frankengate decision rule

Do not select a permanent architecture from public benchmark scores. First run
the matrix with Wikipedia-style questions, then repeat with a consented
enterprise-like wiki containing identifiers, aliases, stale versions, and
cross-team names. Promote only an arm that improves end-to-end answer and
evidence correctness on held-out questions while meeting the same p95 latency,
token, and update-lag budget. The likely production shape is a single MCP
search/context interface with exact identifier search plus hybrid retrieval;
that is a hypothesis, not a result.

## Next implementation step

Build the corpus adapter and deterministic question manifest, then implement
the same `search`, `get_page`, and `expand_links` contract over FTS and vector
backends. Reuse the existing frontier harness and receipt verifier, and keep
raw pages/transcripts outside Git; commit only manifests, hashes, metrics, and
verifiers.

## Harness availability check

The Codex CLI is available and the ToolQA receipts use the authenticated
`gpt-5.6-luna` Codex-subscription path. Claude Code 2.1.220 is installed on the
machine, but a non-interactive smoke test returned `Not logged in`; therefore
this branch does not claim Claude Code benchmark scores. Once an Anthropic
session is authenticated, the same matrix can run through Claude Code's
`--print`/MCP path with the model and permissions recorded in the receipt.
