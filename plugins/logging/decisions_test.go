package logging

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestDecisionsContentSuppression(t *testing.T) {
	p := &LoggerPlugin{disableContentLogging: schemas.Ptr(false)}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyAllowPerRequestStorageOverride, true)
	ctx.SetValue(schemas.BifrostContextKeyDisableContentLogging, false)
	ctx.BlockRestrictedWrites()
	ctx.SuppressContentLogging()
	ctx.SetValue(schemas.BifrostContextKeySuppressContentLogging, false)
	if p.contentLoggingEnabled(ctx) {
		t.Fatal("client or plugin relaxed gateway content suppression")
	}
	ctx.UnblockRestrictedWrites()
	ctx.SetValue(schemas.BifrostContextKeySuppressContentLogging, false)
	ctx.ClearValue(schemas.BifrostContextKeySuppressContentLogging)
	ctx.GetAndSetValue(schemas.BifrostContextKeySuppressContentLogging, nil)
	if p.contentLoggingEnabled(ctx) {
		t.Fatal("content suppression was not monotonic between hook phases")
	}
}

func TestDecisionsLogsKeepMetadataAndSuppressPayloads(t *testing.T) {
	store := newTestStore(t)
	plugin, err := Init(context.Background(), &Config{DisableContentLogging: schemas.Ptr(false)}, testLogger{}, store, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyRequestID, "decision-privacy")
	ctx.SetValue(schemas.BifrostContextKeyShouldStoreRawInLogs, true)
	ctx.SuppressContentLogging()
	req := &schemas.BifrostRequest{RequestType: schemas.PassthroughRequest, PassthroughRequest: &schemas.BifrostPassthroughRequest{
		Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions",
		Body: []byte(`{"input":"private input sentinel"}`), SafeHeaders: map[string]string{"content-type": "application/json"},
	}}
	if _, _, err := plugin.PreLLMHook(ctx, req); err != nil {
		t.Fatal(err)
	}
	resp := &schemas.BifrostResponse{PassthroughResponse: &schemas.BifrostPassthroughResponse{
		StatusCode: 200, Body: []byte(`{"answers":"private answer sentinel"}`),
		PassthroughUsage: &schemas.BifrostPassthroughUsage{LLMUsage: &schemas.BifrostLLMUsage{PromptTokens: 100, TotalTokens: 100}},
		ExtraFields: schemas.BifrostResponseExtraFields{RequestType: schemas.PassthroughRequest, Provider: schemas.OpenAI, OriginalModelRequested: "gpt-6-luna", ResolvedModelUsed: "gpt-6-luna", Latency: 7,
			RawRequest: "private raw input sentinel", RawResponse: "private raw response sentinel"},
	}}
	if _, _, err := plugin.PostLLMHook(ctx, resp, nil); err != nil {
		t.Fatal(err)
	}
	if err := plugin.Cleanup(); err != nil {
		t.Fatal(err)
	}
	entry, err := store.FindByID(context.Background(), "decision-privacy")
	if err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(entry)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(b), "private") {
		t.Fatal("private payload persisted")
	}
	if entry.Model != "gpt-6-luna" || entry.TokenUsageParsed == nil || entry.TokenUsageParsed.PromptTokens != 100 {
		t.Fatal("safe model or usage metadata lost")
	}
}
