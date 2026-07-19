# Upstream v1.6.4 security/config adoption record

FrankenGate adopts the semantics of the three reviewed upstream fixes, with
local tests and compatibility-preserving adaptations:

| Upstream change | Decision | Local evidence |
| --- | --- | --- |
| `82f094d8d` (`/api/devices` auth-prefix bypass) | Adapted | `transports/bifrost-http/handlers/middlewares.go`; `TestAuthMiddleware_APIMiddleware_DevPrefixDoesNotMatchDevices` proves `/api/devices` is not covered by `/api/dev`. |
| `45ca33009` (masked provider-key preview persistence) | Adapted | `transports/bifrost-http/handlers/providers.go`; `TestMergeUpdatedKey`, `TestRestoreRedacted`, and SQLite hash-comparison tests prove masked previews are not written over real secrets. |
| `07a046cb1` (bare wildcard `allowed_models`) | Adapted | Configstore migration/round-trip fixtures repair bare `*` rows idempotently and preserve canonical wildcard behavior. |

No upstream commit is cherry-picked blindly: the fork keeps its existing API,
database schema, and migration ownership while retaining the security
properties of each fix. The remaining compatibility gate is PostgreSQL and
pre-upgrade-binary rehearsal; SQLite race coverage is not used to claim those
environments are verified.
