package a2abroker

import (
	"context"
	"fmt"
	"net/http"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
)

// TokenExchanger is deliberately narrow so transport wiring can inject the
// existing RFC 8693/7523 implementation without coupling the broker to HTTP.
// Implementations must not persist subject, actor, or exchanged token values.
type TokenExchanger interface {
	Exchange(context.Context, *schemas.MCPTokenExchangeConfig, string, string) (string, error)
}

// RuntimeCredentialResolver adapts FrankenGate's existing OAuth and token
// exchange stores to the outbound A2A credential seam. It resolves only at
// dispatch time and returns headers in memory; task state never receives the
// token material.
type RuntimeCredentialResolver struct {
	OAuthProvider schemas.OAuth2Provider
	Exchanger     TokenExchanger
}

func (r RuntimeCredentialResolver) Resolve(ctx context.Context, request CredentialRequest) (Credential, error) {
	kind, err := kindForScheme(request.Scheme)
	if err != nil {
		return Credential{}, err
	}

	if exchange := request.TokenExchange; exchange != nil && exchange.Enabled {
		if r.Exchanger == nil || strings.TrimSpace(request.SubjectToken) == "" {
			return Credential{}, ErrCredentialRequired
		}
		token, err := r.Exchanger.Exchange(ctx, exchange, request.SubjectToken, request.ActorToken)
		if err != nil {
			return Credential{}, fmt.Errorf("A2A token exchange unavailable: %w", err)
		}
		if strings.TrimSpace(token) == "" {
			return Credential{}, ErrCredentialRequired
		}
		return bearerCredential(CredentialTokenExchange, token), nil
	}

	if kind == CredentialBearer && request.AllowSubjectPassThrough {
		if strings.TrimSpace(request.SubjectToken) == "" {
			return Credential{}, ErrCredentialRequired
		}
		return bearerCredential(CredentialPassThrough, request.SubjectToken), nil
	}

	if kind != CredentialOAuth2 && kind != CredentialOIDC {
		if kind == CredentialMTLS {
			return Credential{Kind: CredentialMTLS, Headers: make(http.Header)}, nil
		}
		return Credential{}, ErrCredentialRequired
	}
	if r.OAuthProvider == nil {
		return Credential{}, ErrCredentialRequired
	}

	var token string
	if request.AuthMode != "" && request.AuthMode != schemas.MCPAuthModeNone {
		if strings.TrimSpace(request.Identity) == "" || strings.TrimSpace(request.MCPClientID) == "" {
			return Credential{}, ErrCredentialRequired
		}
		token, err = r.OAuthProvider.GetUserAccessTokenByMode(ctx, request.AuthMode, request.Identity, request.MCPClientID)
	} else if strings.TrimSpace(request.OAuthConfigID) != "" {
		token, err = r.OAuthProvider.GetAccessToken(ctx, request.OAuthConfigID)
	} else {
		return Credential{}, ErrCredentialRequired
	}
	if err != nil {
		return Credential{}, fmt.Errorf("A2A OAuth credential unavailable: %w", err)
	}
	if strings.TrimSpace(token) == "" {
		return Credential{}, ErrCredentialRequired
	}
	return bearerCredential(kind, token), nil
}

func bearerCredential(kind CredentialKind, token string) Credential {
	headers := make(http.Header)
	headers.Set("Authorization", "Bearer "+strings.TrimSpace(token))
	return Credential{Kind: kind, Headers: headers}
}

var _ CredentialResolver = RuntimeCredentialResolver{}
