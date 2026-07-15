package handlers

import (
	"context"
	"crypto/rsa"
	"errors"
	"fmt"
	"slices"
	"strconv"
	"strings"
	"sync"

	"github.com/golang-jwt/jwt/v5"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configtables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

// mcpJWTPublicKeys caches the parsed RSA public key so verification can skip
// re-parsing the PEM on every request. Keyed by the public-key PEM (its content)
// rather than the kid: the content uniquely identifies the keypair, so a rotated
// key materializes a fresh entry while a reused kid across distinct keys can
// never alias the wrong key. The signing key is immutable for the process
// lifetime, so an entry never goes stale.
var mcpJWTPublicKeys sync.Map // publicKeyPEM (string) -> *rsa.PublicKey

// mcpJWTPublicKey returns the verification public key for the given signing key,
// parsing and caching it on first use.
func mcpJWTPublicKey(signingKey *configtables.OAuth2SigningKey) (*rsa.PublicKey, error) {
	if cached, ok := mcpJWTPublicKeys.Load(signingKey.PublicKeyPEM); ok {
		return cached.(*rsa.PublicKey), nil
	}
	pubKey, err := parseRSAPublicKeyPEM(signingKey.PublicKeyPEM)
	if err != nil {
		return nil, fmt.Errorf("invalid signing key: %w", err)
	}
	mcpJWTPublicKeys.Store(signingKey.PublicKeyPEM, pubKey)
	return pubKey, nil
}

const mcpRefreshAuthorityEpochMarker = ".ae"

func bindMCPRefreshTokenAuthority(token string, epoch uint64) string {
	if epoch == 0 {
		return token
	}
	return token + mcpRefreshAuthorityEpochMarker + strconv.FormatUint(epoch, 10)
}

func mcpRefreshTokenAuthorityEpoch(token string) (uint64, bool) {
	idx := strings.LastIndex(token, mcpRefreshAuthorityEpochMarker)
	if idx < 0 {
		return 0, false
	}
	epoch, err := strconv.ParseUint(token[idx+len(mcpRefreshAuthorityEpochMarker):], 10, 64)
	return epoch, err == nil && epoch > 0
}

func validateMCPRefreshAuthority(ctx context.Context, store any, token string, rt *configtables.TableOAuth2RefreshToken, issuer string) error {
	authorityStore, ok := store.(configstore.PrincipalAuthorizationEpochStore)
	if !ok || authorityStore == nil {
		return nil
	}
	if rt == nil || schemas.MCPAuthMode(rt.BfMode) != schemas.MCPAuthModeUser {
		return nil
	}
	epoch, ok := mcpRefreshTokenAuthorityEpoch(token)
	if !ok {
		principal := authorityepoch.Principal{Tenant: rt.Resource, Issuer: issuer, Subject: rt.BfSub}
		if err := authorityepoch.ValidatePrincipal(principal); err != nil {
			return err
		}
		_, err := authorityStore.GetPrincipalAuthorizationEpoch(ctx, principal)
		if errors.Is(err, authorityepoch.ErrUnknownPrincipal) {
			return nil
		}
		if err != nil {
			return err
		}
		return authorityepoch.ErrInvalidReference
	}
	ref := authorityepoch.Reference{
		Principal: authorityepoch.Principal{Tenant: rt.Resource, Issuer: issuer, Subject: rt.BfSub},
		Epoch:     epoch,
		Kind:      authorityepoch.ArtifactMCPGrant,
		ID:        rt.FamilyID,
	}
	if err := authorityepoch.ValidateReferenceShape(ref); err != nil {
		return err
	}
	return authorityStore.ValidatePrincipalAuthorizationEpoch(ctx, ref)
}

func deactivateMCPUserAuthority(ctx context.Context, store any, tenant, issuer, subject string) error {
	authorityStore, ok := store.(configstore.PrincipalAuthorizationEpochStore)
	if !ok || authorityStore == nil {
		return nil
	}
	principal := authorityepoch.Principal{Tenant: tenant, Issuer: issuer, Subject: subject}
	_, err := authorityStore.DeactivatePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonDeactivated)
	if errors.Is(err, authorityepoch.ErrUnknownPrincipal) || errors.Is(err, authorityepoch.ErrInactivePrincipal) {
		return nil
	}
	return err
}

// jwtMCPClaims are the custom claims embedded in Bifrost-issued /mcp JWTs.
type jwtMCPClaims struct {
	jwt.RegisteredClaims
	BfMode      string `json:"bf_mode"` // user | vk | session
	Scope       string `json:"scope"`
	BfTenant    string `json:"bf_tenant,omitempty"`
	BfAuthEpoch uint64 `json:"bf_auth_epoch,omitempty"`
}

func mcpJWTAuthorizationPrincipal(claims *jwtMCPClaims) (authorityepoch.Principal, error) {
	if claims == nil || schemas.MCPAuthMode(claims.BfMode) != schemas.MCPAuthModeUser {
		return authorityepoch.Principal{}, authorityepoch.ErrInvalidPrincipal
	}
	tenant := claims.BfTenant
	// Tokens issued before authorization epochs did not carry bf_tenant. Their
	// already-verified RFC 8707 audience is the same canonical MCP resource used
	// as the tenant by current issuance, so it is the only safe compatibility
	// fallback. Multiple or absent audiences remain fail-closed.
	if tenant == "" && len(claims.Audience) == 1 {
		tenant = claims.Audience[0]
	}
	principal := authorityepoch.Principal{Tenant: tenant, Issuer: claims.Issuer, Subject: claims.Subject}
	if err := authorityepoch.ValidatePrincipal(principal); err != nil {
		return authorityepoch.Principal{}, err
	}
	return principal, nil
}

// ensureMCPJWTAuthorizationEpoch activates a principal on first issuance and
// returns the durable epoch embedded in the access token. Deployments whose
// config store does not implement the authority store retain legacy tokens;
// once supported, issuance is fail-closed on storage errors.
func ensureMCPJWTAuthorizationEpoch(ctx context.Context, store any, tenant, issuer, subject string) (uint64, error) {
	authorityStore, ok := store.(configstore.PrincipalAuthorizationEpochStore)
	if !ok || authorityStore == nil {
		return 0, nil
	}
	principal := authorityepoch.Principal{Tenant: tenant, Issuer: issuer, Subject: subject}
	if err := authorityepoch.ValidatePrincipal(principal); err != nil {
		return 0, err
	}
	row, err := authorityStore.GetPrincipalAuthorizationEpoch(ctx, principal)
	if err == nil {
		if row == nil || !row.Active || row.Epoch == 0 {
			return 0, authorityepoch.ErrInactivePrincipal
		}
		return row.Epoch, nil
	}
	if !errors.Is(err, authorityepoch.ErrUnknownPrincipal) {
		return 0, err
	}
	row, err = authorityStore.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
	if errors.Is(err, authorityepoch.ErrStaleEpoch) {
		row, err = authorityStore.GetPrincipalAuthorizationEpoch(ctx, principal)
	}
	if err != nil {
		return 0, err
	}
	if row == nil || !row.Active || row.Epoch == 0 {
		return 0, authorityepoch.ErrInactivePrincipal
	}
	return row.Epoch, nil
}

// extractBearerJWT returns the raw JWT string from an Authorization: Bearer
// header when the token looks like a JWT (starts with "eyJ"). Returns empty
// string when the header is absent or the token is a VK (starts with "sk-bf-").
func extractBearerJWT(ctx *fasthttp.RequestCtx) string {
	auth := strings.TrimSpace(string(ctx.Request.Header.Peek("Authorization")))
	if auth == "" {
		return ""
	}
	if !strings.HasPrefix(strings.ToLower(auth), "bearer ") {
		return ""
	}
	token := strings.TrimSpace(auth[7:])
	// JWTs are base64url-encoded JSON starting with '{', which encodes to "eyJ".
	// VKs start with the "sk-bf-" prefix. Anything not starting with "eyJ" is
	// treated as a non-JWT credential and left to the VK path.
	if !strings.HasPrefix(token, "eyJ") {
		return ""
	}
	return token
}

// verifyMCPJWT parses and verifies a Bifrost-issued JWT for the /mcp endpoint.
// It validates the RS256 signature using the supplied signing key, checks the
// audience matches the canonical /mcp resource URL (RFC 8707), and returns
// the verified claims. The caller provides the signing key (typically from a
// process-lifetime cache) so verification need not read it per request.
func verifyMCPJWT(ctx *fasthttp.RequestCtx, rawToken string, store *lib.Config, signingKey *configtables.OAuth2SigningKey) (*jwtMCPClaims, error) {
	if signingKey == nil {
		return nil, fmt.Errorf("signing key unavailable")
	}

	pubKey, err := mcpJWTPublicKey(signingKey)
	if err != nil {
		return nil, err
	}

	// Pin the issuer to this instance: the kid + signature checks only prove the
	// token was signed by our key, so a different authorization server sharing
	// the same keypair would otherwise pass. Issuance stamps iss from the same
	// oauth2IssuerURL, so the two always agree.
	issuer := oauth2IssuerURL(ctx, store)

	claims := &jwtMCPClaims{}
	tok, err := jwt.ParseWithClaims(rawToken, claims, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		if kid, _ := t.Header["kid"].(string); kid != signingKey.KID {
			return nil, fmt.Errorf("unknown key id %q", kid)
		}
		return pubKey, nil
	}, jwt.WithExpirationRequired(), jwt.WithIssuedAt(), jwt.WithIssuer(issuer),
		// Accept exactly the algorithm we issue. The SigningMethodRSA type
		// assertion above admits the whole RS family (RS256/384/512); pin to
		// RS256 so verification matches issuance.
		jwt.WithValidMethods([]string{jwt.SigningMethodRS256.Alg()}))
	if err != nil {
		return nil, fmt.Errorf("invalid token: %w", err)
	}
	if !tok.Valid {
		return nil, fmt.Errorf("token is not valid")
	}
	// WithIssuedAt only validates iat when present; require it, since every
	// token we issue stamps one.
	if claims.IssuedAt == nil {
		return nil, fmt.Errorf("token missing iat claim")
	}

	// RFC 8707: the token must have been issued for this specific resource.
	resource := oauth2MCPResourceURL(ctx, store)
	aud, err := claims.GetAudience()
	if err != nil || !slices.Contains(aud, resource) {
		return nil, fmt.Errorf("token audience does not match this resource")
	}

	return claims, nil
}

// injectJWTContext sets the identity context keys from verified JWT claims,
// mirroring what header auth sets today so everything downstream (governance,
// per-user upstream OAuth, tool-group filtering) works unchanged.
//
// bf_mode=user    → BifrostContextKeyUserID
// bf_mode=vk      → BifrostContextKeyVirtualKey (governance derives the VK row ID from it)
// bf_mode=session → BifrostContextKeyMCPSessionID
func injectJWTContext(bifrostCtx *schemas.BifrostContext, claims *jwtMCPClaims, vk *configtables.TableVirtualKey) error {
	sub := claims.Subject
	if sub == "" {
		return fmt.Errorf("JWT missing sub claim")
	}
	switch schemas.MCPAuthMode(claims.BfMode) {
	case schemas.MCPAuthModeUser:
		bifrostCtx.SetValue(schemas.BifrostContextKeyUserID, sub)
		if claims.BfAuthEpoch > 0 {
			principal, err := mcpJWTAuthorizationPrincipal(claims)
			if err != nil {
				return err
			}
			if err := schemas.SetAuthorizationEpochReference(bifrostCtx, authorityepoch.Reference{
				Principal: principal,
				Epoch:     claims.BfAuthEpoch,
				Kind:      authorityepoch.ArtifactMCPGrant,
				ID:        claims.ID,
			}); err != nil {
				return err
			}
		}
	case schemas.MCPAuthModeVK:
		if vk == nil {
			return fmt.Errorf("VK not provided for vk-mode JWT injection")
		}
		// Set the VK value only. Governance's PreMCPConnectionHook resolves it to
		// the VK row ID (BifrostContextKeyGovernanceVirtualKeyID) on the connect
		// path before the per-user credential resolver needs it — the same way the
		// x-bf-vk header path does, which never stamps the row ID at ingress either.
		bifrostCtx.SetValue(schemas.BifrostContextKeyVirtualKey, vk.Value.GetValue())
	case schemas.MCPAuthModeSession:
		bifrostCtx.SetValue(schemas.BifrostContextKeyMCPSessionID, sub)
	default:
		return fmt.Errorf("unknown bf_mode %q in JWT", claims.BfMode)
	}
	return nil
}

// wwwAuthenticateValue returns the WWW-Authenticate header value pointing at
// the /mcp resource metadata endpoint, per RFC 9728 §5.
func wwwAuthenticateValue(ctx *fasthttp.RequestCtx, store *lib.Config) string {
	base := oauth2IssuerURL(ctx, store)
	return fmt.Sprintf(`Bearer resource_metadata="%s/.well-known/oauth-protected-resource/mcp"`, base)
}
