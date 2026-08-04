package handlers

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/logstore"
	"github.com/maximhq/bifrost/plugins/logging"
	"github.com/stretchr/testify/require"
	"github.com/valyala/fasthttp"
)

type selfServiceLogManager struct {
	logging.LogManager
	filters    *logstore.SearchFilters
	pagination *logstore.PaginationOptions
}

func (m *selfServiceLogManager) Search(_ context.Context, filters *logstore.SearchFilters, pagination *logstore.PaginationOptions) (*logstore.SearchResult, error) {
	m.filters = filters
	m.pagination = pagination
	return &logstore.SearchResult{Logs: []logstore.Log{}, Pagination: *pagination}, nil
}

func TestAuthenticatedUserIDFailsClosed(t *testing.T) {
	ctx := &fasthttp.RequestCtx{}
	_, ok := authenticatedUserID(ctx)
	require.False(t, ok)

	ctx.SetUserValue(schemas.BifrostContextKeyUserID, "  user-123  ")
	userID, ok := authenticatedUserID(ctx)
	require.True(t, ok)
	require.Equal(t, "user-123", userID)
}

func TestBuildEvalSuggestionsUsesTracesAsEvidence(t *testing.T) {
	stopReason := "length"
	latency := 2500.0
	logs := []logstore.Log{
		{
			ID:             "trace-error",
			Model:          "model-a",
			Status:         "error",
			ContentSummary: "Find the customer record",
			ToolsParsed:    make([]schemas.ChatTool, 2),
			Latency:        &latency,
		},
		{ID: "trace-long", Model: "model-b", Status: "success", StopReason: &stopReason, InputHistoryParsed: make([]schemas.ChatMessage, 6), Latency: &latency},
		{ID: "trace-3", Model: "model-a", Status: "success", Latency: &latency},
		{ID: "trace-4", Model: "model-a", Status: "success", Latency: &latency},
		{ID: "trace-5", Model: "model-a", Status: "success", Latency: &latency},
	}

	suggestions := buildEvalSuggestions(logs)
	ids := make(map[string]evalSuggestion, len(suggestions))
	for _, suggestion := range suggestions {
		ids[suggestion.ID] = suggestion
	}

	require.Contains(t, ids, "trace-regression")
	require.Contains(t, ids, "error-recovery")
	require.Contains(t, ids, "tool-selection")
	require.Contains(t, ids, "context-retention")
	require.Contains(t, ids, "boundary-behavior")
	require.Contains(t, ids, "model-portability")
	require.Contains(t, ids, "latency-budget")
	require.Equal(t, []string{"trace-error"}, ids["error-recovery"].Evidence.SampleTraceIDs)
	require.Contains(t, ids["trace-regression"].Evidence.Explanation, "rather than truth")
}

func TestBuildEvalSuggestionsEmptyHistory(t *testing.T) {
	require.Empty(t, buildEvalSuggestions(nil))
}

func TestMyPromptHistoryAlwaysScopesToAuthenticatedUser(t *testing.T) {
	manager := &selfServiceLogManager{}
	handler := NewLoggingHandler(manager, nil, nil)
	ctx := &fasthttp.RequestCtx{}
	ctx.SetUserValue(schemas.BifrostContextKeyUserID, "user-owner")
	ctx.Request.URI().SetQueryString("limit=25&offset=10&user_id=someone-else")

	handler.getMyPromptHistory(ctx)

	require.Equal(t, fasthttp.StatusOK, ctx.Response.StatusCode())
	require.Equal(t, []string{"user-owner"}, manager.filters.UserIDs)
	require.Equal(t, 25, manager.pagination.Limit)
	require.Equal(t, 10, manager.pagination.Offset)
}

func TestMyPromptHistoryRejectsMissingIdentity(t *testing.T) {
	manager := &selfServiceLogManager{}
	handler := NewLoggingHandler(manager, nil, nil)
	ctx := &fasthttp.RequestCtx{}

	handler.getMyPromptHistory(ctx)

	require.Equal(t, fasthttp.StatusUnauthorized, ctx.Response.StatusCode())
	require.Nil(t, manager.filters)
}
