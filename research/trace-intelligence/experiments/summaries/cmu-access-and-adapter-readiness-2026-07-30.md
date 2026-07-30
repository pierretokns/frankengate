# CMU Agent Trajectories access and adapter readiness

**Date:** 2026-07-30

**Status:** adapter conformance implemented; trajectory experiment access-gated

## Result

The authenticated Hugging Face account attempted a no-download dry run against
[`cx-cmu/agent_trajectories`](https://huggingface.co/datasets/cx-cmu/agent_trajectories)
at revision `88e2af82c116a9a57f29be6f21b9924da081c2bd`. The Hub
discovered 23 repository files and then returned `Access denied. This repository
requires approval.` No raw trajectory file is present in the local research
cache, and no CMU empirical metric has been run.

The local README is publisher metadata, not a data release. It reports 8,653
retained trajectories across six benchmarks and five models, with up to four
fresh passes per model/task. It also reports that 1,445 empty, crashed,
repeated-API-failure, or truncated trajectories were removed. That removal is a
material survivorship mechanism, not ordinary missingness.

## Work completed without raw access

`cmu_agent_trajectories.py` now defines and tests the frozen import and analysis
contract:

- every source message is preserved as an observed canonical event;
- observed assistant tool calls become `tool.proposed` events;
- observed tool results retain unique proposal correlation or explicitly report
  missing/ambiguous correlation;
- benchmark reward remains publisher-supplied independent outcome evidence;
- all four passes sharing benchmark, domain, task and source model form one
  indivisible split group;
- structural features are outcome-blind;
- the only persisted experiment output is a content-free aggregate; and
- the result explicitly states that fresh passes are not longitudinal learning.

The adapter records absent authorization, tenant, epoch, per-run tool menu,
intervention exposure, and removed failures in its loss receipt. Synthetic
conformance tests exercise complete tool lifecycle preservation, missing and
duplicate correlation, deterministic output, label blindness, split integrity,
and aggregate content minimization.

## Experiment that will run after approval

For every benchmark separately:

1. ingest all retained JSONL shards through the frozen adapter;
2. keep the four-pass group atomic across every split;
3. report parser/lifecycle loss before downstream analysis;
4. compare outcome-blind minimum-friction and trace-length selection on
   mixed-outcome groups;
5. construct failure/success contrasts as independent-attempt evidence;
6. model the removed failures with explicit worst/best-case sensitivity bounds;
7. publish aggregates only, with no raw rows, identifiers, prompts, tools or
   outputs; and
8. refuse skill, employee, natural prevalence, or learning claims.

This is useful for outcome-conditioned mechanism validation across task domains.
It cannot stand in for real-user enterprise traces, and the absent dataset
license prevents raw redistribution even if access is later granted.
