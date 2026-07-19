# Dashboard Okta boundary

The dashboard currently has a local session boundary; it is not an Okta OIDC
implementation. This contract defines the required integration seam without
silently treating MCP OAuth as dashboard authentication.

An Okta-backed dashboard session must validate discovery issuer, client ID,
audience, signature, expiry, nonce, and PKCE state before issuing a secure
rotating session cookie. Redirect URIs are an explicit allowlist. JWKS keys are
cached with bounded refresh and a `kid` miss triggers one discovery refresh;
unknown issuers, malformed claims, stale sessions, and failed refreshes fail
closed.

Groups map to roles through a server-side allowlist. Team and user scope is
derived from validated claims and persisted membership, never from UI-selected
IDs. Every dashboard API and page route must enforce the same authorization
boundary. Login, logout, callback failure, denied access, role changes, and
expiry produce redacted audit events; tokens, authorization codes, and client
secrets must never enter logs.

Until this boundary is wired and its signature/issuer/audience/nonce/state/key
rotation and role-boundary tests exist, the dashboard must continue using its
existing local session behavior and must not advertise Okta support as shipped.
