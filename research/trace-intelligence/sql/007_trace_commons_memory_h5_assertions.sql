\set ON_ERROR_STOP on

-- Transaction-scoped H5 conformance for the Trace Commons memory-composition
-- result. This script stores only synthetic scope values, aggregate counters,
-- and pinned artifact identities. It never imports trace events, prompts,
-- responses, file paths, tool identifiers, or extracted memory text.
begin;

create or replace function pg_temp.assert_count(
  label text,
  actual bigint,
  expected bigint
) returns void
language plpgsql
as $function$
begin
  if actual <> expected then
    raise exception '%: got %, expected %', label, actual, expected;
  end if;
end
$function$;

create or replace function pg_temp.assert_raises(
  label text,
  statement text
) returns void
language plpgsql
as $function$
begin
  begin
    execute statement;
  exception
    when others then
      return;
  end;
  raise exception '%: statement unexpectedly succeeded', label;
end
$function$;

-- Fail early if this is not the intended forced-RLS research schema.
select pg_temp.assert_count(
  'all H5 lifecycle roles exist',
  (
    select count(*)
    from pg_roles
    where rolname in (
      'trace_research_app',
      'trace_research_miner',
      'trace_research_evaluator',
      'trace_research_releaser'
    )
  ),
  4
);
select pg_temp.assert_count(
  'H5 lifecycle roles have no dangerous attributes',
  (
    select count(*)
    from pg_roles
    where rolname in (
      'trace_research_app',
      'trace_research_miner',
      'trace_research_evaluator',
      'trace_research_releaser'
    )
      and (
        rolsuper or rolbypassrls or rolcreaterole or rolcreatedb
        or rolinherit
      )
  ),
  0
);
select pg_temp.assert_count(
  'all H5 protected tables enable and force RLS',
  (
    select count(*)
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'trace_research'
      and c.relname in (
        'trajectories',
        'events',
        'derived_artifacts',
        'artifact_candidates',
        'replay_manifests',
        'evaluation_runs',
        'artifact_releases',
        'release_exposures',
        'trajectory_influences',
        'release_events'
      )
      and c.relrowsecurity
      and c.relforcerowsecurity
  ),
  10
);
select pg_temp.assert_count(
  'runtime roles own no H5 protected table',
  (
    select count(*)
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    join pg_roles r on r.oid = c.relowner
    where n.nspname = 'trace_research'
      and c.relname in (
        'trajectories',
        'events',
        'derived_artifacts',
        'artifact_candidates',
        'replay_manifests',
        'evaluation_runs',
        'artifact_releases',
        'release_exposures',
        'trajectory_influences',
        'release_events'
      )
      and r.rolname in (
        'trace_research_app',
        'trace_research_miner',
        'trace_research_evaluator',
        'trace_research_releaser'
      )
  ),
  0
);

-- All authority values below are deterministic test fixtures. They are not
-- copied from the content-free result or its source traces.
insert into trace_research.authority_epochs (
  tenant_id, subject_id, authorization_epoch, classification_ceiling
) values
  ('tc-h5-tenant', 'tc-h5-source-owner', 41, 2),
  ('tc-h5-tenant', 'tc-h5-analyst', 41, 2),
  ('tc-h5-tenant', 'tc-h5-outsider', 41, 2);

insert into trace_research.team_memberships (
  tenant_id, team_id, subject_id
) values (
  'tc-h5-tenant', 'tc-h5-team', 'tc-h5-analyst'
);

insert into trace_research.trajectories (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, source_dataset, source_revision,
  adapter_revision, task_id, harness, model_name, outcome, loss_receipt,
  raw_payload, content_sha256
) values
  (
    'tc-h5-source', 'tc-h5-tenant', 'tc-h5-source-owner', 'team',
    'tc-h5-team', 1, array['trace-memory-research'], 'tc-h5-policy-v1',
    'trace-commons/agent-traces-full-claude-memory-composition',
    '112ebd4d03ce852b00e935d523107c3d0c9a65bf',
    'deterministic-full-cohort-composition-preflight-v4',
    'tc-h5-full-cohort-aggregate', 'claude-code', null,
    '{
      "histories": 28,
      "records": 17991,
      "native_calls": 4264,
      "native_results": 4262,
      "qualifying_interactions": 67,
      "supported_observations": 50,
      "unique_supported_revisions": 48,
      "online_queries": 3,
      "contextual_online_exact": 1,
      "contextual_online_stale": 2,
      "contextual_online_abstentions": 0,
      "exact_cross_session_write_to_later_read": 1,
      "same_basename_placebo_cases": 6,
      "contextual_placebo_leaks": 0,
      "latest_only_placebo_leaks": 3,
      "future_positive_cases": 13,
      "future_positive_detected": 13,
      "future_filter_leaks": 0,
      "all_negative_controls_passed": false,
      "comparative_quality_claim_allowed": false
    }',
    '{
      "claim": "content-free full-cohort memory mechanics only",
      "does_not_claim": [
        "failed-job atomicity",
        "human identity",
        "continuous validity",
        "memory correctness",
        "memory utility",
        "skill improvement",
        "enterprise transfer"
      ],
      "raw_content_emitted": false,
      "artifact_paths_emitted": false,
      "tool_identifiers_emitted": false,
      "authority_values_emitted": false
    }',
    '{}',
    '3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5'
  ),
  (
    'tc-h5-private-control', 'tc-h5-tenant', 'tc-h5-outsider', 'private',
    null, 1, array['trace-memory-research'], 'tc-h5-policy-v1',
    'synthetic-negative-control', 'fixture-v1', 'fixture-v1',
    'tc-h5-private-control', null, null,
    '{"negative_control": true}',
    '{"claim": "authorization negative control only"}',
    '{}',
    repeat('0', 64)
  );

-- No event row is needed: the candidate source points at the content-free
-- trajectory envelope, and source_event_sequence is deliberately null.
insert into trace_research.artifact_candidates (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, kind, lifecycle, generator_name,
  generator_revision, generator_config, seed, content_text, content_sha256,
  evidence_summary
) values (
  'tc-h5-candidate', 'tc-h5-tenant', 'tc-h5-source-owner', 'team',
  'tc-h5-team', 1, array['trace-memory-research'], 'tc-h5-policy-v1',
  'procedure', 'proposal', 'trace-commons-memory-h5-proposer',
  'deterministic-full-cohort-composition-preflight-v4',
  '{
    "dataset_revision": "112ebd4d03ce852b00e935d523107c3d0c9a65bf",
    "result_sha256": "3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5",
    "content_free": true
  }',
  20260730,
  'Require contextual identity and reject basename-only latest memory.',
  '3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5',
  '{
    "histories": 28,
    "unique_supported_revisions": 48,
    "contextual_placebo_leaks": 0,
    "latest_only_placebo_leaks": 3,
    "comparative_quality_claim_allowed": false
  }'
);

insert into trace_research.candidate_sources (
  id, candidate_id, source_trajectory_id, source_event_sequence, evidence_role
) values (
  'tc-h5-source-edge', 'tc-h5-candidate', 'tc-h5-source', null, 'support'
);

insert into trace_research.replay_manifests (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, split_name, task_family,
  task_manifest_sha256, environment_sha256, tool_schema_sha256,
  evaluator_revision, hidden_from_proposer, payload
) values
  (
    'tc-h5-manifest-evidence', 'tc-h5-candidate', 'tc-h5-tenant',
    'tc-h5-source-owner', 'team', 'tc-h5-team', 1,
    array['trace-memory-research'], 'tc-h5-policy-v1', 'evidence',
    'memory-lifecycle-mechanics', repeat('1', 64), repeat('2', 64),
    repeat('3', 64), 'tc-h5-evaluator-v1', false,
    '{"aggregate_only": true, "task_count": 2}'
  ),
  (
    'tc-h5-manifest-selection', 'tc-h5-candidate', 'tc-h5-tenant',
    'tc-h5-source-owner', 'team', 'tc-h5-team', 1,
    array['trace-memory-research'], 'tc-h5-policy-v1', 'selection',
    'memory-lifecycle-mechanics', repeat('4', 64), repeat('2', 64),
    repeat('3', 64), 'tc-h5-evaluator-v1', false,
    '{"aggregate_only": true, "task_count": 2}'
  ),
  (
    'tc-h5-manifest-test', 'tc-h5-candidate', 'tc-h5-tenant',
    'tc-h5-source-owner', 'team', 'tc-h5-team', 1,
    array['trace-memory-research'], 'tc-h5-policy-v1', 'test',
    'memory-lifecycle-mechanics', repeat('5', 64), repeat('2', 64),
    repeat('3', 64), 'tc-h5-evaluator-v1', true,
    '{"aggregate_only": true, "task_count": 2, "hidden": true}'
  );

set role trace_research_miner;
select set_config('app.tenant_id', '', true);
select set_config('app.subject_id', '', true);
select set_config('app.authorization_epoch', '', true);
select set_config('app.classification_ceiling', '', true);
select set_config('app.purpose', '', true);
select pg_temp.assert_count(
  'missing authority fails closed',
  (select count(*) from trace_research.artifact_candidates
   where id = 'tc-h5-candidate'),
  0
);

select set_config('app.tenant_id', 'tc-h5-other-tenant', true);
select set_config('app.subject_id', 'tc-h5-analyst', true);
select set_config('app.authorization_epoch', '41', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select pg_temp.assert_count(
  'wrong tenant fails closed',
  (select count(*) from trace_research.artifact_candidates
   where id = 'tc-h5-candidate'),
  0
);

select set_config('app.tenant_id', 'tc-h5-tenant', true);
select set_config('app.subject_id', 'tc-h5-outsider', true);
select pg_temp.assert_count(
  'non-member cannot see team candidate',
  (select count(*) from trace_research.artifact_candidates
   where id = 'tc-h5-candidate'),
  0
);

select set_config('app.subject_id', 'tc-h5-analyst', true);
select set_config('app.authorization_epoch', '40', true);
select pg_temp.assert_count(
  'stale epoch fails closed',
  (select count(*) from trace_research.artifact_candidates
   where id = 'tc-h5-candidate'),
  0
);

select set_config('app.authorization_epoch', '41', true);
select pg_temp.assert_count(
  'authorized team member sees the content-free candidate',
  (select count(*) from trace_research.artifact_candidates
   where id = 'tc-h5-candidate'),
  1
);
select pg_temp.assert_count(
  'miner sees evidence and selection manifests',
  (select count(*) from trace_research.replay_manifests
   where id like 'tc-h5-manifest-%'),
  2
);
select pg_temp.assert_count(
  'miner cannot see hidden tests',
  (select count(*) from trace_research.replay_manifests
   where id = 'tc-h5-manifest-test'),
  0
);
select pg_temp.assert_raises(
  'miner cannot read independent evaluation outcomes',
  'select count(*) from trace_research.evaluation_runs'
);
select pg_temp.assert_raises(
  'miner cannot forge a hidden test',
  $sql$
    insert into trace_research.replay_manifests (
      id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, policy_revision, split_name,
      task_family, task_manifest_sha256, environment_sha256,
      tool_schema_sha256, evaluator_revision, hidden_from_proposer, payload
    ) values (
      'tc-h5-forged-test', 'tc-h5-candidate', 'tc-h5-tenant',
      'tc-h5-source-owner', 'team', 'tc-h5-team', 1,
      array['trace-memory-research'], 'tc-h5-policy-v1', 'test',
      'memory-lifecycle-mechanics', repeat('9', 64), repeat('2', 64),
      repeat('3', 64), 'tc-h5-evaluator-v1', true, '{}'
    )
  $sql$
);

update trace_research.artifact_candidates
set lifecycle = 'selected'
where id = 'tc-h5-candidate';

set role trace_research_releaser;
select pg_temp.assert_raises(
  'release fails before independent selection and hidden-test outcomes',
  $sql$
    insert into trace_research.artifact_releases (
      id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, policy_revision, status,
      content_sha256, signature, approved_by
    ) values (
      'tc-h5-release-early', 'tc-h5-candidate', 'tc-h5-tenant',
      'tc-h5-source-owner', 'team', 'tc-h5-team', 1,
      array['trace-memory-research'], 'tc-h5-policy-v1', 'active',
      '3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5',
      'tc-h5-fixture-signature', 'tc-h5-independent-reviewer'
    )
  $sql$
);

set role trace_research_evaluator;
select pg_temp.assert_count(
  'evaluator sees the independently held hidden test',
  (select count(*) from trace_research.replay_manifests
   where id = 'tc-h5-manifest-test'),
  1
);
insert into trace_research.evaluation_runs (
  id, replay_manifest_id, candidate_id, evaluator_name, evaluator_revision,
  seed, passed, security_violation, outcome
) values
  (
    'tc-h5-eval-selection', 'tc-h5-manifest-selection',
    'tc-h5-candidate', 'tc-h5-fixture-evaluator', 'tc-h5-evaluator-v1',
    20260730, true, false,
    '{"aggregate_contract_passed": true, "raw_content_required": false}'
  ),
  (
    'tc-h5-eval-test', 'tc-h5-manifest-test',
    'tc-h5-candidate', 'tc-h5-fixture-evaluator', 'tc-h5-evaluator-v1',
    20260730, true, false,
    '{
      "contextual_controls_passed": true,
      "latest_only_context_isolation_failed": true,
      "candidate_rejects_latest_only": true,
      "raw_content_required": false
    }'
  );

set role trace_research_releaser;
insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status,
  content_sha256, signature, approved_by
) values (
  'tc-h5-release', 'tc-h5-candidate', 'tc-h5-tenant',
  'tc-h5-source-owner', 'team', 'tc-h5-team', 1,
  array['trace-memory-research'], 'tc-h5-policy-v1', 'active',
  '3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5',
  'tc-h5-fixture-signature', 'tc-h5-independent-reviewer'
);
insert into trace_research.release_events (
  release_id, sequence, event_kind, actor_id, reason
) values (
  'tc-h5-release', 0, 'published', 'tc-h5-independent-reviewer',
  'content-free selection and hidden-test gates passed'
);

set role trace_research_app;
select pg_temp.assert_count(
  'authorized runtime sees the active release',
  (select count(*) from trace_research.artifact_releases
   where id = 'tc-h5-release'),
  1
);
insert into trace_research.release_exposures (
  id, release_id, tenant_id, subject_id, team_id
) values (
  'tc-h5-exposure', 'tc-h5-release', 'tc-h5-tenant',
  'tc-h5-analyst', null
);
select pg_temp.assert_raises(
  'runtime cannot create an exposure for another subject',
  $sql$
    insert into trace_research.release_exposures (
      id, release_id, tenant_id, subject_id, team_id
    ) values (
      'tc-h5-exposure-outsider', 'tc-h5-release', 'tc-h5-tenant',
      'tc-h5-outsider', null
    )
  $sql$
);
insert into trace_research.trajectory_influences (
  trajectory_id, release_id, exposure_id, influence_kind
) values (
  'tc-h5-source', 'tc-h5-release', 'tc-h5-exposure', 'memory'
);
select pg_temp.assert_raises(
  'runtime cannot attach influence to an unauthorized trajectory',
  $sql$
    insert into trace_research.trajectory_influences (
      trajectory_id, release_id, exposure_id, influence_kind
    ) values (
      'tc-h5-private-control', 'tc-h5-release', 'tc-h5-exposure', 'memory'
    )
  $sql$
);
select pg_temp.assert_raises(
  'runtime cannot forge a release event',
  $sql$
    insert into trace_research.release_events (
      release_id, sequence, event_kind, actor_id, reason
    ) values (
      'tc-h5-release', 1, 'rolled_back', 'tc-h5-analyst', 'forged'
    )
  $sql$
);

set role trace_research_releaser;
update trace_research.artifact_releases
set status = 'rolled_back'
where id = 'tc-h5-release';
insert into trace_research.release_events (
  release_id, sequence, event_kind, actor_id, reason
) values (
  'tc-h5-release', 1, 'rolled_back', 'tc-h5-independent-reviewer',
  'H5 rollback visibility drill'
);

set role trace_research_app;
select pg_temp.assert_count(
  'rolled-back release disappears from runtime selection',
  (select count(*) from trace_research.artifact_releases
   where id = 'tc-h5-release'),
  0
);
select pg_temp.assert_count(
  'rolled-back release exposure disappears from runtime selection',
  (select count(*) from trace_research.release_exposures
   where id = 'tc-h5-exposure'),
  0
);

reset role;

-- Content-free contract: the trajectory envelope is metadata only, there are
-- no event rows, and the candidate carries a fixed label plus the corrected
-- internal result identity. The schema currently treats content_sha256 as an
-- artifact identity; it does not verify it against content_text.
select pg_temp.assert_count(
  'H5 trajectory raw payloads are empty objects',
  (
    select count(*)
    from trace_research.trajectories
    where id like 'tc-h5-%'
      and raw_payload <> '{}'::jsonb
  ),
  0
);
select pg_temp.assert_count(
  'H5 fixture stores no trace events or tool identifiers',
  (
    select count(*)
    from trace_research.events
    where trajectory_id like 'tc-h5-%'
  ),
  0
);
select pg_temp.assert_count(
  'H5 candidate has only the fixed content-free label',
  (
    select count(*)
    from trace_research.artifact_candidates
    where id = 'tc-h5-candidate'
      and content_text =
        'Require contextual identity and reject basename-only latest memory.'
      and content_sha256 =
        '3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5'
  ),
  1
);
select pg_temp.assert_count(
  'H5 outcome JSON uses only aggregate allowlisted keys',
  (
    select count(*)
    from trace_research.trajectories
    where id = 'tc-h5-source'
      and (
        outcome - array[
          'histories',
          'records',
          'native_calls',
          'native_results',
          'qualifying_interactions',
          'supported_observations',
          'unique_supported_revisions',
          'online_queries',
          'contextual_online_exact',
          'contextual_online_stale',
          'contextual_online_abstentions',
          'exact_cross_session_write_to_later_read',
          'same_basename_placebo_cases',
          'contextual_placebo_leaks',
          'latest_only_placebo_leaks',
          'future_positive_cases',
          'future_positive_detected',
          'future_filter_leaks',
          'all_negative_controls_passed',
          'comparative_quality_claim_allowed'
        ]::text[]
      ) <> '{}'::jsonb
  ),
  0
);
select pg_temp.assert_count(
  'candidate and release use the corrected internal result identity',
  (
    select count(*)
    from trace_research.artifact_candidates c
    join trace_research.artifact_releases r on r.candidate_id = c.id
    where c.id = 'tc-h5-candidate'
      and c.content_sha256 =
        '3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5'
      and r.content_sha256 = c.content_sha256
  ),
  1
);

select 'Trace Commons memory H5 PostgreSQL assertions passed' as result;
rollback;
