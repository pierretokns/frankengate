# Natural trace memory factorial

## Outcome

Ran 16 arms over 23 eligible later-read queries from 2 public sources.
The all-runnable arm achieved 16 exact availability outcomes versus 16 for the strongest singleton.
Each runnable singleton was exact for 16/23 queries (0.696) and stale for 7. The no-memory control abstained on every query.

## Source, project, and time splits

- `fable5`: 16/19 exact (0.842).
- `wisp`: 0/4 exact (0.000).
- Anonymous project query counts: [12, 7, 4].
- Target-time bucket query counts: early=9, middle=7, late=7.
These are descriptive strata, not learned train/test generalization estimates.

## Treatment contrast gate

All four runnable singletons produced the same decision vector and every composition tied its strongest component. The corpus therefore does not identify a differential mechanism effect. Bitemporal value needs historical/valid-time queries; semantic retrieval value needs free-text targets.

## Natural release gates

- `released_dream`: not_runnable_no_natural_independent_release; 0 candidate artifact writes/edits and 0 independently released items.
- `released_procedure`: not_runnable_no_natural_independent_release; 0 candidate artifact writes/edits and 0 independently released items.

## Claim boundary

This is a natural evidence-availability study. It does not measure memory correctness, model or user utility, causal benefit, Dream quality, procedure quality, skill, or enterprise transfer. Seven stale outcomes show that a successful pre-query observation is not proof that the state remained valid at the later Read.

Raw trace content, paths, native identifiers, project identifiers, and per-item hashes are not included.
