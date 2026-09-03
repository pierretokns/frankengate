# MCP OAuth hardening decisions

Status: adopted/deferred decisions, 2026-09-02.

## Adopted

- Keep RFC 8707 resource indicators and exact audience validation on every
  Bifrost-issued MCP token. A token is for the `/mcp` resource, not a generic
  gateway identity.
- Keep enterprise-managed authorization as the two-leg ID-JAG flow: RFC 8693
  at the enterprise identity provider, then RFC 7523 at the resource
  authorization server. Cache only the final destination token.
- Return the RFC 6750 `invalid_token` challenge parameter for a failed MCP JWT,
  while retaining the RFC 9728 protected-resource metadata URL. This lets
  clients discard a bad cached token and restart discovery/authorization.
- Keep inbound-token passthrough prohibited. The gateway must mint or resolve
  a destination-bound credential for every downstream MCP connection.

## Next adoption candidates

### Sender-constrained downstream tokens

Support DPoP (RFC 9449) or mTLS-bound access tokens (RFC 8705) when a downstream
authorization server advertises the capability. This is a meaningful upgrade
over bearer-only credentials because a stolen token cannot be replayed without
the proof key or client certificate. It should be a credential-provider
capability, not a global mode: key storage, rotation, proxy forwarding, and
resource-server support must be explicit before enabling it.

### Metadata trust cross-checks

For discovered authorization servers, cross-check protected-resource metadata
and authorization-server metadata before exchange, and require every discovered
URL to pass the existing host/HTTPS policy. RFC 9728 supports both metadata
directions and signed metadata; the first implementation should use pinned
operator configuration and treat discovery as an optimization, not as a new
trust root.

### Revocation-aware cache eviction

On a downstream `401` with `invalid_token`, evict the exact subject/audience
cache entry and allow one single-flight re-exchange. Do not flush the whole
cache or retry arbitrary `403` responses. This complements the existing bounded
TTL and single-flight exchange behavior.

### Delegation lineage limits

When actor tokens are used, preserve only non-secret delegation metadata for
audit and impose a configured maximum exchange depth. RFC 8693 permits nested
`act` history, but prior actors are informational and must not widen an access
decision. The gateway should never log or persist the token material itself.

## Do not adopt

- Generic bearer-token passthrough, even when the downstream API accepts it.
- Broad multi-resource exchange requests when one resource is sufficient.
- Implicit-flow access tokens or discovery URLs treated as trusted without
  operator policy and SSRF validation.

References: [MCP Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), [Enterprise-Managed Authorization](https://github.com/modelcontextprotocol/ext-auth/blob/main/specification/stable/enterprise-managed-authorization.mdx), [RFC 8707](https://www.rfc-editor.org/rfc/rfc8707.html), [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html), [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728.html), [RFC 9700](https://datatracker.ietf.org/doc/html/rfc9700), and [RFC 9449](https://www.rfc-editor.org/rfc/rfc9449.html).
