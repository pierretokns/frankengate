# Coder workstation identity boundary

## Evidence

Coder's documented automation credential is a scoped API token sent in the
`Coder-Session-Token` header; it is not documented as a JWT assertion for a
downstream gateway. Tokens support resource scopes, workspace allow-lists, and
explicit expiry/removal. See the [Coder authentication reference](https://coder.com/docs/reference/api/authentication)
and [token management](https://coder.com/docs/admin/users/sessions-tokens).

Coder also exposes the authenticated user's OIDC claims through its API, but
that endpoint requires a Coder session token. It does not make the browser's
OIDC token a safe credential to forward to FrankenGate. See the [Coder user API](https://coder.com/docs/reference/api/users).

## FrankenGate decision

1. Do not accept `Coder-Session-Token`, cached browser tokens, or arbitrary
   workstation headers as FrankenGate authentication.
2. A Coder integration must exchange a short-lived, audience-bound token at a
   trusted control-plane boundary. The resulting FrankenGate token must carry
   issuer, audience, subject, workspace ID, agent/session ID, and an authority
   epoch; verify signature, issuer, audience, expiry, and epoch on every
   control-plane reveal/rotate request.
3. Workstation name and peer address are audit attributes only. They never
   grant identity or authorization and must be sanitized before persistence.
4. Virtual-key reveal and rotation require an explicit control-plane scope and
   user/team policy. Inference authorization must not imply secret-reveal
   authorization.
5. Revocation is fail-closed: expire the exchanged token, bump the principal
   authority epoch, or remove the Coder workspace allow-list before a reveal or
   rotation can proceed.

The implementation remains gated until a trusted exchange endpoint and
Coder-issued workspace/agent claim contract are specified. This document does
not claim that Coder currently supplies a gateway-verifiable JWT.
