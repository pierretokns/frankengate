# Enterprise embedding promotion gate (2026-08-01)

The CodeTraceBench silver-label factorial keeps structured retrieval as the
strong baseline (`Recall@20 = 0.808`) and adds a general dense channel
(`Recall@20 = 0.818`, +1.0 percentage point). This is not the registered
promotion threshold: a trace-adapted embedding must gain at least five absolute
Recall@20 points on a frozen human hard-negative slice, with no exact-ID,
subgroup, deletion, latency, or transfer regression.

No adapted-model arm was run because the required user/project/task/time-held-
out training split and human labels do not yet exist. Custom embedding training
is therefore deferred, not rejected on the basis of an underpowered silver
pilot.
