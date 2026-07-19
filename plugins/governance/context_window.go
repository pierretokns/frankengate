package governance

import (
	"fmt"
	"strings"

	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/providers/anthropic"
	"github.com/maximhq/bifrost/core/schemas"
)

// validateContextWindowHeaders is the request-admission membrane for beta
// context-window headers. A header is an explicit request to use a larger
// provider window; silently forwarding it to an unknown model or surface can
// change billing and produce provider-specific failures. We therefore reject
// it before any provider call unless the resolved provider/model/surface is
// one of the catalogued Anthropic 1M paths.
func validateContextWindowHeaders(ctx *schemas.BifrostContext, provider schemas.ModelProvider, model string, requestType schemas.RequestType) *schemas.BifrostError {
	if ctx == nil {
		return nil
	}
	extra, ok := ctx.Value(schemas.BifrostContextKeyExtraHeaders).(map[string][]string)
	if !ok || len(extra) == 0 {
		return nil
	}
	requested := false
	for key, values := range extra {
		if !strings.EqualFold(key, "anthropic-beta") {
			continue
		}
		for _, value := range values {
			for token := range strings.SplitSeq(value, ",") {
				if strings.HasPrefix(strings.ToLower(strings.TrimSpace(token)), anthropic.AnthropicContext1MBetaHeaderPrefix) {
					requested = true
				}
			}
		}
	}
	if !requested {
		return nil
	}

	surfaceSupported := requestType == schemas.ChatCompletionRequest ||
		requestType == schemas.ChatCompletionStreamRequest ||
		requestType == schemas.ResponsesRequest ||
		requestType == schemas.ResponsesStreamRequest
	providerSupported := provider == schemas.Anthropic || provider == schemas.Bedrock ||
		provider == schemas.BedrockMantle || provider == schemas.Vertex || provider == schemas.Azure
	if !surfaceSupported || !providerSupported || !anthropic.SupportsContext1MModel(model) {
		return &schemas.BifrostError{
			Type:       bifrost.Ptr("context_window_unsupported"),
			StatusCode: bifrost.Ptr(400),
			Error: &schemas.ErrorField{Message: fmt.Sprintf(
				"context-1m beta header is unsupported for provider %q, model %q, request type %q",
				provider, model, requestType)},
			AllowFallbacks: bifrost.Ptr(false),
		}
	}
	return nil
}
