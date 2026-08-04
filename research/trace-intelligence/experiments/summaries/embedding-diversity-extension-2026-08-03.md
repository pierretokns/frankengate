# Beyond the paper's six encoders

The paper's six models must remain frozen for the reproduction. A newer model
can be an extension arm, but replacing a paper encoder would turn the result
into a new ensemble and erase the comparison.

“More models” is not the same as “more diversity.” We should measure diversity
by architecture, training objective, language/context coverage, and error
correlation on our hard-negative labels. Candidate extension arms:

| Candidate | What diversity it adds | Why it is relevant | Main caveat |
| --- | --- | --- | --- |
| `Qwen/Qwen3-Embedding-0.6B` (then 4B if justified) | Newer foundation-model family; instruction-aware; 32K context; MRL | Strong modern retrieval baseline and already led our bounded TechQA vintage probe | Same family at multiple sizes is not independent diversity |
| `BAAI/bge-m3` | Dense + sparse + multi-vector retrieval, 100+ languages, 8192 tokens | Tests whether lexical and late-interaction signals beat six dense vectors for identifiers and long traces | One model with multiple modes; score calibration differs by mode |
| `nomic-ai/nomic-embed-text-v2-moe` | Sparse mixture-of-experts routing and open training/eval data | Tests whether expert specialization helps corporate aliases without a six-model ensemble | Requires task prefixes and custom `megablocks`; 512-token limit |
| `Snowflake/snowflake-arctic-embed-l` | Independent modern retrieval training family | Strong single-encoder control from the existing model-vintage probe | Primarily dense English retrieval; less architectural diversity |
| `jinaai/jina-embeddings-v4` | Qwen2.5-VL base, multimodal/late-interaction, task adapters, 32K context | Tests tables, diagrams, code, and multimodal enterprise artifacts | 4B, custom code, Qwen Research License; not a fair drop-in for the paper arm |

The first extension matrix should therefore compare:

1. paper six-encoder ensemble (faithful arm, with the Jina-v3 packaging issue
   resolved);
2. each paper encoder alone;
3. Qwen3-0.6B, Arctic-L, BGE-M3 dense, BGE-M3 dense+sparse/late-interaction,
   and Nomic-v2-MoE as single-model controls;
4. a low-correlation subset chosen from measured per-query errors; and
5. the paper selector versus a modern single-model nearest-neighbor selector.

Selection should be based on enterprise slices—acronym collisions, same
system/different operation, schema/version conflicts, and near-duplicate
tool calls—not on MTEB rank alone. A model that wins generic retrieval but
collapses on exact identifiers is not diverse in the way Frankengate needs.
