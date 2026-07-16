package handlers

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	governanceplugin "github.com/maximhq/bifrost/plugins/governance"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

var errListModelsVKAuthorityStale = errors.New(governanceplugin.VirtualKeyAuthorityStaleReason)

type listModelsVirtualKeyResolver func(context.Context, string) (*configstoreTables.TableVirtualKey, error)

func newListModelsVirtualKeyResolver(config *lib.Config) listModelsVirtualKeyResolver {
	return func(ctx context.Context, value string) (*configstoreTables.TableVirtualKey, error) {
		if config == nil {
			return nil, errors.New("governance authority unavailable: config is nil")
		}
		plugin, err := lib.FindPluginAs[*governanceplugin.GovernancePlugin](config, governanceplugin.PluginName)
		if err != nil {
			return nil, fmt.Errorf("governance authority unavailable: %w", err)
		}
		if !plugin.IsAuthorityFresh() {
			return nil, errListModelsVKAuthorityStale
		}
		vk, ok := plugin.GetGovernanceStore().GetVirtualKey(ctx, value)
		if !ok || vk == nil {
			return nil, configstore.ErrNotFound
		}
		return vk, nil
	}
}

// applyListModelsVirtualKeyProviderFilter narrows provider fan-out for GET /v1/models
// when the request is made with a virtual key. Without this, ListAllModels asks every
// configured provider to list models and governance rejects providers outside the VK,
// creating noisy, expected errors in request logs.
func (h *CompletionHandler) applyListModelsVirtualKeyProviderFilter(ctx *fasthttp.RequestCtx, bifrostCtx *schemas.BifrostContext) bool {
	vkValue := governanceplugin.ParseVirtualKeyFromFastHTTPRequest(ctx)
	if vkValue == nil {
		return true
	}

	trimmedVKValue := strings.TrimSpace(*vkValue)
	if trimmedVKValue == "" {
		return true
	}

	if h.resolveListModelsVirtualKey == nil {
		SendError(ctx, fasthttp.StatusServiceUnavailable, "virtual key authority unavailable")
		return false
	}

	vk, err := h.resolveListModelsVirtualKey(ctx, trimmedVKValue)
	if err != nil {
		if errors.Is(err, errListModelsVKAuthorityStale) {
			SendError(ctx, fasthttp.StatusServiceUnavailable, governanceplugin.VirtualKeyAuthorityStaleReason)
			return false
		}
		if errors.Is(err, configstore.ErrNotFound) {
			SendError(ctx, fasthttp.StatusUnauthorized, "virtual key not found. The provided virtual key does not exist or has been revoked.")
			return false
		}
		SendError(ctx, fasthttp.StatusInternalServerError, fmt.Sprintf("Failed to resolve virtual key: %v", err))
		return false
	}
	if vk == nil || vk.IsActive == nil || !*vk.IsActive {
		SendError(ctx, fasthttp.StatusUnauthorized, "virtual key not found. The provided virtual key does not exist or has been revoked.")
		return false
	}

	availableProviders := make([]schemas.ModelProvider, 0, len(vk.ProviderConfigs))
	for _, providerConfig := range vk.ProviderConfigs {
		provider := strings.TrimSpace(providerConfig.Provider)
		if provider == "" {
			continue
		}
		availableProviders = append(availableProviders, schemas.ModelProvider(provider))
	}

	bifrostCtx.SetValue(schemas.BifrostContextKeyAvailableProviders, availableProviders)
	return true
}
