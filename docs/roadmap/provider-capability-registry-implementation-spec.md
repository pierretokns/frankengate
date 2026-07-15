# Provider Capability Registry Implementation Spec

## Purpose

Bifrost already exposes multimodal provider operations through the core `Provider` interface, but capability knowledge is scattered across provider stubs, `AllowedRequests`, model catalog pricing/parameter rows, provider converters, and late upstream errors. This spec defines a minimal provider capability registry that can answer one hot-path question before provider I/O:

> Can this provider/model serve this request type with these input/output modalities, parameters, and feature requirements?

The first PR should be additive, low-risk, and compatible with current behavior. It should create the registry types, compiler, and read-only admission predicate, then wire it where provider/model decisions already happen. It must not make learning/eval services or remote catalog refresh part of the inference availability path.

## Inspected Seams

- `core/schemas/provider.go:602-719` defines the full provider interface, including text, chat, responses, embeddings, rerank, OCR, speech, transcription, images, video, batch, files, containers, and passthrough.
- `core/schemas/provider.go:314-378` defines `AllowedRequests`; `core/schemas/provider.go:380-509` maps request types to allowed fields; `core/schemas/provider.go:512-526` applies it to custom providers.
- `core/providers/utils/utils.go:1647-1660` standardizes late provider-stub denials as `unsupported_operation`.
- `framework/modelcatalog/main.go:1-10` documents `ModelCatalog` as the composer of datasheet, live list-models, and key config stores.
- `framework/modelcatalog/datasheet/store.go:46-63` owns pricing rows, base-model index, supported response types, supported params, datasheet models, and deprecated models.
- `framework/modelcatalog/datasheet/store.go:193-217` already resolves a capability-oriented pricing entry for `(model, provider)`.
- `framework/modelcatalog/datasheet/store.go:315-322` checks model-parameter request-type support, currently keyed by model only.
- `framework/modelcatalog/datasheet/params.go:161-240` compiles model-parameter JSON into supported response types, supported params, and provider-utils model params.
- `core/schemas/models.go:149-188` already exposes optional `Architecture.InputModalities` and `Architecture.OutputModalities` on models.
- `plugins/governance/main.go:469-648` performs governance load-balancing and fallback construction.
- `plugins/governance/main.go:926-1120` performs provider/model/VK admission, budget/rate checks, and MCP injected-tool checks.
- `core/bifrost.go:4930-4967` and `core/bifrost.go:5081-5095` run pre-request hooks, reread provider/model/fallbacks, and validate request fields before provider attempts.
- `core/bifrost.go:6820-6895` dispatches by `RequestType` to provider methods, where unsupported operations are currently discovered late.

## Non-Goals

- Do not add new provider methods in the first PR.
- Do not remove existing provider stubs or late `unsupported_operation` errors.
- Do not require a live datasheet fetch, Redis, gossip, eval service, or learner to admit requests.
- Do not make the registry the source of budget, entitlement, privacy, or MCP policy. It is a capability predicate used by those layers.
- Do not block unknown capability rows by default in the first PR.

## Ownership

- `core/schemas` owns neutral capability types, the `CapabilityRegistry` interface, `RequiredCapability` extraction from `BifrostRequest`, and error shapes. It must not import `framework`.
- `core` owns the hot-path admission call site. It consumes only the `schemas.CapabilityRegistry` interface from `BifrostConfig`.
- `framework/modelcatalog` owns the concrete registry implementation and compiler from catalog stores.
- `framework/modelcatalog/datasheet` owns parsing source rows and compiling model-level request types, parameters, features, limits, and modalities.
- `plugins/governance` consumes the registry to filter route candidates before random/weighted selection and before fallback construction.
- `transports/bifrost-http/server` wires the existing `ModelCatalog` into `schemas.BifrostConfig.CapabilityRegistry`.
- Provider maintainers own provider-operation seed data when provider methods or stubs change.

## Minimal Go Types

Put neutral types in `core/schemas/capabilities.go`:

```go
package schemas

type CapabilityUnknownBehavior string

const (
	CapabilityUnknownAllow CapabilityUnknownBehavior = "allow"
	CapabilityUnknownDeny  CapabilityUnknownBehavior = "deny"
)

type ModalityMask uint64

const (
	ModalityText ModalityMask = 1 << iota
	ModalityImage
	ModalityAudio
	ModalityVideo
	ModalityFile
	ModalityDocument
)

type FeatureMask uint64

const (
	FeatureTools FeatureMask = 1 << iota
	FeatureToolChoice
	FeatureParallelToolCalls
	FeatureReasoning
	FeatureReasoningWithToolCalls
	FeatureResponseSchema
	FeatureWebSearch
	FeaturePromptCaching
	FeatureRealtime
	FeatureWebSocketResponses
)

type CapabilityRequirements struct {
	RequestType      RequestType
	InputModalities  ModalityMask
	OutputModalities ModalityMask
	Features         FeatureMask
	Parameters       []string
	MaxInputTokens   *int
	MaxOutputTokens  *int
	RawBody          bool
}

type ModelOperationCapability struct {
	RequestType      RequestType
	InputModalities  ModalityMask
	OutputModalities ModalityMask
	Features         FeatureMask
	Parameters       map[string]struct{}
	MaxInputTokens   *int
	MaxOutputTokens  *int
	ContextLength    *int
	Source           string
}

type ModelCapability struct {
	Provider   ModelProvider
	Model      string
	BaseModel  string
	Operations map[RequestType]ModelOperationCapability
	Source     string
	Revision   string
}

type CapabilityDecision struct {
	Allowed bool
	Reason  string
	Code    string
	Known   bool
}

type CapabilityRegistry interface {
	CheckCapability(ctx *BifrostContext, provider ModelProvider, model string, req CapabilityRequirements) CapabilityDecision
}
```

Implementation notes:

- Use bitmasks instead of slices on the hot path.
- `Parameters` can be a slice on requirements because request extraction is per-request; compiled capabilities should use a map.
- `Source` and `Revision` are small strings for audit/debug. They must not contain request payload content.
- `RawBody` marks requests sent via raw passthrough where typed modality extraction is incomplete.

Add a concrete compiler in `framework/modelcatalog/capabilities.go`:

```go
type CapabilityIndex struct {
	unknownBehavior schemas.CapabilityUnknownBehavior
	byProviderModel map[providerModelKey]schemas.ModelCapability
	providerOps     map[schemas.ModelProvider]requestTypeMask
}

func (mc *ModelCatalog) CheckCapability(ctx *schemas.BifrostContext, provider schemas.ModelProvider, model string, req schemas.CapabilityRequirements) schemas.CapabilityDecision
func (mc *ModelCatalog) RebuildCapabilityIndex()
func (mc *ModelCatalog) CapabilityForModel(provider schemas.ModelProvider, model string) (schemas.ModelCapability, bool)
```

`ModelCatalog` should store the compiled index behind an `atomic.Pointer[CapabilityIndex]` or immutable pointer swapped under the existing catalog reload path. Reads must not perform I/O.

## Source Of Truth And Generation

The registry is a compiled view, not a new primary authority.

Authoritative inputs:

1. Provider operation seed: a reviewed static source file, for example `framework/modelcatalog/capabilitydata/provider_operations.yaml`, generated into Go with `go generate`. It records which built-in providers implement which top-level `RequestType`s. This is the source that turns provider stubs into early denials. Provider PRs that add/remove operations must update this seed.
2. Custom provider restrictions: existing `CustomProviderConfig.AllowedRequests` remains authoritative for custom-provider operation gating. Nil keeps the current "all operations allowed" semantics.
3. Model pricing rows: existing `governance_model_pricing` rows carry `(model, provider, mode)`, context length, max input/output tokens, `architecture`, and deprecation state. See `framework/configstore/tables/modelpricing.go:10-129`.
4. Model parameter rows: existing `governance_model_parameters` stores raw model-parameter JSON keyed by model. See `framework/configstore/tables/modelparameters.go:3-13`.
5. Live list-models and key config: these gate model availability and key eligibility, but they are not the capability authority.

Generation rules:

- `provider_operations.yaml` is human-reviewed and generated into a deterministic Go table. CI must fail if generated output is stale.
- The model capability compiler runs during `ModelCatalog` initialization and after pricing/model-parameter reloads.
- Pricing row `mode` maps through the existing normalization in `framework/modelcatalog/datasheet/types.go:359-389`.
- `architecture.input_modalities` and `architecture.output_modalities` are preferred when present.
- If architecture modalities are absent, infer conservative defaults from request type or pricing mode:
  - chat, responses, text completion, count tokens, compaction: text input, text output.
  - embedding: text input, embedding output is represented as no user-visible output modality in the first PR.
  - rerank: text input, text output.
  - OCR: document or image input, text output.
  - speech: text input, audio output.
  - transcription: audio input, text output.
  - image generation: text input, image output.
  - image edit and variation: image input, image output; image edit also accepts text input.
  - video generation: text input, video output.
  - video remix/retrieve/download/list/delete: lifecycle operations are provider-level only unless a model is present.
- Model-parameter booleans compile into `FeatureMask`: tools, tool choice, parallel tool calls, reasoning, reasoning with tool calls, response schema, prompt caching, and web search.
- Unknown rows remain unknown. The first PR must not synthesize false certainty for a model/provider pair that the catalog does not know.

No first-PR migration is required if the existing pricing and model-parameter tables are sufficient. A later override table can be added if enterprise operations need local capability overrides independent of pricing/parameter sync.

## Required Capability Extraction

Add a pure helper in `core/schemas`, for example:

```go
func RequiredCapabilityFromRequest(req *BifrostRequest) CapabilityRequirements
```

Rules:

- Normalize streaming request types to their base semantic operation for capability comparison, but preserve the original request type for error metadata.
- Treat chat and responses string content as text.
- Treat chat content blocks as:
  - `text` -> `ModalityText`
  - `image_url` -> `ModalityImage`
  - `input_audio` -> `ModalityAudio`
  - `file` -> `ModalityFile`, and also `ModalityDocument` when MIME type or filename indicates PDF/document.
- Treat responses content blocks as:
  - `input_text` -> `ModalityText`
  - `input_image` -> `ModalityImage`
  - `input_audio` -> `ModalityAudio`
  - `input_file` and `input_container` -> `ModalityFile`, with document inference where possible.
- Chat `Params.Modalities` controls output modalities. Empty means text output. `["audio"]` or `["text","audio"]` requires audio output.
- Chat/Responses tools require `FeatureTools`; explicit tool-choice requires `FeatureToolChoice`; parallel tool calls require `FeatureParallelToolCalls`.
- Reasoning fields require `FeatureReasoning`; reasoning plus tools requires `FeatureReasoningWithToolCalls`.
- JSON schema / structured output requires `FeatureResponseSchema`.
- Web search options or web search tools require `FeatureWebSearch`.
- Prompt cache fields require `FeaturePromptCaching`.
- Image-generation `Params.InputImages` adds image input.
- Image edit/variation require image input.
- Video generation `Input.InputReference` adds image input; `Params.VideoURI` adds video input; normal generation requires text input and video output.
- Speech requires text input and audio output.
- Transcription requires audio input and text output.
- OCR requires image or document input and text output based on `OCRDocument.Type`.
- Raw request body mode sets `RawBody=true`. Default policy should allow unknown raw-body capability for backward compatibility; enterprise strict mode may deny or require an explicit override.

The extractor must not copy media bytes or raw payloads.

## Admission Algorithm

### Core Admission

Add `CapabilityRegistry schemas.CapabilityRegistry` and an optional `CapabilityUnknownBehavior` to `schemas.BifrostConfig`. In `core.Bifrost`, store the interface pointer.

Call admission in both non-stream and stream flows after `PreRequestHook` mutation and `validateRequestAfterPreRequestHooks`, before `tryRequest` or `tryStreamRequest`:

1. If registry is nil, allow.
2. Build requirements with `schemas.RequiredCapabilityFromRequest(req)`.
3. Read provider and model from `req.GetRequestFields()`.
4. If request type does not require a model, only enforce provider-level operation support when known.
5. Ask `registry.CheckCapability(ctx, provider, model, requirements)`.
6. If allowed, continue.
7. If denied, return a `BifrostError` before key selection/provider queue.

Fallback behavior:

- Before each fallback attempt, set provider/model on a temporary request view or call the registry with the fallback tuple.
- Skip fallback candidates denied for capability mismatch and append a routing-engine log entry.
- If every candidate is denied, return the most specific capability denial with `AllowFallbacks=false`.
- Capability denial for the primary should not count as a provider health failure.

Error mapping:

- Provider/request-type unsupported: preserve `unsupported_operation` where possible.
- Model/provider capability mismatch: use `unsupported_model_capability`.
- Parameter/feature mismatch: use `unsupported_model_parameter`.
- Status code: 400 for caller-chosen incompatible model/provider; 502 only for provider/upstream failures.
- Always populate `Provider`, `RequestType`, `OriginalModelRequested`, and `ResolvedModelUsed`.

### Governance Routing

Use the same predicate inside `GovernancePlugin.loadBalanceProvider`:

1. Extract request requirements before scanning provider configs.
2. Existing filters still run first: VK provider allowlist, model allowlist/blacklist, budgets, and rate limits.
3. Before a provider config enters `allowedProviderConfigs`, refine the model for that provider and check capability.
4. Exclude incapable candidates with a routing log reason.
5. Build fallback list only from capable candidates.
6. If no capable candidates remain, return a typed error in strict mode. In backward-compatible mode, preserve current soft-skip behavior until the enterprise launch profile enables strict admission.

This keeps capability filtering aligned with entitlement and routing instead of discovering mismatches after random weighted selection.

## Backward Compatibility

- Registry nil means current behavior.
- Unknown capability data allows by default in the first PR.
- Existing provider stubs remain and continue returning `unsupported_operation`.
- Existing `AllowedRequests` semantics remain unchanged: nil means all operations allowed; non-nil only allows true fields.
- No existing API response fields are removed.
- If capability metadata is added to list-models responses, it must be optional and omitted when unknown.
- Custom providers without registry data keep current behavior unless they already restrict operations through `AllowedRequests`.
- Raw body passthrough keeps current behavior by default.
- Strict denial should be controlled by an internal/enterprise config switch after registry coverage is validated.

## Tests

Unit tests:

- `core/schemas/capabilities_test.go`
  - chat string content -> text input/text output.
  - chat image/audio/file blocks -> image/audio/file/document input.
  - chat modalities `["text","audio"]` -> text and audio output.
  - responses input_image/input_audio/input_file -> modality masks.
  - image generation with input images -> text+image input, image output.
  - image edit/variation -> image input, image output.
  - speech/transcription/OCR/video extraction.
  - raw-body requests set `RawBody` without copying bytes.

- `framework/modelcatalog/capabilities_test.go`
  - compile provider operation seed.
  - compile pricing mode rows into operation masks.
  - prefer architecture modalities when present.
  - infer modality defaults when architecture is absent.
  - merge model-parameter features into feature masks.
  - exact model beats base-model family; provider-prefixed model aliases resolve.
  - unknown behavior allow vs deny.

- `plugins/governance/routing_capabilities_test.go`
  - weighted routing excludes provider/model candidates lacking required image/audio/video capability.
  - fallbacks contain only capable candidates.
  - unknown capability allows in default mode.
  - strict mode returns typed no-capable-provider error.

- `core/capability_admission_test.go`
  - selected incapable provider is denied before key selection/provider call.
  - capable fallback is attempted when primary lacks capability.
  - all incapable fallbacks return the capability error, not a provider network error.
  - registry nil preserves current behavior.
  - passthrough raw body preserves current behavior in default mode.

Regression tests:

- Keep existing provider unsupported-operation tests, such as `core/providers/opencode/opencode_test.go:53-120`, passing.
- Add at least one test proving `AllowedRequests` still wins for custom providers even if registry says capable.
- Add a benchmark or allocation test only after the first functional PR if the hot-path lookup shows measurable allocation risk.

## First PR File List

Expected files to add:

- `core/schemas/capabilities.go`
- `core/schemas/capabilities_test.go`
- `framework/modelcatalog/capabilities.go`
- `framework/modelcatalog/capabilities_test.go`
- `framework/modelcatalog/capabilitydata/provider_operations.yaml`
- `framework/modelcatalog/capabilitydata/provider_operations_generated.go`
- `framework/modelcatalog/capabilitydata/generate.go`
- `plugins/governance/routing_capabilities_test.go`
- `core/capability_admission_test.go`

Expected files to edit:

- `core/schemas/bifrost.go`
  - add `CapabilityRegistry` to `BifrostConfig`.
  - optionally add small request helpers if they fit better beside `GetRequestFields`.
- `core/bifrost.go`
  - store registry on `Bifrost`.
  - call admission after pre-request hooks and before provider attempts.
  - recheck fallbacks before each fallback attempt.
- `core/utils.go`
  - add capability error construction helper or keep it in `core/bifrost.go` if smaller.
- `framework/modelcatalog/main.go`
  - initialize and rebuild the compiled capability index during catalog load/reload.
- `framework/modelcatalog/datasheet/params.go`
  - expose compiled supported endpoints/feature data needed by the capability compiler.
- `framework/modelcatalog/datasheet/types.go`
  - add parsing fields only if the upstream model-parameters JSON already carries explicit modalities not currently parsed.
- `framework/modelcatalog/pricing.go`
  - expose `CapabilityForModel` or keep the registry methods in `capabilities.go`.
- `plugins/governance/main.go`
  - capability-filter routing candidates and fallbacks.
- `transports/bifrost-http/server/server.go`
  - pass the existing `ModelCatalog` as `CapabilityRegistry` in `BifrostConfig`.
- `go.work` and module files only if a generator introduces a new tool dependency. Prefer standard library generation to avoid this.

Files not needed in the first PR:

- No config schema change unless strict-mode runtime configuration is included.
- No database migration unless a provider/model override table is intentionally added.
- No UI change unless capability metadata is surfaced to users.
- No provider implementation change except correcting provider-operation seed rows when tests reveal existing stubs and the seed disagree.

## Rollout Plan

1. Add registry types, compiler, generated provider operation seed, and unit tests.
2. Wire `ModelCatalog` into core as an optional `CapabilityRegistry`, but keep unknown allow.
3. Add core admission checks and prove no provider call happens on known-deny cases.
4. Add governance candidate filtering and fallback pruning.
5. Run provider-focused tests for routing and unsupported operations.
6. After coverage is acceptable, enable strict unknown-deny only in the internal enterprise launch profile.

## Open Questions

- Should capability strictness live in `BifrostConfig`, transport config, or enterprise governance profile?
- Do we need first-class `ModalityEmbedding`, or should embeddings stay represented by request type only?
- How should file MIME detection behave when only a provider file ID is supplied?
- Should video requests with `Params.Audio=true` require an audio-output feature or only a video-output capability with an audio-track feature?
- Do custom providers need a first-PR `capability_overrides` config field, or is `AllowedRequests` enough until the override table exists?
