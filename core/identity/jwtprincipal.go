// Package identity contains authentication adapters that turn external
// identity assertions into FrankenGate's canonical principal tuple.
package identity

import (
	"crypto/rsa"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/maximhq/bifrost/core/authorityepoch"
)

var (
	ErrIssuerMismatch   = errors.New("identity: issuer mismatch")
	ErrAudienceMismatch = errors.New("identity: audience mismatch")
	ErrMissingSubject   = errors.New("identity: subject missing")
	ErrExpired          = errors.New("identity: token expired")
)

// JWTConfig describes the trust boundary for a workstation token. Issuer and
// Audience are deliberately required; accepting values supplied by the token
// would allow a token minted for another application or tenant to authenticate
// to the gateway.
type JWTConfig struct {
	Tenant   string
	Issuer   string
	Audience string
	// KeyFunc resolves a signing key from the token header. A JWKS-backed
	// implementation can rotate keys without changing this adapter.
	KeyFunc jwt.Keyfunc
	// Clock exists for deterministic tests and controlled deployments.
	Clock func() time.Time
}

// Claims is the bounded identity projection retained after verification.
// Groups and WorkstationID are copied for authorization/attribution only; the
// raw JWT is never retained.
type Claims struct {
	Principal     authorityepoch.Principal
	Groups        []string
	WorkstationID string
	ExpiresAt     time.Time
}

type jwtClaims struct {
	jwt.RegisteredClaims
	Groups        []string `json:"groups,omitempty"`
	WorkstationID string   `json:"workstation_id,omitempty"`
}

// Verify validates a signed Coder/OIDC JWT and returns its canonical principal.
// Only RS256 is accepted by default because workstation identity is an
// enterprise trust boundary; callers can wrap KeyFunc but cannot weaken issuer,
// audience, expiry, or subject checks.
func Verify(raw string, cfg JWTConfig) (Claims, error) {
	if strings.TrimSpace(raw) == "" || strings.TrimSpace(cfg.Tenant) == "" ||
		strings.TrimSpace(cfg.Issuer) == "" || strings.TrimSpace(cfg.Audience) == "" || cfg.KeyFunc == nil {
		return Claims{}, errors.New("identity: incomplete verifier configuration")
	}
	clock := cfg.Clock
	if clock == nil {
		clock = time.Now
	}
	parsed := &jwtClaims{}
	tok, err := jwt.ParseWithClaims(raw, parsed, func(t *jwt.Token) (any, error) {
		if t.Method != jwt.SigningMethodRS256 {
			return nil, fmt.Errorf("identity: unexpected signing method %q", t.Method.Alg())
		}
		return cfg.KeyFunc(t)
	}, jwt.WithValidMethods([]string{jwt.SigningMethodRS256.Alg()}),
		jwt.WithIssuer(cfg.Issuer), jwt.WithAudience(cfg.Audience),
		jwt.WithExpirationRequired(), jwt.WithIssuedAt())
	if err != nil || tok == nil || !tok.Valid {
		if err != nil {
			if errors.Is(err, jwt.ErrTokenExpired) {
				return Claims{}, ErrExpired
			}
			if errors.Is(err, jwt.ErrTokenInvalidIssuer) {
				return Claims{}, ErrIssuerMismatch
			}
			if errors.Is(err, jwt.ErrTokenInvalidAudience) {
				return Claims{}, ErrAudienceMismatch
			}
		}
		return Claims{}, fmt.Errorf("identity: invalid token: %w", err)
	}
	// jwt's validator uses time.Now; apply the injected clock to the explicit
	// expiry check so tests and deployments with a controlled clock remain safe.
	if parsed.ExpiresAt == nil || !parsed.ExpiresAt.Time.After(clock()) {
		return Claims{}, ErrExpired
	}
	if strings.TrimSpace(parsed.Subject) == "" {
		return Claims{}, ErrMissingSubject
	}
	if parsed.Issuer != cfg.Issuer {
		return Claims{}, ErrIssuerMismatch
	}
	audienceMatch := false
	for _, audience := range parsed.Audience {
		if audience == cfg.Audience {
			audienceMatch = true
			break
		}
	}
	if !audienceMatch {
		return Claims{}, ErrAudienceMismatch
	}
	principal := authorityepoch.Principal{Tenant: cfg.Tenant, Issuer: parsed.Issuer, Subject: parsed.Subject}
	if err := authorityepoch.ValidatePrincipal(principal); err != nil {
		return Claims{}, err
	}
	groups := append([]string(nil), parsed.Groups...)
	return Claims{Principal: principal, Groups: groups, WorkstationID: parsed.WorkstationID, ExpiresAt: parsed.ExpiresAt.Time}, nil
}

// RSAKeyFunc is a small helper for static or JWKS-cached RSA keys.
func RSAKeyFunc(key *rsa.PublicKey) jwt.Keyfunc {
	return func(_ *jwt.Token) (any, error) { return key, nil }
}
