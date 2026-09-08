//go:build !tinygo && !wasm

package mcp

import (
	"context"
	"fmt"
	"slices"
	"strings"

	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/maximhq/bifrost/core/schemas"
)

// ResourceEntry and PromptEntry retain the upstream client identity while
// exposing the standard MCP values to the HTTP gateway. MCP has no namespace
// for aggregated servers, so the transport uses this identity to create a
// collision-free gateway URI/name and maps it back on read/get.
type ResourceEntry struct {
	ClientName string       `json:"client_name"`
	Resource   mcp.Resource `json:"resource"`
}

type ResourceTemplateEntry struct {
	ClientName string               `json:"client_name"`
	Template   mcp.ResourceTemplate `json:"template"`
}

type PromptEntry struct {
	ClientName string     `json:"client_name"`
	Prompt     mcp.Prompt `json:"prompt"`
}

func (m *MCPManager) GetAvailableMCPResources(ctx *schemas.BifrostContext) ([]ResourceEntry, []ResourceTemplateEntry, error) {
	states := m.discoveryClients(ctx)
	resources := make([]ResourceEntry, 0)
	templates := make([]ResourceTemplateEntry, 0)
	var firstErr error
	for _, state := range states {
		var listedResources *mcp.ListResourcesResult
		var listedTemplates *mcp.ListResourceTemplatesResult
		err := m.runDiscoveryOperation(ctx, schemas.MCPRequestTypeListResources, state, func(conn *client.Client) error {
			var err error
			listedResources, err = conn.ListResources(ctx, mcp.ListResourcesRequest{})
			if err != nil {
				return err
			}
			listedTemplates, err = conn.ListResourceTemplates(ctx, mcp.ListResourceTemplatesRequest{})
			return err
		})
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			m.logger.Warn("%s failed to discover resources for %s: %v", MCPLogPrefix, state.Name, err)
			continue
		}
		if listedResources != nil {
			for _, resource := range listedResources.Resources {
				resources = append(resources, ResourceEntry{ClientName: state.Name, Resource: resource})
			}
		}
		if listedTemplates != nil {
			for _, template := range listedTemplates.ResourceTemplates {
				templates = append(templates, ResourceTemplateEntry{ClientName: state.Name, Template: template})
			}
		}
	}
	slices.SortStableFunc(resources, func(a, b ResourceEntry) int {
		return strings.Compare(a.ClientName+"\x00"+a.Resource.URI, b.ClientName+"\x00"+b.Resource.URI)
	})
	slices.SortStableFunc(templates, func(a, b ResourceTemplateEntry) int {
		return strings.Compare(a.ClientName+"\x00"+a.Template.Name, b.ClientName+"\x00"+b.Template.Name)
	})
	if len(resources) == 0 && len(templates) == 0 && firstErr != nil {
		return nil, nil, firstErr
	}
	return resources, templates, nil
}

func (m *MCPManager) ReadMCPResource(ctx *schemas.BifrostContext, clientName, uri string) ([]mcp.ResourceContents, error) {
	state := m.GetClientByName(clientName)
	if state == nil {
		return nil, fmt.Errorf("MCP client %q is not available", clientName)
	}
	var result *mcp.ReadResourceResult
	err := m.runDiscoveryOperation(ctx, schemas.MCPRequestTypeReadResource, state, func(conn *client.Client) error {
		var err error
		result, err = conn.ReadResource(ctx, mcp.ReadResourceRequest{Params: mcp.ReadResourceParams{URI: uri}})
		return err
	})
	if err != nil {
		return nil, err
	}
	if result == nil {
		return nil, fmt.Errorf("MCP client %q returned an empty resource response", clientName)
	}
	return result.Contents, nil
}

func (m *MCPManager) GetAvailableMCPPrompts(ctx *schemas.BifrostContext) ([]PromptEntry, error) {
	states := m.discoveryClients(ctx)
	prompts := make([]PromptEntry, 0)
	var firstErr error
	for _, state := range states {
		var listed *mcp.ListPromptsResult
		err := m.runDiscoveryOperation(ctx, schemas.MCPRequestTypeListPrompts, state, func(conn *client.Client) error {
			var err error
			listed, err = conn.ListPrompts(ctx, mcp.ListPromptsRequest{})
			return err
		})
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			m.logger.Warn("%s failed to discover prompts for %s: %v", MCPLogPrefix, state.Name, err)
			continue
		}
		if listed != nil {
			for _, prompt := range listed.Prompts {
				prompts = append(prompts, PromptEntry{ClientName: state.Name, Prompt: prompt})
			}
		}
	}
	slices.SortStableFunc(prompts, func(a, b PromptEntry) int {
		return strings.Compare(a.ClientName+"\x00"+a.Prompt.Name, b.ClientName+"\x00"+b.Prompt.Name)
	})
	if len(prompts) == 0 && firstErr != nil {
		return nil, firstErr
	}
	return prompts, nil
}

func (m *MCPManager) GetMCPPrompt(ctx *schemas.BifrostContext, clientName, name string, arguments map[string]string) (*mcp.GetPromptResult, error) {
	state := m.GetClientByName(clientName)
	if state == nil {
		return nil, fmt.Errorf("MCP client %q is not available", clientName)
	}
	var result *mcp.GetPromptResult
	err := m.runDiscoveryOperation(ctx, schemas.MCPRequestTypeGetPrompt, state, func(conn *client.Client) error {
		var err error
		result, err = conn.GetPrompt(ctx, mcp.GetPromptRequest{Params: mcp.GetPromptParams{Name: name, Arguments: arguments}})
		return err
	})
	return result, err
}

func (m *MCPManager) discoveryClients(ctx context.Context) []*schemas.MCPClientState {
	var includeClients []string
	if ctx != nil {
		includeClients, _ = ctx.Value(schemas.MCPContextKeyIncludeClients).([]string)
	}
	m.mu.RLock()
	states := make([]*schemas.MCPClientState, 0, len(m.clientMap))
	for _, state := range m.clientMap {
		if state == nil || state.ExecutionConfig == nil || state.State == schemas.MCPConnectionStateDisabled {
			continue
		}
		if !shouldIncludeClient(state.ExecutionConfig.Name, includeClients, m.logger) {
			continue
		}
		copy := *state
		states = append(states, &copy)
	}
	m.mu.RUnlock()
	slices.SortStableFunc(states, func(a, b *schemas.MCPClientState) int {
		return strings.Compare(a.Name, b.Name)
	})
	return states
}

func (m *MCPManager) runDiscoveryOperation(ctx *schemas.BifrostContext, requestType schemas.MCPRequestType, state *schemas.MCPClientState, op func(*client.Client) error) error {
	if ctx == nil {
		ctx = schemas.NewBifrostContext(m.ctx, schemas.NoDeadline)
	}
	req := &schemas.BifrostMCPRequest{RequestType: requestType, ClientName: state.Name}
	_, bifrostErr := m.RunWithPluginPipeline(ctx, req, func(_ *schemas.BifrostMCPRequest) (*schemas.BifrostMCPResponse, error) {
		conn, release, err := m.AcquireClientConn(ctx, state)
		if err != nil {
			return nil, err
		}
		defer release()
		if err := op(conn); err != nil {
			return nil, err
		}
		return &schemas.BifrostMCPResponse{}, nil
	})
	if bifrostErr != nil && bifrostErr.Error != nil {
		return fmt.Errorf("%s", bifrostErr.Error.Message)
	}
	return nil
}
