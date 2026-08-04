# Dataset-task fit audit

**Status:** verified admission audit
**Coverage:** 44 pinned dataset manifests and six claim profiles

## Result

| Claim | Direct-fit manifests | Proxy-only | Mechanics-only |
|---|---:|---:|---:|
| NL2SQL schema retrieval | 2 | 1 | 41 |
| Trace structure | 3 | 14 | 27 |
| Friction/recovery | 0 | 0 | 44 |
| Skill improvement | 0 | 0 | 44 |
| Cross-user similarity | 0 | 0 | 44 |
| Term/alias quality | 0 | 0 | 44 |

The two direct NL2SQL datasets are the governed Defog SQL fixture and the WMH
BIRD trace corpus. They support schema/identifier retrieval, SQL execution,
and bounded replay—not enterprise skill or collaboration claims. No admitted
manifest currently contains the observations needed for a direct claim about
cross-user similarity, skill improvement, or reviewed enterprise alias
quality.

Receipt:
[`dataset-fit-audit-2026-08-04.json`](../results/dataset-fit-audit-2026-08-04.json)

Independent verification:
[`dataset-fit-audit-2026-08-04-verification.json`](../results/dataset-fit-audit-2026-08-04-verification.json)

The audit is intentionally conservative: missing observations lower a claim to
`proxy_only` or `mechanics_only`; unsupported-claim text is never treated as
positive evidence.
