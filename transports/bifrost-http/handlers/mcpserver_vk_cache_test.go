package handlers

import (
	"context"
	"testing"

	"github.com/mark3labs/mcp-go/server"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

type testMCPVirtualKeyCache struct {
	byID    map[string]*tables.TableVirtualKey
	byValue map[string]*tables.TableVirtualKey
}

func (c *testMCPVirtualKeyCache) GetVirtualKeyByID(_ context.Context, id string) (*tables.TableVirtualKey, bool) {
	vk, ok := c.byID[id]
	return vk, ok
}

func (c *testMCPVirtualKeyCache) GetVirtualKey(_ context.Context, value string) (*tables.TableVirtualKey, bool) {
	vk, ok := c.byValue[value]
	return vk, ok
}

func TestEnsureVKMCPServerByValueRejectsInactiveCachedServer(t *testing.T) {
	value := "sk-bf-now-inactive"
	active := false
	vk := &tables.TableVirtualKey{
		ID:       "vk-now-inactive",
		Name:     "now-inactive",
		Value:    *schemas.NewSecretVar(value),
		IsActive: &active,
	}
	cachedServer := server.NewMCPServer("stale", "test")
	h := &MCPServerHandler{
		vkCache: &testMCPVirtualKeyCache{
			byID:    map[string]*tables.TableVirtualKey{vk.ID: vk},
			byValue: map[string]*tables.TableVirtualKey{value: vk},
		},
		vkMCPServers: map[string]*server.MCPServer{value: cachedServer},
	}

	got, err := h.ensureVKMCPServerByValue(context.Background(), value)
	require.Nil(t, got)
	require.EqualError(t, err, "virtual key is inactive")
	_, stillCached := h.vkMCPServers[value]
	require.False(t, stillCached)
}

func TestEnsureVKMCPServerByValueReturnsValidatedCachedServer(t *testing.T) {
	value := "sk-bf-active"
	active := true
	vk := &tables.TableVirtualKey{
		ID:       "vk-active",
		Name:     "active",
		Value:    *schemas.NewSecretVar(value),
		IsActive: &active,
	}
	cachedServer := server.NewMCPServer("active", "test")
	h := &MCPServerHandler{
		vkCache: &testMCPVirtualKeyCache{
			byID:    map[string]*tables.TableVirtualKey{vk.ID: vk},
			byValue: map[string]*tables.TableVirtualKey{value: vk},
		},
		vkMCPServers: map[string]*server.MCPServer{value: cachedServer},
	}

	got, err := h.ensureVKMCPServerByValue(context.Background(), value)
	require.NoError(t, err)
	require.Same(t, cachedServer, got)
}
