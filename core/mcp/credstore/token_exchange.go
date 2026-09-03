package credstore

import (
	"fmt"
	"net/http"

	"github.com/maximhq/bifrost/core/mcp/tokenexchange"
	"github.com/maximhq/bifrost/core/schemas"
)

// tokenExchangeResolver turns the already-authenticated request credential into
// a destination-bound credential. The exchanged token is resolved after the
// connect hook, just like the other per-user resolvers, so plugins cannot see it.
// This follows MCP's authorization rule that a client must not pass an inbound
// access token through to an upstream resource server.
type tokenExchangeResolver struct {
	exchanger *tokenexchange.Exchanger
}

func (r *tokenExchangeResolver) ConnectionHeaders(ctx *schemas.BifrostContext, config *schemas.MCPClientConfig) (http.Header, error) {
	if config == nil || config.TokenExchange == nil || !config.TokenExchange.Enabled {
		return nil, fmt.Errorf("MCP client %q requires an enabled token_exchange profile", configName(config))
	}
	if _, err := schemas.AuthorizationPrincipalFromContext(ctx); err != nil {
		return nil, fmt.Errorf("MCP client %q requires a trusted authorization principal for token exchange", config.Name)
	}
	token, err := r.exchanger.ExchangeFromContext(ctx, config.TokenExchange)
	if err != nil {
		return nil, fmt.Errorf("token exchange for MCP client %q failed: %w", config.Name, err)
	}
	headers := make(http.Header)
	headers.Set("Authorization", "Bearer "+token)
	return headers, nil
}

func (r *tokenExchangeResolver) RequiresPerCallConnection() bool { return true }

func configName(config *schemas.MCPClientConfig) string {
	if config == nil {
		return "<nil>"
	}
	return config.Name
}
