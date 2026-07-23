# AWS observation scope and client matrix

This contract defines what a future AWS Bedrock or Bedrock Mantle observation
campaign may observe. It is not an authorization to run the campaign. The C2
scope bead made no AWS calls, used no AWS credentials, and performed no paid
inference.

The normative machine-readable scope is
`provenance/aws-observation-scope.json`. Any runner must validate that manifest
with `scripts/verify-aws-observation-scope.sh` before opening a socket to AWS or
to a Bifrost instance that can reach AWS.

## Consent and Scope

Every run must record explicit human consent, operator identity, account,
region, endpoint, model, project or workspace, retention policy, allowed facts,
pricing source, and the hard ceilings that apply to the run. Wildcard account
scope is forbidden. The only region authorized by this revision is `us-east-1`.

Allowed observations are limited to routing and envelope facts: lane ID, pinned
client version, endpoint host and path template, model ID, project/workspace ID,
request IDs returned naturally by the service, HTTP status class, local latency,
local token counts, estimated cost, and assurance level. Prompt and response
bodies, secrets, credential material, and SigV4 header values are not retained.
Raw wire observations expire after 7 days; redacted facts expire after 90 days.

## Client Matrix

The matrix names six lanes:

| Lane | Mode | Surface | Status |
| --- | --- | --- | --- |
| `direct-native-bedrock` | direct client | Bedrock Runtime | enabled |
| `bifrost-native-bedrock` | through Bifrost | Bedrock provider | enabled |
| `direct-mantle-openai` | direct client | Bedrock Mantle OpenAI-compatible | enabled |
| `bifrost-mantle-openai` | through Bifrost | Bedrock Mantle OpenAI-compatible | enabled |
| `direct-mantle-anthropic` | direct client | Bedrock Mantle native Anthropic | blocked before connect |
| `bifrost-mantle-anthropic` | through Bifrost | Bedrock Mantle native Anthropic | blocked before connect |

The Mantle Anthropic lanes are intentionally present but disabled. The local
pricing catalog pins Bedrock pricing for `anthropic.claude-opus-4-8`, not a
Bedrock Mantle Anthropic price and maxima row. Unknown or stale price/maximum
data fails before connect.

Codex CLI and Claude Code are pinned at exact minimum, production, and advisory
versions in the manifest. Official OpenAI and Anthropic Python and TypeScript
SDK artifacts are pinned to the repository lockfiles. boto3 and the AWS SDK for
JavaScript Bedrock Runtime client are native-Bedrock only. AWS CLI is excluded
from Mantle lanes unless a future manifest pins exact code proving Mantle
coverage.

Through-Bifrost lanes require an immutable Bifrost container digest before
connect. The release Dockerfile base images are digest-pinned in the manifest;
the runtime image must be recorded as `ghcr.io/maximhq/bifrost@sha256:<digest>`.

## Ceilings

The hard campaign ceilings are six total attempts, one attempt per lane, four
billable calls total, one billable call per enabled lane, 512 input tokens per
call, 64 output tokens per call, 4096 total tokens, USD 0.25 estimated total
spend, USD 0.05 per lane, zero redirects, zero client retries, zero gateway
retries, and zero provider fallbacks. Where AWS supports an independently
verified account budget, that budget must be at or below USD 0.10 before any
connection is attempted.

Only naturally occurring safe errors may be observed. Operators must not
provoke auth failures, destructive operations, quota exhaustion, 429s, malformed
SigV4, or policy-denied calls.

GitHub Models and LocalStack are excluded. They do not prove AWS Bedrock or
Bedrock Mantle contracts.

## Verification

Run this local-only verifier:

```bash
scripts/verify-aws-observation-scope.sh
```

To also compare the local Codex and Claude Code binaries against the pinned
production versions, run:

```bash
VERIFY_LOCAL_CLI=1 scripts/verify-aws-observation-scope.sh
```

The verifier hashes the local pricing catalog and release Dockerfile, compares
pinned SDK versions against repository lockfiles, checks that every enabled lane
has a pricing row and model maxima, checks that disabled Mantle Anthropic lanes
fail before connect, and confirms the required exclusions and ceilings. It does
not call AWS, load credentials, start Bifrost, or run inference.
