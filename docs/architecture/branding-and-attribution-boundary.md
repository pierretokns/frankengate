# Branding and attribution boundary

FrankenGate is the fork-owned product identity. Upstream Bifrost names remain
only where they are required for legal attribution, compatibility contracts,
or historical provenance. They must not be used to imply affiliation,
support, or ownership.

Every identity reference is classified as one of:

- `retain-attribution`: LICENSE, NOTICE, provenance, and source-credit text;
- `retain-compatibility`: API headers, environment variables, migration names,
  and import paths whose change would break drop-in consumers;
- `historical-only`: changelog and migration history;
- `migrate`: public package, chart, binary, registry, or website identity;
- `remove`: stale upstream marketing, badges, domains, or support links.

The rename gate is not satisfied by changing README text alone. It requires a
machine-readable inventory with an owner and destination decision for every
tracked reference, followed by build, chart, package, and documentation link
checks. Legal attribution and non-affiliation notices must remain intact while
fork-owned public surfaces move to FrankenGate.

Generate the review inventory from the repository root with:

```sh
scripts/branding-inventory.sh /tmp/frankengate-branding-inventory.tsv
```

The generator is deliberately non-mutating; each row still requires a human
owner decision before any rename or removal is applied.
