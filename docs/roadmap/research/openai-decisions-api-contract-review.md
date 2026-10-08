# OpenAI Decisions contract review — 2026-10-08

The authoritative project is `pierretokns/frankengate`, whose default branch is `dev`. Implementation starts from freshly fetched fork `dev` at `e12317bcc00897fcffaa85445bd8d7316eea5c21`. Existing developer changes were preserved in their original checkout.

## Upstream finding

Bifrost upstream `dev` at `dfa57061c46793d1229885dcf7c54ef1e74b754b` has a `DecisionRequest` with a TypeSafe state/criteria contract and adapters/emulation. Its OpenAI provider and OpenAI HTTP integration do not implement the native OpenAI `/decisions` endpoint. A TypeSafe decision request, a Luna model alias, or a Responses approximation is not evidence of OpenAI Decisions API compatibility. No upstream adapter was copied; upstream licenses and notices are unchanged.

The September 29 Tibo post about fast constrained decisions was only discovery context. Endpoint, schema, model, and availability claims were checked against official sources instead.

## Official evidence

- [Decisions guide](https://developers.openai.com/api/docs/guides/decisions): public beta; `POST /v1/decisions`; `gpt-6-luna`; text/inline images; predicate, typed choice, score, and per-question refusal semantics.
- [openai-node v7.30.0](https://github.com/openai/openai-node/blob/a4942ba48e999f9f637f81c5c925ed91b326343f/src/resources/decisions.ts), commit `a4942ba48e999f9f637f81c5c925ed91b326343f`: exact request/response unions, user-only input, 128-image limit, required usage detail counters, nullable response names, optional safety identifier, and unary bearer-auth SDK call.
- [Pricing](https://developers.openai.com/api/docs/pricing): dedicated Decisions input rates, long-context tier, no separate output/cache charges, and regional premium.
- [Regional processing](https://developers.openai.com/api/docs/guides/your-data#sub-processors-and-regional-request-processing): explicit US/EU OpenAI hosts. Account eligibility is not inferred from the guide.

The implementation is a validated native wire adapter over existing passthrough. It preserves unknown extension fields and does not claim normalized provider-independent core support. Native capability admission is explicit for the verified provider/model/contract; actual passthrough permission, identity, key, provider/model grants, budgets, rate limits, and durable admission remain active. Content storage is restricted for this endpoint.

## Local evidence and limitations

`core/providers/openai/testdata/decisions` contains synthetic contract fixtures, not live OpenAI outputs or calibration data. Regression tests cover typed values, inline-image envelope validation, refusals, malformed/duplicate JSON, response distributions and names, usage, exact raw wire preservation, headers/auth, 401/429 errors, cancellation, network timeout, malformed-response settlement, route middleware, virtual-key/model/provider/budget/rate denials, populated-catalog admission, logging suppression, pricing tiers, regional uplift, and scoped overrides.

Run the dedicated offline CI lane locally from an initialized Go workspace:

```sh
env -u OPENAI_API_KEY go test -race ./core/providers/openai ./transports/bifrost-http/integrations ./transports/bifrost-http/handlers ./plugins/logging ./plugins/governance ./framework/modelcatalog/datasheet -run '^TestDecisions' -count=1
env -u OPENAI_API_KEY go test ./core/schemas ./core/providers/openai ./transports/bifrost-http/integrations ./plugins/logging ./framework/modelcatalog/datasheet
env -u OPENAI_API_KEY go test ./plugins/governance ./transports/bifrost-http/handlers -run 'Test(ConfiguredReservationEstimator|DurableCoordinator|DurableReservation|PostLLMHook|CorsMiddleware|TracingMiddleware)' -count=1
go vet ./core/schemas ./core/providers/openai ./transports/bifrost-http/integrations ./transports/bifrost-http/handlers ./plugins/logging ./plugins/governance ./framework/modelcatalog/datasheet
python3 docs/openapi/bundle.py --output /tmp/frankengate-decisions-openapi.json
```

No new credentials, paid API calls, live API tests, deployment, or data-factory changes were performed. Live entitlement, image acceptance, model quality/calibration/latency, and invoice accuracy remain unverified until the existing credential and budget gate permits a test. The SDK source supplies the contract; an actual SDK call to the live beta has not been made.

## Independent review and live validation gate

A fresh independent reviewer examined PR #150 at `00f00b1e3a5442d72e004bc051e7c5dfa59d486f`. Reproductions found outer HTTP query/error logging and root-span query leaks, durable settlement retaining the reservation ceiling, and full refunds of malformed successes carrying billed usage. Focused fixes strip Decisions queries from access logs/root spans, suppress console error-body dumps even before the router runs, settle observed usage and resolved native prices, and retain billed errors. Follow-up review identified native upstream non-success responses counted as successes; these now refund unbilled reservations and skip success counts. Regression fixtures cover these cases, zero usage, fractional microdollars, regional pricing, and scoped overrides. Other passthrough routes retain their existing error classification.

The current task process has no `OPENAI_API_KEY`. The repository-level `config.json` files in the isolated clone, `/Users/pierre/dev/bifrost`, and `/Users/pierre/dev/frankengate-lab-debug` are empty, and neither `.env` nor `.env.local` exists there. The default macOS runtime config paths under `~/.config/bifrost` and `~/.config/frankengate` have no `config.json`. Custom application directories, database-stored keys, external secret loaders, and account beta entitlement were not verified. No credential value was exposed or created.

A live smoke test requires an existing approved OpenAI credential loaded through the deployment's approved secret path, confirmed project access to the Decisions beta, explicit authorization with a maximum spend and request count, and an authorized gateway virtual key with OpenAI/Luna grants, passthrough permission, budgets, and rate limits. Start with one small text request within that approved cap; real image acceptance, cancellation behavior against OpenAI, quality/latency, and invoice reconciliation require separate approved checks. No paid call is authorized by these offline results.
