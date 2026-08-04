package handlers

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog"
)

func TestAgentModelCardValidationReasonsAreStableAndDedupeCodes(t *testing.T) {
	reasons := validateAgentModelCardPayload(modelcatalog.AgentModelCard{ProviderMapping: modelcatalog.AgentModelProviderMapping{Provider: schemas.OpenAI}})
	if len(reasons) < 3 {
		t.Fatalf("expected multiple validation reasons, got %#v", reasons)
	}
	codes := dedupeAgentModelCardReasonCodes(reasons)
	if len(codes) != len(map[string]struct{}{"agent_model_card_provider_required": {}, "agent_model_card_model_required": {}, "agent_model_card_base_model_required": {}, "agent_model_card_wire_model_required": {}, "agent_model_card_provider_mapping_mismatch": {}}) {
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
	if len(page) != 2 || page[0].Model != "b" || !more {
		t.Fatalf("unexpected page: %#v more=%v", page, more)
	}
	if !agentModelCardETagMatches(`W/"digest", "other"`, `"digest"`) || !agentModelCardETagMatches("*", `"digest"`) {
		t.Fatal("weak and wildcard ETag matches should be honored")
	}
	if agentModelCardETagMatches(`"other"`, `"digest"`) {
		t.Fatal("unrelated ETag must not match")
	}
}
