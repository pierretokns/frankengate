package openai

import (
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestToCodexListModelsResponseAddsCatalogAndReasoningFields(t *testing.T) {
	ua := schemas.CodexCLI.String()
	ctx := schemas.NewBifrostContext(nil, time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyUserAgent, ua)
	resp := ToCodexListModelsResponse(ctx, &schemas.BifrostListModelsResponse{Data: []schemas.Model{{ID: "bedrock_mantle/openai.gpt-5.5"}}})
	model := resp.Data[0]
	if model.Slug != "bedrock_mantle/gpt-5.5" || model.DisplayName == "" || model.DefaultReasoningLevel != "medium" || model.UseResponsesLite == nil || !*model.UseResponsesLite {
		t.Fatalf("unexpected Codex model metadata: %#v", model)
	}
	if len(model.SupportedReasoningLevels) != 3 || model.SupportedReasoningLevels[0].Effort != "low" || model.SupportedReasoningLevels[2].Effort != "high" {
		t.Fatalf("unexpected reasoning levels: %#v", model.SupportedReasoningLevels)
	}
}

func TestToCodexListModelsResponseLeavesOrdinaryClientsStandard(t *testing.T) {
	ctx := schemas.NewBifrostContext(nil, time.Time{})
	resp := ToCodexListModelsResponse(ctx, &schemas.BifrostListModelsResponse{Data: []schemas.Model{{ID: "openai/gpt-5.5"}}})
	if resp.Data[0].Slug != "" || resp.Data[0].SupportedReasoningLevels != nil {
		t.Fatalf("Codex fields leaked to ordinary client: %#v", resp.Data[0])
	}
}
