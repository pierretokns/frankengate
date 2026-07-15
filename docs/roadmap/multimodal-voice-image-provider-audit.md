# Multimodal, Voice, Image, and Provider-Parity Audit

Date: 2026-07-15
Scope: repository evidence only; no live-provider credentials were used.

## Executive decision

Bifrost is a good base for a launch gateway whose supported multimodal surface is deliberately constrained and advertised from a capability registry. The common schemas, provider interface, request pipeline, streaming hook path, governance operation flags, and test harness already cover vision input, files, speech synthesis, transcription, image generation/edit/variation, realtime audio, OCR, and video. Replacing this foundation would discard substantial working code.

It is **not launch-good-enough as a claim of uniform multimodal support across providers**. Every provider implements the same interface, but many methods are explicit `NewUnsupportedOperationError` stubs. Support is also model- and upstream-dependent inside providers. The most important missing product primitive is therefore not another converter: it is an authoritative, model-aware capability registry used by routing, governance, UI, documentation, and conformance tests.

Recommended launch contract:

1. Support vision input through chat/Responses for provider/model combinations proven by the live harness.
2. Support speech/transcription initially through OpenAI, ElevenLabs, Gemini, Hugging Face, Groq, and Mistral only where their provider tests pass.
3. Support image operations initially through OpenAI/Azure, Gemini/Vertex, Bedrock, Hugging Face, Replicate, and Runware, with operation-level capability checks.
4. Treat OpenAI Realtime as a separate, explicitly allowlisted preview surface. Do not imply that `SpeechStream` is equivalent to bidirectional realtime voice.
5. Reject unsupported provider/model/operation combinations before queueing or charging, with a machine-readable capability error.

## End-to-end architecture

```text
OpenAI-compatible HTTP or native SDK integration
  -> HTTP validation / multipart or streamed-large-body handling
  -> Bifrost speech, transcription, image, chat, Responses, realtime schemas
  -> governance AllowedRequests and plugin pre-hooks
  -> core request queue and Provider interface dispatch
  -> provider-specific pure converter and HTTP/SSE/EventStream implementation
  -> provider response converted to Bifrost response or BifrostStreamChunk
  -> post-hooks, logging, tracing, cost accounting, serialization
```

Evidence:

- Core dispatch calls unary modality methods at `core/bifrost.go:6955-6983` and stream methods at `core/bifrost.go:7225-7231`.
- The contract is explicit at `core/schemas/provider.go:633-652`.
- Operation allowlisting covers speech, transcription, image generation/edit/variation and realtime at `core/schemas/provider.go:419-435,495`.
- HTTP supports synchronous modality endpoints in `transports/bifrost-http/handlers/inference.go` (speech around 1380, transcription around 1490, image generation around 2257, edit around 2313, variation around 2513).
- Durable async equivalents are registered at `transports/bifrost-http/handlers/asyncinference.go:32-36,77-94`.
- The schemas are first-class rather than raw passthroughs: `core/schemas/speech.go:8`, `core/schemas/images.go:15,291,334`, and the transcription types used by the provider interface.
- Chat vision/audio/file blocks are represented at `core/schemas/chatcompletions.go:1122-1133,1156-1158,1365-1376`; Responses image/file blocks are at `core/schemas/responses.go:1340-1346,1744`.
- Large request protection is configurable and defaults to 100 MB (`transports/bifrost-http/lib/config.go:589,1069-1070`); decompression and streamed bodies are handled at `handlers/middlewares.go:230-320`. Audio upload validation independently caps files at 25 MB (`handlers/inference.go:663,2140-2148`).

## Provider/feature matrix

Legend: **Yes** = real provider path; **Stream** = dedicated incremental path exists; **No** = explicit unsupported stub; **Input** = accepted as chat/Responses input rather than generated output; **Conditional** = model/inference-provider specific and must not be advertised provider-wide.

| Provider | Vision / multimodal input | Speech / TTS | Transcription | Image generate | Image edit | Variation | Realtime voice | Assessment and evidence |
|---|---|---|---|---|---|---|---|---|
| OpenAI | Yes: chat and Responses image/audio/file blocks | Yes + Stream | Yes + Stream | Yes + Stream | Yes + Stream | Yes | Yes, WebSocket/WebRTC/client secrets | Reference implementation. Endpoints at `core/providers/openai/openai.go:2151-2161,2287-2301,2559-2569,2803-2811,3076-3086,3227-3247,4595-4605,4734-4743,5112-5122`; realtime converter tests in `core/providers/openai/realtime_test.go`. |
| Anthropic | Yes: native image/document content conversion | No | No | No | No | No | No | Input multimodality is real, output media methods are explicit stubs at `core/providers/anthropic/anthropic.go:2171-2212`. Do not confuse Claude vision with image generation. |
| Bedrock | Yes, model-family dependent | No | No | Yes, Titan/Nova Canvas/Stability | Yes | Yes | No gateway realtime | Image generation is real at `core/providers/bedrock/bedrock.go:2164-2233`; edit at 2243-2308; variation at 2315 onward. Speech/transcription are stubs at 2077-2078 and 2155-2161. Cross-region/inference-profile routing must preserve model-family capability. |
| Gemini API | Yes, native multimodal | Yes + Stream implementation | Yes + Stream implementation | Yes, Gemini/Imagen | Yes, Gemini/Imagen | No | No OpenAI-compatible realtime bridge proven | Real paths at `core/providers/gemini/gemini.go:1329,1640,1935-1943,2092-2099`; variation stub at 2236-2237. Image routing branches by model family. |
| Vertex AI | Yes, native multimodal | No | No | Yes, Gemini/Imagen | Yes, Gemini/Imagen | No | No | Model validation is explicit at `core/providers/vertex/vertex.go:1847-1857,2067-2077`; speech/transcription stubs at 1689-1690 and 1838-1844; variation stub at 2273-2274. Also has long-running video generation at 2277 onward. |
| ElevenLabs | Audio-oriented, not general vision | Yes + Stream; includes sound effects | Yes + Stream | No | No | No | Provider-specific audio | Real TTS dispatch at `core/providers/elevenlabs/elevenlabs.go:183-190`, transcription at 495-502; media image methods are stubs at 734-755. Strong launch candidate for voice after live conformance. |
| Hugging Face | Conditional by inference provider/model | Yes + Stream | Yes + Stream | Yes + Stream | Yes + Stream | No | No | Real paths split `inferenceProvider/model` at `core/providers/huggingface/huggingface.go:702-709,797-804,902-909,1276-1283`; variation is a stub at 1661-1662. Capability is an inference-provider/model tuple, not merely `huggingface`. |
| Replicate | Model-input dependent | No | No | Yes + Stream/prediction polling | Yes + Stream/prediction polling | No | No | Image generation and edit use predictions at `core/providers/replicate/replicate.go:1735-1745,2141-2151`; voice/transcription and variation are stubs at 1705-1731,2528-2529. Also implements video generation at 2532 onward. |
| Runware | Image input/edit focused | No | No | Yes | Yes | No | No | Real unified task-array paths at `core/providers/runware/runware.go:129-154,255-261`; variation and audio are stubs at 109-125,251-252. Stream methods are unsupported despite the uniform interface. |
| Mistral | Vision plus dedicated OCR | No | Yes + Stream | No | No | No | No | Multipart transcription is real at `core/providers/mistral/mistral.go:276-289,378`; extensive tests are in `transcription_test.go`. OCR supports document and image URLs in `core/providers/mistral/ocr.go:15-45`. Other media output methods are stubs at 793-814. |
| Groq | Vision depends on selected model/API compatibility | Delegates OpenAI-compatible path | Delegates OpenAI-compatible path + Stream | No | No | No | No | Delegation is real at `core/providers/groq/groq.go:179-186,214-221`; image methods are stubs at 236-257. Actual TTS availability must be model-catalog verified rather than inferred from converter reuse. |
| Azure OpenAI | Same schema family as OpenAI; deployment dependent | OpenAI-compatible where deployment supports it | OpenAI-compatible | Yes + Stream where supported | Yes + Stream | Deployment dependent | Provider-specific endpoint constraints | Shared OpenAI converter behavior means changes cascade; live account configuration in `core/internal/llmtests/account.go:1185-1186` marks edit/stream support. |

Other OpenAI-compatible providers generally compile because they implement the interface, not because they provide every modality. An interface method is not capability evidence. The provider account matrix itself records many `false` values (`core/internal/llmtests/account.go:992-1636`) and should seed, but not remain, the runtime capability source.

## Realtime voice is a distinct subsystem

The repository has substantially more than unary TTS/STT:

- `RealtimeRequest` and reserved session/transport/voice context keys exist at `core/schemas/bifrost.go:191,316-322`.
- OpenAI realtime event conversion includes input-audio transcription events (`core/providers/openai/realtime.go:1101` and `realtime_test.go:364,504,751`).
- The HTTP layer recognizes `/v1/realtime`, `/realtime/calls`, and client-secret/session minting variants; coverage is visible in `handlers/middlewares_test.go:419-468` and `realtime_client_secrets_test.go`.
- Realtime logging deliberately substitutes `[Audio transcription unavailable]` (`handlers/realtime_logging.go:20,122-159`) rather than storing raw audio in the normal log record.

This is promising, but launch exposure should remain OpenAI-only until there are measured session-soak, reconnect, cancellation, backpressure, ephemeral-key expiry, governance, and cost tests. Realtime sessions can outlive ordinary request assumptions and cannot be treated as a long `SpeechStream` call.

## Files, documents, OCR, and vision

The common message schemas cleanly represent URL and base64 image/file inputs. Mistral has a dedicated OCR request with document URL and image URL validation (`handlers/inference.go:1285-1302`; `providers/mistral/ocr.go:15-45`). OpenAI Files and Containers are exposed through routes at `handlers/inference.go:776-811,3362-4231`.

Gaps:

- Provider-side URL fetching creates SSRF, redirect, DNS-rebinding, private-network, payload-size, and content-type risks unless all external fetches use one hardened fetch policy. The schema comments explicitly allow providers to fetch `FileURL` at conversion time (`chatcompletions.go:1156-1158`), so enforcement must be audited per converter.
- The 25 MB audio cap is explicit, but image edit/variation multipart paths read uploads into memory (`handlers/inference.go:2313-2408,2513-2523`). The global 100 MB default limits damage but concurrent base64 expansion can still multiply heap use.
- File APIs are provider-specific. Many providers return explicit unsupported errors; gateway-owned durable object storage is not implied by the common API.
- Vision support is tested semantically through `core/internal/llmtests/image_url.go:33-143`, but model capability drift can make a provider-level boolean stale.

## Governance, security, cost, and reliability findings

### P0 before broad internal launch

1. **Capability-aware admission and routing.** Today operation allowlisting says whether an administrator permits an operation, not whether a provider/model actually supports it. Reject before provider queueing, fallback, and budget charging. Never route an image request to a text-only fallback.
2. **Harden all media URL fetches.** One egress policy must block loopback, link-local, RFC1918, metadata endpoints, unsafe redirects, DNS rebinding, oversized/decompression-bomb payloads, and disallowed MIME types. If a provider fetches the URL remotely, surface that data-residency fact in policy.
3. **Bound memory and cancellation.** Stream multipart/media bodies where possible; enforce decoded-size and pixel/duration limits, not only encoded HTTP body length. Verify client cancellation closes upstream response bodies, polling loops, SSE streams, WebSockets, and async jobs.
4. **Governance and accounting conformance.** Confirm every modality, stream, realtime session, async poll, fallback attempt, and provider-generated media unit is attributed once to virtual key/team/model. Current full-pipeline fallback re-execution makes double-counting a specific risk.
5. **Launch allowlist plus live provider matrix.** A release must not claim a cell in the matrix until a credentialed live test proves unary/stream result shape, cancellation, error metadata, governance denial, and usage extraction.

### P1

1. Add media-specific limits: maximum decoded bytes, pixels, frames/pages, audio duration/sample rate/channels, output count, realtime session duration, and async-job lifetime.
2. Add a unified media safety/redaction hook contract before logging/tracing. Store hashes, dimensions, duration, MIME, and policy outcome by default—not raw images/audio/documents.
3. Add provider/model-aware pricing units for seconds, characters, images, resolutions/quality, prediction runtime, and realtime audio tokens. Unknown usage must fail closed for spend enforcement or enter an explicitly bounded overdraft.
4. Add async job ownership, expiry, cancellation, and orphan reconciliation tests. Replicate/Vertex/HF prediction jobs need cleanup semantics on gateway timeout.
5. Expose the capability registry through HTTP/UI/docs and use it to constrain virtual-key model grants.

### P2

1. Cross-provider multimodal fallback transforms with explicit loss policy (for example, file URL to uploaded file, audio input to prior transcription) rather than silent field dropping.
2. Realtime provider abstraction beyond OpenAI only after session semantics can be normalized without lowest-common-denominator loss.
3. Media caching/deduplication by tenant-scoped content hash, with opt-in retention and deletion propagation.
4. Video-generation normalization and long-running job governance.

## Beads-ready acceptance criteria

### P0 — Authoritative model capability registry

- Registry key is provider, model/deployment, operation, input modality, output modality, streaming mode, and region where relevant.
- Each capability records source, probe/test timestamp, revision, and confidence; unknown is distinct from false.
- Admission rejects unsupported/unknown launch combinations before queueing with stable machine-readable error fields.
- Routing and fallbacks filter candidates by lossless capability compatibility before price/latency scoring.
- Governance UI, model grants, docs, and live test selection consume the same registry.
- Drift probe can disable a capability without process restart and emits an audit event.

### P0 — Hardened remote-media ingestion

- A shared fetcher validates scheme, resolved IP on every connection, redirects, MIME, content length, decoded length, timeout, and tenant egress policy.
- Tests cover loopback, private/link-local/metadata IPs, DNS rebinding, redirect escape, chunked oversize, decompression bomb, MIME spoofing, and cancellation.
- Provider converters cannot perform ad hoc network fetches outside the shared policy; exceptions are enumerated and documented as upstream-provider fetches.
- Logs and errors never contain media bytes, signed URLs, credentials, or unredacted document contents.

### P0 — Multimodal governance and billing conformance

- Table-driven tests cover allow/deny, budget exhaustion/controlled overdraft, rate limit, fallback, retry, streaming termination, async completion, and realtime disconnect for each launch modality.
- Exactly one final charge is attributable to virtual key/team/user while provider attempts remain separately observable.
- Unknown or missing provider usage cannot silently bypass budgets; configured maximum exposure is enforced.
- Model grants reject operations or modalities outside the granted capability set.

### P0 — Credentialed release matrix

- CI/release manifest enumerates every claimed provider/model/operation cell and its required secret.
- Live harness verifies success shape, malformed input, upstream error conversion, timeout, cancellation, and usage for each cell.
- Unsupported interface stubs have negative tests and are not shown as available in UI/docs.
- Release fails if a claimed cell is untested or its last successful probe exceeds the agreed freshness window.

### P1 — Media resource limits and lifecycle

- Config schema defines encoded bytes, decoded bytes, pixels/pages/duration, output count, session duration, and job TTL with safe defaults.
- Limits apply consistently to synchronous, streaming, async, WebSocket/WebRTC, and integration-layer paths.
- Load tests prove bounded heap/goroutine growth under concurrent maximum-sized uploads and slow consumers.
- Cancellation closes upstream bodies/connections and cancels or reconciles remote jobs; no orphan remains beyond TTL.

## Test evidence and verification status

Repository evidence shows a serious test framework rather than only mocks:

- Vision semantic scenario: `core/internal/llmtests/image_url.go:33-143`.
- Speech/transcription round trip and streaming: `transcription.go`, `transcription_stream.go`, `speech_synthesis_stream.go`.
- Image edit unary/stream scenarios: `image_edit.go:207-381`.
- Provider capability fixtures: `account.go:992-1636`.
- OpenAI realtime event tests and HTTP realtime governance/logging tests exist.
- Mistral transcription has extensive multipart, streaming, validation, and response tests in `core/providers/mistral/transcription_test.go`.

Attempted command:

```text
env GOCACHE=/tmp/bifrost-go-cache go test ./providers/openai ./providers/elevenlabs ./providers/huggingface ./providers/gemini ./providers/bedrock ./providers/replicate ./providers/mistral ./providers/runware
```

It did not reach compilation because the sandbox denied writes to the default Go module cache while missing dependencies (`github.com/fasthttp/websocket` and `github.com/hajimehoshi/go-mp3`) were being fetched. The first attempt also confirmed the default Go build cache is outside the writable workspace. No passing test claim is made. Credentialed `make test-core PROVIDER=...` runs remain required for release evidence.

## Bottom line

Keep Bifrost. Its multimodal architecture is already substantial and appropriately provider-specific. The launch-critical work is to turn scattered implementation knowledge into an enforceable capability contract, harden media ingestion and resource bounds, and prove governance/cost semantics across streams, realtime sessions, and asynchronous jobs. Once that is done, the existing code is a credible internal launch base; without it, the uniform API can overstate support and route costly media requests into predictable failures.
