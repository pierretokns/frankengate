# RHO initial-harness repeat (control stability)

The powered RHO optimizer rejected its candidate, leaving the initial harness
as the final artifact. A separate eight-task held-out replay of that same
initial harness scored `0.313` versus `0.643` for a second matched initial
harness control replay (paired delta `-0.330`). This is a stochastic control
stability observation, not a RHO efficacy result: both arms use the same
`h_c8c03d6d0938` harness and no generated candidate. It is retained to prevent
the rejected-candidate run from being misread as a deterministic score.
