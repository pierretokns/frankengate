package handlers

import (
	"encoding/json"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/modelcatalog"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

func TestAgentModelCardValidationReasonsAreStableAndDedupeCodes(t *testing.T) {
	reasons := validateAgentModelCardPayload(modelcatalog.AgentModelCard{ProviderMapping: modelcatalog.AgentModelProviderMapping{Provider: schemas.OpenAI}})
	if len(reasons) < 3 {
		t.Fatalf("expected multiple validation reasons, got %#v", reasons)
	}
	codes := dedupeAgentModelCardReasonCodes(reasons)
	if len(codes) != len(map[string]struct{}{"agent_model_card_provider_required": {}, "agent_model_card_model_required": {}, "agent_model_card_base_model_required": {}, "agent_model_card_wire_model_required": {}, "agent_model_card_provider_mapping_mismatch": {}, "agent_model_card_capability_state_invalid": {}}) {
		t.Fatalf("expected stable deduplicated reason codes, got %#v", codes)
	}
	for _, code := range codes {
		if code == "" {
			t.Fatal("reason code must not be empty")
		}
	}
}

func TestAgentModelCardPaginationAndETagMatching(t *testing.T) {
	cards := []modelcatalog.AgentModelCard{{Model: "a"}, {Model: "b"}, {Model: "c"}}
	page, more := paginateAgentModelCards(cards, 2, 1)
	if len(page) != 2 || page[0].Model != "b" || more {
		t.Fatalf("unexpected page: %#v more=%v", page, more)
	}
	_, more = paginateAgentModelCards(cards, 2, 0)
	if !more {
		t.Fatal("first page should report remaining cards")
	}
	if !agentModelCardETagMatches(`W/"digest", "other"`, `"digest"`) || !agentModelCardETagMatches("*", `"digest"`) {
		t.Fatal("weak and wildcard ETag matches should be honored")
	}
	if agentModelCardETagMatches(`"other"`, `"digest"`) {
		t.Fatal("unrelated ETag must not match")
	}
}

func TestAgentModelCardMetadataIsVisibleAndETagged(t *testing.T) {
	catalog := modelcatalog.NewTestCatalog(nil)
	catalog.UpsertLive(schemas.OpenAI, "key-a", false, []string{"gpt-4o", "hidden-model"})

	h := &ProviderHandler{
		inMemoryStore: &lib.Config{
			Providers: map[schemas.ModelProvider]configstore.ProviderConfig{
				schemas.OpenAI: {},
			},
			ModelCatalog: catalog,
		},
		modelsManager: &mockModelsManager{
			filtered: map[schemas.ModelProvider][]string{
				schemas.OpenAI: {"gpt-4o"},
			},
		},
	}

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetMethod(fasthttp.MethodGet)
	ctx.Request.SetRequestURI("/api/v1/agent-model-cards/metadata?provider=openai")

	h.getAgentModelCardMetadataV1(ctx)

	if got := ctx.Response.StatusCode(); got != fasthttp.StatusOK {
		t.Fatalf("expected 200, got %d: %s", got, string(ctx.Response.Body()))
	}
	etag := string(ctx.Response.Header.Peek("ETag"))
	if etag == "" {
		t.Fatal("metadata response must include an ETag")
	}

	var raw map[string]json.RawMessage
	if err := json.Unmarshal(ctx.Response.Body(), &raw); err != nil {
		t.Fatalf("failed to unmarshal raw metadata response: %v", err)
	}
	if _, ok := raw["cards"]; ok {
		t.Fatal("metadata endpoint must not include card bodies")
	}

	var resp agentModelCardMetadataResponse
	if err := json.Unmarshal(ctx.Response.Body(), &resp); err != nil {
		t.Fatalf("failed to unmarshal metadata response: %v", err)
	}
	if resp.SchemaVersion != agentModelCardAPIResponseSchemaVersion {
		t.Fatalf("schema_version = %q, want %q", resp.SchemaVersion, agentModelCardAPIResponseSchemaVersion)
	}
	if resp.CardSchemaVersion != modelcatalog.AgentModelCardSchemaVersion {
		t.Fatalf("card_schema_version = %q, want %q", resp.CardSchemaVersion, modelcatalog.AgentModelCardSchemaVersion)
	}
	if resp.Revision.ID == "" || resp.Revision.CardCount != 2 {
		t.Fatalf("expected stable catalog revision for both compiled cards, got %#v", resp.Revision)
	}
	if resp.VisibleCardCount != 1 {
		t.Fatalf("expected one visible card after provider/model filtering, got %d", resp.VisibleCardCount)
	}
	if resp.Export.Path != "/api/v1/agent-model-cards/export" || resp.Export.Filename == "" {
		t.Fatalf("expected export metadata, got %#v", resp.Export)
	}
	if len(resp.SourcePrecedence) == 0 || len(resp.Sources) == 0 {
		t.Fatalf("expected source metadata, got precedence=%#v sources=%#v", resp.SourcePrecedence, resp.Sources)
	}

	cachedCtx := &fasthttp.RequestCtx{}
	cachedCtx.Request.Header.SetMethod(fasthttp.MethodGet)
	cachedCtx.Request.Header.Set("If-None-Match", etag)
	cachedCtx.Request.SetRequestURI("/api/v1/agent-model-cards/metadata?provider=openai")

	h.getAgentModelCardMetadataV1(cachedCtx)

	if got := cachedCtx.Response.StatusCode(); got != fasthttp.StatusNotModified {
		t.Fatalf("expected 304 for matching ETag, got %d: %s", got, string(cachedCtx.Response.Body()))
	}
	if len(cachedCtx.Response.Body()) != 0 {
		t.Fatalf("304 response must not include a body, got %q", string(cachedCtx.Response.Body()))
	}
}

func TestAgentModelCardMetadataUnavailableIsReasonCoded(t *testing.T) {
	h := &ProviderHandler{
		inMemoryStore: &lib.Config{},
		modelsManager: &mockModelsManager{},
	}

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetMethod(fasthttp.MethodGet)
	ctx.Request.SetRequestURI("/api/v1/agent-model-cards/metadata")

	h.getAgentModelCardMetadataV1(ctx)

	if got := ctx.Response.StatusCode(); got != fasthttp.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d: %s", got, string(ctx.Response.Body()))
	}

	var bifrostErr schemas.BifrostError
	if err := json.Unmarshal(ctx.Response.Body(), &bifrostErr); err != nil {
		t.Fatalf("failed to unmarshal error response: %v", err)
	}
	if bifrostErr.Error == nil || bifrostErr.Error.Code == nil || *bifrostErr.Error.Code != agentModelCardReasonCatalogUnavailable {
		t.Fatalf("expected catalog-unavailable reason code, got %#v", bifrostErr.Error)
	}
}
