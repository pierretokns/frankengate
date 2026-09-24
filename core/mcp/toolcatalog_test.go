package mcp

import (
	"context"
	"testing"

	"github.com/mark3labs/mcp-go/client"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestSearchToolsRanksNameBeforeDescription(t *testing.T) {
	name := "search_documents"
	description := "Searches indexed documents"
	otherName := "list_documents"
	otherDescription := "Searches indexed documents"
	mgr := &MCPManager{
		ctx:    context.Background(),
		logger: &MockLogger{},
	}
	mgr.toolsManager = newToolsManagerForTest(&searchToolClientManager{
		tools: []schemas.ChatTool{
			{Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: name, Description: &description}},
			{Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: otherName, Description: &otherDescription}},
		},
	})

	results := mgr.SearchTools(schemas.NewBifrostContext(context.Background(), schemas.NoDeadline), "search documents", 10)
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
	if results[0].Tool.Function.Name != name {
		t.Fatalf("expected exact name match first, got %q", results[0].Tool.Function.Name)
	}
}

func TestSearchToolsLimitAndEmptyQuery(t *testing.T) {
	first := "alpha"
	second := "beta"
	mgr := &MCPManager{
		ctx:    context.Background(),
		logger: &MockLogger{},
	}
	mgr.toolsManager = newToolsManagerForTest(&searchToolClientManager{
		tools: []schemas.ChatTool{
			{Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: first}},
			{Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: second}},
		},
	})

	results := mgr.SearchTools(schemas.NewBifrostContext(context.Background(), schemas.NoDeadline), "", 1)
	if len(results) != 1 {
		t.Fatalf("expected limit to be enforced, got %d", len(results))
	}
	if results[0].Tool.Function.Name != first {
		t.Fatalf("expected deterministic alphabetical result, got %q", results[0].Tool.Function.Name)
	}
}

func TestSearchToolsHonorsClientFilter(t *testing.T) {
	allowedName := "allowed_lookup"
	hiddenName := "hidden_lookup"
	mgr := &MCPManager{
		ctx:    context.Background(),
		logger: &MockLogger{},
		clientMap: map[string]*schemas.MCPClientState{
			"allowed": {
				Name:            "allowed",
				ExecutionConfig: &schemas.MCPClientConfig{Name: "allowed", ToolsToExecute: schemas.WhiteList{"*"}},
				ToolMap:         map[string]schemas.ChatTool{allowedName: {Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: allowedName}}},
				State:           schemas.MCPConnectionStateConnected,
			},
			"hidden": {
				Name:            "hidden",
				ExecutionConfig: &schemas.MCPClientConfig{Name: "hidden", ToolsToExecute: schemas.WhiteList{"*"}},
				ToolMap:         map[string]schemas.ChatTool{hiddenName: {Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: hiddenName}}},
				State:           schemas.MCPConnectionStateConnected,
			},
		},
	}
	mgr.toolsManager = newToolsManagerForTest(mgr)
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.MCPContextKeyIncludeClients, []string{"allowed"})

	results := mgr.SearchTools(ctx, "lookup", 10)
	if len(results) != 1 || results[0].Tool.Function.Name != allowedName {
		t.Fatalf("expected only the authorized client tool, got %#v", results)
	}
}

type searchToolClientManager struct {
	tools []schemas.ChatTool
}

func (m *searchToolClientManager) GetClientByName(name string) *schemas.MCPClientState {
	return &schemas.MCPClientState{
		Name: name,
		ExecutionConfig: &schemas.MCPClientConfig{
			Name:             name,
			IsCodeModeClient: false,
		},
	}
}
func (m *searchToolClientManager) GetClientForTool(string) *schemas.MCPClientState { return nil }
func (m *searchToolClientManager) GetToolPerClient(context.Context) map[string][]schemas.ChatTool {
	return map[string][]schemas.ChatTool{"search": m.tools}
}
func (m *searchToolClientManager) GetPluginPipeline() PluginPipeline    { return nil }
func (m *searchToolClientManager) ReleasePluginPipeline(PluginPipeline) {}
func (m *searchToolClientManager) AcquireClientConn(*schemas.BifrostContext, *schemas.MCPClientState) (*client.Client, func(), error) {
	return nil, func() {}, nil
}
func (m *searchToolClientManager) RunWithPluginPipeline(ctx *schemas.BifrostContext, req *schemas.BifrostMCPRequest, op MCPOpFunc) (*schemas.BifrostMCPResponse, *schemas.BifrostError) {
	resp, err := op(req)
	if err != nil {
		return nil, &schemas.BifrostError{Error: &schemas.ErrorField{Message: err.Error()}}
	}
	return resp, nil
}
