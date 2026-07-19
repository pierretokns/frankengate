# Bedrock destination observability contract

FrankenGate records the destination information it actually knows at request
time, and does not infer an execution Region from a model identifier.

## Gateway-known fields

The request envelope may identify:

- the configured signing Region;
- an explicit Region prefix on the model alias;
- the resolved canonical model;
- an inference-profile ARN, when configured;
- the Bedrock Mantle project identifier and endpoint Region.

These fields describe routing inputs, not the Region in which AWS executed a
cross-Region inference-profile request.

## Assurance levels

| Level | Meaning | Evidence |
| --- | --- | --- |
| `requested` | The gateway selected a configured Region/endpoint. | Signed request metadata. |
| `profile-bound` | The request used a named inference profile. | Profile ARN plus AWS profile metadata. |
| `destination-confirmed` | AWS identified the actual destination Region. | AWS service telemetry or CloudTrail correlation. |

The gateway must emit `requested` or `profile-bound` when those facts are
available and must never label either as `destination-confirmed`. A
`destination-confirmed` value requires an external correlation worker that
joins the request identifier/profile ARN with AWS telemetry or CloudTrail.
Missing or delayed AWS evidence remains `unknown`; it is not replaced with the
configured Region.

## Quota attribution

Gateway token and latency measurements are local observations. CRIS/AIP quota
and cost attribution must be sourced from the corresponding AWS metrics and
joined by profile/application identity. Until that join exists, dashboards must
show gateway usage separately from AWS destination quota and must not claim
actual-region residency.

This contract is deliberately conservative: it prevents a plausible model ID
or endpoint Region from becoming an unsupported compliance assertion.
