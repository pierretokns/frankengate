# Branded pricing synchronization

The gateway already supports a configurable pricing URL and a 24-hour runtime
sync. For the public site, `scripts/pricing-sync` provides a separate,
last-known-good publication path. It fetches the configured public Bifrost
datasheet (or another approved URL), validates that it is a non-empty JSON
object containing model objects, and atomically writes:

* `latest-upstream.json` — validated upstream document;
* `latest.json` — FrankenGate-branded envelope with source and retrieval time;
* `archive/pricing-<UTC timestamp>.json` — immutable historical snapshot.

An HTTP failure, malformed payload, or write error exits non-zero and never
replaces `latest.json`. The helper is an independent Go module under
`scripts/pricing-sync`; run it from that directory so it does not depend on the
developer-only workspace file. The repository includes a minimal
`.gitlab-ci.yml` entrypoint which includes `.gitlab/pricing-sync.yml`. Configure
one GitLab Pipeline Schedule for that mirror, daily in UTC, and have the site's
deployment step publish the artifact. Do not expose credentials in the URL.

## Attribution and licensing

The pricing data is sourced from the public Bifrost datasheet. FrankenGate does
not claim ownership of upstream model prices; the generated envelope retains
the source URL and retrieval timestamp for attribution and auditability. Review
the upstream repository/site license and any provider-specific pricing terms
before redistributing a snapshot. This repository's branding applies only to
the wrapper and publication plumbing, not to upstream data.
