# What enterprise model-customization platforms actually do

Date: 2026-08-02  
Status: primary-source practice map; not a claim about undisclosed private lab systems

Public enterprise platforms converge on a narrower pattern than “train a model
on all corporate logs.” They start with retrieval, metadata, examples, and
evaluation; fine-tuning is a later, task-specific intervention.

| Platform | Publicly documented practice | Frankengate implication |
| --- | --- | --- |
| Databricks AI Search / Genie | Put custom metadata, business terms, synonyms, prompt matches, join relationships, and focused datasets beside governed tables; its retrieval guide says to diagnose the embedding problem first and treat embedding fine-tuning as a last resort | Mine aliases and schema relations into explicit metadata/identifier features before training a vector model |
| Google Gemini Enterprise Agent Platform | Tune text embeddings with query/corpus examples and train labels; reports up to 41% maximum and 12% average gains on public retrieval experiments | A custom embedding requires labeled query–positive/negative pairs and a held-out corporate test, not raw logs alone |
| AWS SageMaker | Fine-tune from customer datasets in S3, register/deploy model artifacts, and integrate the result into MLOps; RAG guidance keeps enterprise data in a knowledge library and updates embeddings asynchronously | Separate corpus/index updates from model training; version both and gate deployment |
| Cohere | Provides Embed Jobs for large corpora and fine-tuning for generation, classification, rerank, and chat in its documented platform, while later deprecating several older fine-tuning capabilities | Treat hosted model APIs as replaceable adapters; maintain model/version receipts and rerun retrieval evals after migrations |
| Databricks LLMOps | Describes a progression from third-party models and prompt/pipeline artifacts to fine-tuned models, with human feedback feeding monitoring, testing, and future tuning | Promote validated prompts, retrieval policies, and tool capsules before promoting weights |

The common operational loop is:

```text
metadata / retrieval baseline
  -> labeled failures and hard negatives
  -> task-specific reranker or embedding tune
  -> held-out evaluation and human review
  -> versioned deployment with rollback
```

What these public practices do **not** show is automatic ontology induction from
unstructured employee traces. The closest supported intervention is to turn
traces into supervised examples: successful query/artifact pairs, rejected or
conflicting candidates, temporal/authority labels, and explicit aliases. Raw
logs are a source for mining those examples, not a sufficient training target.

This reinforces our empirical plan: use deterministic identifiers and metadata
to generate candidate pairs, use hard negatives from same-system collisions and
NIL cases, tune only after a strong baseline, and evaluate on user/project/time
held-out data with changed-system replay. A custom embedding should be treated
as an optional compressed retrieval component, not the source of truth.

Primary sources: [Databricks retrieval quality guide](https://docs.databricks.com/gcp/en/ai-search/retrieval-quality), [Databricks Genie knowledge store](https://docs.databricks.com/aws/en/genie-agents/tune-quality), [Google embedding tuning](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tuning/embeddings), [AWS SageMaker fine-tuning](https://docs.aws.amazon.com/sagemaker/latest/dg/jumpstart-fine-tune.html), [Cohere platform](https://docs.cohere.com/v1/docs/the-cohere-platform), [Databricks LLMOps](https://docs.databricks.com/aws/en/machine-learning/mlops/llmops).

## Primary-document refresh

The current vendor documentation makes the supervision requirement more
explicit than the older practice map:

- Databricks recommends comparing full-text, hybrid, ANN, and reranked
  retrieval first. It interprets “full-text significantly better than ANN” as
  an embedding/domain-fit problem and says fine-tuning should follow the
  preceding retrieval-quality steps, not replace them. See the [retrieval
  evaluation guide](https://docs.databricks.com/gcp/en/ai-search/retrieval-quality-eval).
- Google’s embedding tuning contract requires separate corpus, query, and
  relevance-label files. It permits graded relevance scores and recommends
  explicit validation and test labels; its documented dataset bounds are
  9–10,000 queries and up to 500,000 corpus documents. See [Tune text
  embeddings](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tuning/embeddings?hl=en).
- Cohere’s reranker training format explicitly contains `query`,
  `relevant_passages`, and `hard_negatives`; its documentation says that about
  five hard negatives per query can provide meaningful improvement and
  requires a relevant passage for every query. See [Starting the Rerank
  Fine-Tuning](https://docs.cohere.com/v1/docs/rerank-starting-the-training).
- AWS keeps the knowledge library and its asynchronously refreshed embeddings
  separate from model fine-tuning and deployment. This supports versioned
  index/model artifacts with rollback rather than treating every new log as a
  weight update. See [RAG with enterprise data](https://docs.aws.amazon.com/solutions/text-generation-using-embeddings-from-enterprise-data-on-aws/index.html)
  and [fine-tuning domain adaptation](https://docs.aws.amazon.com/sagemaker/latest/dg/jumpstart-foundation-models-fine-tuning-domain-adaptation.html).

These documents strengthen, but do not overturn, our conclusion: companies
customize a retrieval or reranking component after constructing supervised
query–corpus evidence. They do not present one-shot ontology induction from
raw corporate traces as a solved production primitive.
