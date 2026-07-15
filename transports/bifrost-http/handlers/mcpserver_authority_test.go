package handlers

import (
	"context"
	"errors"
	"testing"

	"github.com/golang-jwt/jwt/v5"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/plugins/governance"
	"github.com/stretchr/testify/require"
	"github.com/valyala/fasthttp"
	"gorm.io/gorm"
)

type rejectingAuthorityStore struct {
	err       error
	validated int
	row       *tables.TablePrincipalAuthorizationEpoch
	getErr    error
}

func (s *rejectingAuthorityStore) GetPrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal) (*tables.TablePrincipalAuthorizationEpoch, error) {
	return s.row, s.getErr
}
func (*rejectingAuthorityStore) ActivatePrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal, uint64, ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpoch, error) {
	panic("not used")
}
func (*rejectingAuthorityStore) AdvancePrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal, authorityepoch.Reason, ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpochEvent, error) {
	panic("not used")
}
func (*rejectingAuthorityStore) DeactivatePrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal, authorityepoch.Reason, ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpochEvent, error) {
	panic("not used")
}
func (s *rejectingAuthorityStore) ValidatePrincipalAuthorizationEpoch(_ context.Context, ref authorityepoch.Reference) error {
	s.validated++
	if ref.Kind != authorityepoch.ArtifactMCPGrant {
		return authorityepoch.ErrInvalidReference
	}
	return s.err
}
func (*rejectingAuthorityStore) ListPrincipalAuthorizationEpochEventsAfter(context.Context, uint64, int) ([]tables.TablePrincipalAuthorizationEpochEvent, error) {
	panic("not used")
}
func (*rejectingAuthorityStore) GetPrincipalAuthorizationEpochHighWatermark(context.Context) (uint64, error) {
	panic("not used")
}
func (*rejectingAuthorityStore) PrincipalAuthorizationEpochWakeups(context.Context) <-chan struct{} {
	panic("not used")
}

func TestMCPUserJWTAuthorityRejectsBeforeCachedServerUse(t *testing.T) {
	SetLogger(&mockLogger{})
	key, priv := newTestSigningKey(t)
	store := &mockOAuth2Store{signingKey: key}
	cfg := newTestOAuth2Config(store, "oauth", false)

	for _, tc := range []struct {
		name string
		err  error
	}{
		{name: "stale", err: authorityepoch.ErrStaleEpoch},
		{name: "inactive", err: authorityepoch.ErrInactivePrincipal},
	} {
		t.Run(tc.name, func(t *testing.T) {
			authority := &rejectingAuthorityStore{err: tc.err}
			h := newTestMCPHandler(cfg)
			h.authorityStore = authority
			raw := mintTestToken(t, priv, key.KID, func(c jwt.MapClaims) {
				c["bf_mode"] = "user"
				c["sub"] = "user-1"
				c["jti"] = "grant-1"
				c["bf_tenant"] = testMCPResource
				c["bf_auth_epoch"] = 7
			})
			ctx := &fasthttp.RequestCtx{}
			ctx.Request.Header.Set("Authorization", "Bearer "+raw)

			res, err := h.getMCPServerForRequest(ctx)
			require.Nil(t, res, "no cached/global MCP capability may escape failed authority")
			require.ErrorIs(t, err, tc.err)
			require.Equal(t, 1, authority.validated)

			httpCtx := &fasthttp.RequestCtx{}
			httpCtx.Request.Header.Set("Authorization", "Bearer "+raw)
			h.handleMCPServer(httpCtx)
			require.Equal(t, fasthttp.StatusUnauthorized, httpCtx.Response.StatusCode())
			require.Contains(t, string(httpCtx.Response.Header.Peek("WWW-Authenticate")), "Bearer")
			require.Equal(t, 2, authority.validated)
		})
	}
}

func TestMCPUserJWTAuthorityCompatibilityIsExplicit(t *testing.T) {
	claims := &jwtMCPClaims{RegisteredClaims: jwt.RegisteredClaims{
		Issuer: testIssuer, Subject: "user-1", Audience: jwt.ClaimStrings{testMCPResource},
	}, BfMode: "user"}

	legacy := &MCPServerHandler{}
	require.NoError(t, legacy.validateJWTAuthority(context.Background(), claims))

	enabled := &MCPServerHandler{authorityStore: &rejectingAuthorityStore{row: &tables.TablePrincipalAuthorizationEpoch{Epoch: 1, Active: true}}}
	require.ErrorIs(t, enabled.validateJWTAuthority(context.Background(), claims), authorityepoch.ErrInvalidReference)

	claims.BfTenant, claims.BfAuthEpoch, claims.ID = testMCPResource, 1, "grant-1"
	enabled.authorityStore = &rejectingAuthorityStore{err: errors.New("authority unavailable")}
	require.ErrorContains(t, enabled.validateJWTAuthority(context.Background(), claims), "authority unavailable")
}

func TestMCPRefreshGrantCannotCrossAuthorityEpoch(t *testing.T) {
	token := bindMCPRefreshTokenAuthority("opaque-random", 7)
	epoch, ok := mcpRefreshTokenAuthorityEpoch(token)
	require.True(t, ok)
	require.Equal(t, uint64(7), epoch)

	rt := &tables.TableOAuth2RefreshToken{
		FamilyID: "grant-family-1", BfMode: "user", BfSub: "user-1", Resource: testMCPResource,
	}
	authority := &rejectingAuthorityStore{err: authorityepoch.ErrStaleEpoch}
	err := validateMCPRefreshAuthority(context.Background(), authority, token, rt, testIssuer)
	require.ErrorIs(t, err, authorityepoch.ErrStaleEpoch)
	require.Equal(t, 1, authority.validated)

	require.ErrorIs(t,
		validateMCPRefreshAuthority(context.Background(), &rejectingAuthorityStore{row: &tables.TablePrincipalAuthorizationEpoch{Epoch: 1, Active: true}}, "legacy-token", rt, testIssuer),
		authorityepoch.ErrInvalidReference,
	)
	require.NoError(t, validateMCPRefreshAuthority(context.Background(), &rejectingAuthorityStore{getErr: authorityepoch.ErrUnknownPrincipal}, "legacy-token", rt, testIssuer))
	require.NoError(t, validateMCPRefreshAuthority(context.Background(), nil, "legacy-token", rt, testIssuer))
}

func TestInjectMCPUserJWTPropagatesValidatedAuthorityReference(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	claims := &jwtMCPClaims{
		RegisteredClaims: jwt.RegisteredClaims{Issuer: testIssuer, Subject: "user-1", ID: "grant-1"},
		BfMode:           "user", BfTenant: testMCPResource, BfAuthEpoch: 7,
	}
	require.NoError(t, injectJWTContext(ctx, claims, nil))
	ref, err := schemas.AuthorizationEpochReferenceFromContext(ctx)
	require.NoError(t, err)
	require.Equal(t, uint64(7), ref.Epoch)
	require.Equal(t, authorityepoch.ArtifactMCPGrant, ref.Kind)
	require.Equal(t, "grant-1", ref.ID)
}

func TestMCPDirectAuthFailsClosedWhenVKAuthorityIsStale(t *testing.T) {
	cfg := newTestOAuth2Config(&mockOAuth2Store{}, tables.MCPServerAuthModeHeaders, true)
	h := newTestMCPHandler(cfg)
	h.SetAuthorityFreshnessSource(governance.AuthorityFreshnessFunc(func() bool { return false }))
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("x-bf-vk", "sk-bf-stale")

	res, err := h.getMCPServerForRequest(ctx)
	require.Nil(t, res)
	require.ErrorContains(t, err, "authority is stale")
}
