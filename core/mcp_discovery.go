package bifrost

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	coremcp "github.com/maximhq/bifrost/core/mcp"
	"github.com/maximhq/bifrost/core/schemas"
)

func (bifrost *Bifrost) GetAvailableMCPResources(ctx context.Context) ([]coremcp.ResourceEntry, []coremcp.ResourceTemplateEntry, error) {
	manager, ok := bifrost.MCPManager.(coremcp.MCPDiscoveryManager)
	if !ok {
		return nil, nil, nil
	}
	return manager.GetAvailableMCPResources(newMCPDiscoveryContext(ctx, bifrost))
}

func (bifrost *Bifrost) ReadMCPResource(ctx context.Context, clientName, uri string) ([]mcp.ResourceContents, error) {
	manager, ok := bifrost.MCPManager.(coremcp.MCPDiscoveryManager)
	if !ok {
		return nil, nil
	}
	return manager.ReadMCPResource(newMCPDiscoveryContext(ctx, bifrost), clientName, uri)
}

func (bifrost *Bifrost) GetAvailableMCPPrompts(ctx context.Context) ([]coremcp.PromptEntry, error) {
	manager, ok := bifrost.MCPManager.(coremcp.MCPDiscoveryManager)
	if !ok {
		return nil, nil
	}
	return manager.GetAvailableMCPPrompts(newMCPDiscoveryContext(ctx, bifrost))
}

func (bifrost *Bifrost) GetMCPPrompt(ctx context.Context, clientName, name string, arguments map[string]string) (*mcp.GetPromptResult, error) {
	manager, ok := bifrost.MCPManager.(coremcp.MCPDiscoveryManager)
	if !ok {
		return nil, nil
	}
	return manager.GetMCPPrompt(newMCPDiscoveryContext(ctx, bifrost), clientName, name, arguments)
}

func (bifrost *Bifrost) SearchMCPTools(ctx context.Context, query string, limit int) []coremcp.ToolSearchResult {
	manager, ok := bifrost.MCPManager.(*coremcp.MCPManager)
	if !ok {
		return nil
	}
	return manager.SearchTools(newMCPDiscoveryContext(ctx, bifrost), query, limit)
}

func newMCPDiscoveryContext(ctx context.Context, bifrost *Bifrost) *schemas.BifrostContext {
	if ctx == nil {
		return schemas.NewBifrostContext(bifrost.ctx, schemas.NoDeadline)
	}
	return schemas.NewBifrostContext(ctx, schemas.NoDeadline)
}
