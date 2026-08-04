# Same-model wiki backend factorial — 2026-08-02

## Protocol

The same `gpt-5.5` Codex structured-action agent, 20 synthetic wiki tasks,
1/5/10/25 corpus sizes, and five-action budget were run against raw FTS,
raw TF-IDF, and raw hybrid retrieval. The previously committed hybrid run is
included as the control. Native MCP was not used; the action contract is the
same one used in the earlier frontier experiment.

## Aggregate results

| backend | target answer accuracy | gold page loaded | NIL abstention | errors | finished |
|---|---:|---:|---:|---:|---:|
| FTS | 16/16 | 20/20 | 1/4 | 1 | 19/20 |
| TF-IDF | 16/16 | 19/20 | 4/4 | 0 | 20/20 |
| hybrid | 16/16 | 20/20 | 4/4 | 0 | 20/20 |

## Interpretation

On this fixture, backend choice did not change answer accuracy once the agent
could find and read the target page. It did change the reliability envelope:
raw FTS produced three NIL false accepts and one step/error failure, while
TF-IDF and hybrid abstained on all NILs. Hybrid also loaded the gold page on
every target case; TF-IDF missed one gold search at the largest scale but still
produced the checked answer from its trajectory.

This is a concrete embedding-vs-model boundary: the frontier model can often
repair modest candidate-ranking differences, but it cannot make a bad NIL gate
safe, and retrieval coverage remains measurable separately from answer quality.
The result supports a structured/lexical+dense cascade with abstention rather
than a model-only search policy.

## Limits

- Five generated questions per scale and a synthetic 100-page fixture are not
  an enterprise benchmark.
- The run is not native MCP and has no real tool/network latency.
- The same frontier model and prompt were used for all arms; no claim about
  model ranking or production cost is established.

Receipt: [content-minimized factorial result](../results/wiki-frontier-gpt55-backend-factorial-2026-08-02.json)
