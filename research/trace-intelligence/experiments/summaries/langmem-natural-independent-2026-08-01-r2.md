# Faithful Graphiti and LangMem natural-component bakeoff

## Outcome

The preregistered cohort contained 3 natural Wisp/Fable
context-artifact cases, but **0/3 full Graphiti+LangMem cases completed**
within the 600-second run ceiling. Graphiti completed
0 natural cases and LangMem had
3 durably evidenced natural cases; observed
typed component failures: graphiti:EmptyResponseError. No proxy result was substituted.

Both real pinned libraries passed smaller synthetic compatibility checks before
the natural run: Graphiti returned a structured extraction through its actual
`OpenAIGenericClient`, and LangMem returned one structured memory through its
actual `create_memory_manager`. Those checks establish API compatibility only.
On the first full natural input, Graphiti's real node-extraction path logged four
`EmptyResponseError` events and was stopped during the next in-flight request at
the ceiling. The other two Graphiti cases were not executed. The independent LangMem arm completed 3/3 selected cases through the real `MemoryManager.invoke` surface. It produced 0 durable memory candidates, mean exact-identifier recall 0.0, and 0 existing-memory updates. These are component mechanics, not a usefulness or quality claim.

The deterministic exact-artifact baseline would match
1 of the three later states. Graphiti and combined
retrieval deltas are `null`, not negative scores, because no natural component
case completed.

No Graphiti node, edge, temporal, invalidation, or combined-retrieval metric is
reported. In the independent LangMem arm, the explicit zero observations above
mean that the real manager returned no durable candidates and preserved no
measured identifiers; they are not missing-data placeholders.

## Upstream pins and execution surface

| Component | Exact source | License | Real surface executed |
|---|---|---|---|
| Graphiti 0.29.3 | `v0.29.3` / `021d3a57d511f21b10adaf7fa923bd5c1fce5e9d` | Apache-2.0 | `build_indices_and_constraints`, `add_episode`, `search_` |
| LangMem 0.0.30 source snapshot | unreleased main / `56d85939d80bb731bd5e237567148d817d7bfd16` | MIT | `create_memory_manager`, `MemoryManager.invoke` |

LangMem has no GitHub release or tag at this pin, so this result deliberately
calls it an exact source snapshot rather than a stable release.

## Compatibility and operational hard edges

1. Installing unconstrained current transitive dependencies made the pinned
   LangMem source fail inside TrustCall because `ExtractionState.tool_call_id`
   was absent. Aligning to LangMem's exact `uv.lock` was required.
2. Pairing locked `langchain-core==1.4.8` with newer
   `langchain-openai==1.4.1` failed because
   `langchain_core.utils._gateway` did not exist. The upstream-locked
   `langchain-openai==1.1.14` was required.
3. Ollama's Qwen3 emitted reasoning with empty final content to Graphiti and
   ignored the tool-selection behavior LangMem needs. Both real libraries ran
   only after their public OpenAI-compatible client surfaces injected
   `extra_body.think=false`.
   That adapter fixed the small smoke but did not fix full natural-document
   Graphiti node extraction within the bound.
4. Graphiti adds an LLM, embedding model, graph engine, graph schema/index
   lifecycle, and reranking/search configuration. The experiment used embedded
   FalkorDB and local Nomic embeddings; this does not establish Aurora
   compatibility or production operations.
5. LangMem performs LLM tool calls but supplies no persistence or authorization
   plane in `create_memory_manager`; Frankengate would own governed storage,
   provenance, update review, and deletion semantics.
6. Exact-artifact current-state lookup and semantic graph/memory extraction are
   different objectives. A component can add entities, relations, or compressed
   candidates while still losing exact source-state retrieval. Combining them
   cannot reconstruct a later state absent from all pre-query evidence.

## Commands and configuration

| Purpose | Command/surface |
|---|---|
| Unit contracts | `python3 -m unittest research/trace-intelligence/tests/test_faithful_memory_components.py` |
| Graphiti source pin | `git rev-parse v0.29.3^{commit}` and source `LICENSE`/`uv.lock` receipts |
| LangMem source pin | exact main `HEAD` plus source `LICENSE`/`uv.lock` receipts |
| Natural cohort | existing Wisp/Fable canonical loaders and strict pre-query eligibility |
| Local inference | Ollama OpenAI-compatible endpoint, Qwen3 4B, reasoning disabled |
| Graph retrieval | `COMBINED_HYBRID_SEARCH_RRF`, limit 5 |

Important configuration: Python 3.12.4, `graphiti-core==0.29.3`,
`langmem==0.0.30`, `falkordblite==0.10.0`, `trustcall==0.0.39`,
Qwen3 4B for extraction, Nomic Embed Text at 768 dimensions, temperature zero,
one Graphiti coroutine, Graphiti telemetry disabled, and LangSmith tracing
disabled. No source content or model output was durably emitted.

## Interpretation

This bounded result establishes pinned dependency/API compatibility for small
synthetic inputs and a falsifiable full-input failure boundary. It does **not**
establish natural extraction, retrieval, identifier preservation, temporal
mechanics, memory updating, user benefit, causal value, enterprise transfer,
authorization correctness, production scaling, or a need to replace
PostgreSQL/Aurora. The changed cases would also be impossible to solve exactly
from a future state not present before the cutoff.

## Primary upstream sources

- [Graphiti v0.29.3 release](https://github.com/getzep/graphiti/releases/tag/v0.29.3)
- [Graphiti `add_episode` at the pin](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/graphiti.py)
- [Graphiti OpenAI-generic client at the pin](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/llm_client/openai_generic_client.py)
- [LangMem exact source snapshot](https://github.com/langchain-ai/langmem/tree/56d85939d80bb731bd5e237567148d817d7bfd16)
- [LangMem memory manager at the pin](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/src/langmem/knowledge/extraction.py)
- [LangMem release-gap issue #130](https://github.com/langchain-ai/langmem/issues/130)
- [LangMem open schema/search issues](https://github.com/langchain-ai/langmem/issues)
