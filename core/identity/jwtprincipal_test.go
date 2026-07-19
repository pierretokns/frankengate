package identity

import (
	"crypto/rand"
	"crypto/rsa"
	"errors"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

func signedToken(t *testing.T, key *rsa.PrivateKey, issuer, audience, subject string, exp time.Time) string {
	t.Helper()
	c := jwt.MapClaims{"iss": issuer, "aud": audience, "sub": subject, "iat": time.Now().Unix(), "exp": exp.Unix(), "groups": []string{"research"}, "workstation_id": "coder-1"}
	tok := jwt.NewWithClaims(jwt.SigningMethodRS256, c)
	raw, err := tok.SignedString(key)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestVerifyMapsCoderClaimsToPrincipal(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	raw := signedToken(t, key, "https://okta.example", "frankengate", "user-1", time.Now().Add(time.Hour))
	got, err := Verify(raw, JWTConfig{Tenant: "corp", Issuer: "https://okta.example", Audience: "frankengate", KeyFunc: RSAKeyFunc(&key.PublicKey)})
	if err != nil {
		t.Fatal(err)
	}
	if got.Principal.Tenant != "corp" || got.Principal.Issuer != "https://okta.example" || got.Principal.Subject != "user-1" {
		t.Fatalf("principal = %+v", got.Principal)
	}
	if len(got.Groups) != 1 || got.WorkstationID != "coder-1" {
		t.Fatalf("projection = %+v", got)
	}
}

func TestVerifyFailsClosedIssuerAudienceExpiry(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		name             string
		issuer, audience string
		exp              time.Time
		want             error
	}{
		{"issuer", "https://wrong", "frankengate", time.Now().Add(time.Hour), ErrIssuerMismatch},
		{"audience", "https://okta.example", "other", time.Now().Add(time.Hour), ErrAudienceMismatch},
		{"expired", "https://okta.example", "frankengate", time.Now().Add(-time.Minute), ErrExpired},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			raw := signedToken(t, key, tc.issuer, tc.audience, "user-1", tc.exp)
			_, err := Verify(raw, JWTConfig{Tenant: "corp", Issuer: "https://okta.example", Audience: "frankengate", KeyFunc: RSAKeyFunc(&key.PublicKey)})
			if !errors.Is(err, tc.want) {
				t.Fatalf("err = %v, want %v", err, tc.want)
			}
		})
	}
}

func TestVerifyRejectsMissingSubjectAndAlgorithm(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	raw := signedToken(t, key, "https://okta.example", "frankengate", "", time.Now().Add(time.Hour))
	_, err = Verify(raw, JWTConfig{Tenant: "corp", Issuer: "https://okta.example", Audience: "frankengate", KeyFunc: RSAKeyFunc(&key.PublicKey)})
	if !errors.Is(err, ErrMissingSubject) {
		t.Fatalf("err = %v, want missing subject", err)
	}
	hmac := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{"iss": "https://okta.example", "aud": "frankengate", "sub": "user", "iat": time.Now().Unix(), "exp": time.Now().Add(time.Hour).Unix()})
	bad, _ := hmac.SignedString([]byte("not-a-rsa-key"))
	if _, err := Verify(bad, JWTConfig{Tenant: "corp", Issuer: "https://okta.example", Audience: "frankengate", KeyFunc: RSAKeyFunc(&key.PublicKey)}); err == nil {
		t.Fatal("accepted non-RS256 token")
	}
}
