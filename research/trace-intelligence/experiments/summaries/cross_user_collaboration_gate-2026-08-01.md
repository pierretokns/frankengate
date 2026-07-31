# Cross-user collaboration gate (2026-08-01)

The existing retrieval and H5 receipts demonstrate authorization mechanics:
wrong-tenant, wrong-subject, and stale-epoch queries produce zero candidates
before ranking. They do not establish that two users are doing the same work,
that a shared artifact is useful, or that an introduction is wanted.

The available 145-document/99-query benchmark uses publisher-supplied silver
task labels. It has no independent human same-work labels, reciprocal consent,
randomized shared-artifact or introduction exposure, verified transfer outcome,
or unwanted-contact measure. The collaboration feature therefore remains
explicitly unbuilt rather than inferred from retrieval relevance.
