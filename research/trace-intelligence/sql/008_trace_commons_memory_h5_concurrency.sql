\set ON_ERROR_STOP on

-- Multi-session, content-free H5 concurrency conformance suite.
--
-- Run this file only through
-- tests/run_trace_commons_memory_h5_concurrency.py. The runner supplies one
-- `mode` per independent psql session, owns the advisory-lock barriers, checks
-- expected worker failures, and always invokes cleanup + zero-residue checks.
--
-- Every persisted fixture identity is prefixed tc-h5c-. No trace event,
-- prompt, response, path, tool identifier, or extracted memory text is stored.

select
  :'mode' = 'setup' as mode_setup,
  :'mode' = 'failed_job' as mode_failed_job,
  :'mode' = 'assert_failed_job' as mode_assert_failed_job,
  :'mode' = 'promote_a' as mode_promote_a,
  :'mode' = 'promote_b' as mode_promote_b,
  :'mode' = 'assert_promotion' as mode_assert_promotion,
  :'mode' = 'withdraw_a' as mode_withdraw_a,
  :'mode' = 'promote_c' as mode_promote_c,
  :'mode' = 'assert_withdraw_promote' as mode_assert_withdraw_promote,
  :'mode' = 'expose_c' as mode_expose_c,
  :'mode' = 'withdraw_c' as mode_withdraw_c,
  :'mode' = 'assert_withdraw_exposure' as mode_assert_withdraw_exposure,
  :'mode' = 'seed_release_d' as mode_seed_release_d,
  :'mode' = 'epoch_reader_rc' as mode_epoch_reader_rc,
  :'mode' = 'epoch_reader_rr' as mode_epoch_reader_rr,
  :'mode' = 'epoch_reader_rr_guarded' as mode_epoch_reader_rr_guarded,
  :'mode' = 'epoch_advance' as mode_epoch_advance,
  :'mode' = 'epoch_restore' as mode_epoch_restore,
  :'mode' = 'membership_reader_rc' as mode_membership_reader_rc,
  :'mode' = 'membership_reader_rr' as mode_membership_reader_rr,
  :'mode' = 'membership_revoke' as mode_membership_revoke,
  :'mode' = 'membership_restore' as mode_membership_restore,
  :'mode' = 'deletion_reader_rc' as mode_deletion_reader_rc,
  :'mode' = 'deletion_reader_rr' as mode_deletion_reader_rr,
  :'mode' = 'delete_target' as mode_delete_target,
  :'mode' = 'restore_delete_target' as mode_restore_delete_target,
  :'mode' = 'delete_provenance_source' as mode_delete_provenance_source,
  :'mode' = 'assert_provenance_source' as mode_assert_provenance_source,
  :'mode' = 'final_assertions' as mode_final_assertions,
  :'mode' = 'cleanup' as mode_cleanup,
  :'mode' = 'verify_zero' as mode_verify_zero
\gset

\if :mode_setup
begin;

do $assert_clean$
declare
  residue bigint;
begin
  select sum(n) into residue
  from (
    select count(*) n from trace_research.trajectory_influences
      where trajectory_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.release_events
      where release_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.release_exposures
      where id like 'tc-h5c-%' or release_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.artifact_releases
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.evaluation_runs
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.replay_manifests
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.candidate_sources
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.artifact_candidates
      where id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.events
      where trajectory_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.trajectories
      where id like 'tc-h5c-%' or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.team_memberships
      where tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.authority_epochs
      where tenant_id like 'tc-h5c-%'
  ) q;
  if residue <> 0 then
    raise exception 'tc-h5c setup refused: % fixture rows already exist', residue;
  end if;
end
$assert_clean$;

do $role$
begin
  if exists (
    select 1 from pg_roles
    where rolname = 'trace_research_h5c_governance'
  ) then
    raise exception 'tc-h5c setup refused: temporary governance role exists';
  end if;
  create role trace_research_h5c_governance
    nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
end
$role$;

grant usage on schema trace_research to trace_research_h5c_governance;

create function trace_research.h5c_set_authorization_epoch(
  fixture_tenant_id text,
  fixture_subject_id text,
  fixture_epoch bigint
) returns void
language plpgsql
security definer
set search_path = pg_catalog, trace_research
as $function$
begin
  if fixture_tenant_id !~ '^tc-h5c-'
     or fixture_subject_id !~ '^tc-h5c-'
     or fixture_epoch not in (51, 52) then
    raise exception 'H5C governance helper refuses non-fixture authority';
  end if;
  update trace_research.authority_epochs
  set authorization_epoch = fixture_epoch,
      updated_at = clock_timestamp()
  where tenant_id = fixture_tenant_id
    and subject_id = fixture_subject_id;
  if not found then
    raise exception 'H5C authority fixture not found';
  end if;
end
$function$;

create function trace_research.h5c_set_membership_active(
  fixture_tenant_id text,
  fixture_team_id text,
  fixture_subject_id text,
  fixture_active boolean
) returns void
language plpgsql
security definer
set search_path = pg_catalog, trace_research
as $function$
begin
  if fixture_tenant_id !~ '^tc-h5c-'
     or fixture_team_id !~ '^tc-h5c-'
     or fixture_subject_id !~ '^tc-h5c-' then
    raise exception 'H5C governance helper refuses non-fixture membership';
  end if;
  update trace_research.team_memberships
  set active = fixture_active,
      updated_at = clock_timestamp()
  where tenant_id = fixture_tenant_id
    and team_id = fixture_team_id
    and subject_id = fixture_subject_id;
  if not found then
    raise exception 'H5C membership fixture not found';
  end if;
end
$function$;

alter function trace_research.h5c_set_authorization_epoch(text, text, bigint)
  owner to trace_research_owner;
alter function trace_research.h5c_set_membership_active(
  text, text, text, boolean
) owner to trace_research_owner;
revoke all on function trace_research.h5c_set_authorization_epoch(
  text, text, bigint
) from public;
revoke all on function trace_research.h5c_set_membership_active(
  text, text, text, boolean
) from public;
grant execute on function trace_research.h5c_set_authorization_epoch(
  text, text, bigint
) to trace_research_h5c_governance;
grant execute on function trace_research.h5c_set_membership_active(
  text, text, text, boolean
) to trace_research_h5c_governance;

insert into trace_research.authority_epochs (
  tenant_id, subject_id, authorization_epoch, classification_ceiling
) values
  ('tc-h5c-tenant', 'tc-h5c-source-owner', 51, 2),
  ('tc-h5c-tenant', 'tc-h5c-analyst', 51, 2);

insert into trace_research.team_memberships (
  tenant_id, team_id, subject_id
) values (
  'tc-h5c-tenant', 'tc-h5c-team', 'tc-h5c-analyst'
);

insert into trace_research.trajectories (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, source_dataset, source_revision,
  adapter_revision, task_id, harness, model_name, outcome, loss_receipt,
  raw_payload, content_sha256
) values
  (
    'tc-h5c-source', 'tc-h5c-tenant', 'tc-h5c-source-owner', 'team',
    'tc-h5c-team', 1, array['trace-memory-research'],
    'tc-h5c-policy-v1', 'tc-h5c-content-free-fixture', 'tc-h5c-revision-v1',
    'tc-h5c-adapter-v1', 'tc-h5c-source-task', null, null,
    '{"fixture": true}', '{"content_free": true}', '{}', repeat('1', 64)
  ),
  (
    'tc-h5c-delete-target', 'tc-h5c-tenant', 'tc-h5c-source-owner', 'team',
    'tc-h5c-team', 1, array['trace-memory-research'],
    'tc-h5c-policy-v1', 'tc-h5c-content-free-fixture', 'tc-h5c-revision-v1',
    'tc-h5c-adapter-v1', 'tc-h5c-delete-task', null, null,
    '{"fixture": true}', '{"content_free": true}', '{}', repeat('2', 64)
  );

insert into trace_research.artifact_candidates (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, kind, lifecycle, generator_name,
  generator_revision, generator_config, seed, content_text, content_sha256,
  evidence_summary
) values (
  'tc-h5c-candidate', 'tc-h5c-tenant', 'tc-h5c-source-owner', 'team',
  'tc-h5c-team', 1, array['trace-memory-research'], 'tc-h5c-policy-v1',
  'procedure', 'selected', 'tc-h5c-content-free-proposer',
  'tc-h5c-revision-v1', '{"content_free": true}', 20260730,
  'H5C content-free lifecycle fixture.', repeat('3', 64),
  '{"content_free": true}'
);

insert into trace_research.candidate_sources (
  id, candidate_id, source_trajectory_id, source_event_sequence, evidence_role
) values (
  'tc-h5c-source-edge', 'tc-h5c-candidate', 'tc-h5c-source', null, 'support'
);

insert into trace_research.replay_manifests (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, split_name, task_family,
  task_manifest_sha256, environment_sha256, tool_schema_sha256,
  evaluator_revision, hidden_from_proposer, payload
) values
  (
    'tc-h5c-manifest-selection', 'tc-h5c-candidate', 'tc-h5c-tenant',
    'tc-h5c-source-owner', 'team', 'tc-h5c-team', 1,
    array['trace-memory-research'], 'tc-h5c-policy-v1', 'selection',
    'tc-h5c-lifecycle', repeat('4', 64), repeat('5', 64), repeat('6', 64),
    'tc-h5c-evaluator-v1', false, '{"content_free": true}'
  ),
  (
    'tc-h5c-manifest-test', 'tc-h5c-candidate', 'tc-h5c-tenant',
    'tc-h5c-source-owner', 'team', 'tc-h5c-team', 1,
    array['trace-memory-research'], 'tc-h5c-policy-v1', 'test',
    'tc-h5c-lifecycle', repeat('7', 64), repeat('5', 64), repeat('6', 64),
    'tc-h5c-evaluator-v1', true, '{"content_free": true}'
  );

insert into trace_research.evaluation_runs (
  id, replay_manifest_id, candidate_id, evaluator_name, evaluator_revision,
  seed, passed, security_violation, outcome
) values
  (
    'tc-h5c-eval-selection', 'tc-h5c-manifest-selection',
    'tc-h5c-candidate', 'tc-h5c-evaluator', 'tc-h5c-evaluator-v1',
    20260730, true, false, '{"content_free": true}'
  ),
  (
    'tc-h5c-eval-test', 'tc-h5c-manifest-test',
    'tc-h5c-candidate', 'tc-h5c-evaluator', 'tc-h5c-evaluator-v1',
    20260730, true, false, '{"content_free": true}'
  );

do $assert_roles$
declare
  unsafe bigint;
  owned bigint;
begin
  select count(*) into unsafe
  from pg_roles
  where rolname in (
    'trace_research_app',
    'trace_research_evaluator',
    'trace_research_miner',
    'trace_research_releaser',
    'trace_research_h5c_governance'
  )
    and (
      rolsuper or rolbypassrls or rolcreaterole or rolcreatedb or rolinherit
    );
  if unsafe <> 0 then
    raise exception 'H5C actor role safety failure: % unsafe roles', unsafe;
  end if;

  select count(*) into owned
  from pg_class c
  join pg_roles r on r.oid = c.relowner
  where r.rolname in (
    'trace_research_app',
    'trace_research_evaluator',
    'trace_research_miner',
    'trace_research_releaser',
    'trace_research_h5c_governance'
  );
  if owned <> 0 then
    raise exception 'H5C actor role owns % relations', owned;
  end if;
end
$assert_roles$;

commit;
select 'H5C_SETUP_OK';
\endif

\if :mode_failed_job
select set_config('application_name', 'tc-h5c-failed-job', false);
begin;
set role trace_research_evaluator;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.evaluation_runs (
  id, replay_manifest_id, candidate_id, evaluator_name, evaluator_revision,
  seed, passed, security_violation, outcome
) values (
  'tc-h5c-eval-job-selection', 'tc-h5c-manifest-selection',
  'tc-h5c-candidate', 'tc-h5c-failed-worker', 'tc-h5c-failed-job-v1',
  20260731, true, false, '{"stage": 1, "content_free": true}'
);
-- The second stage is deliberately invalid. ON_ERROR_STOP closes the worker
-- connection while the transaction is aborted, so stage one must roll back.
insert into trace_research.evaluation_runs (
  id, replay_manifest_id, candidate_id, evaluator_name, evaluator_revision,
  seed, passed, security_violation, outcome, cost_microunits
) values (
  'tc-h5c-eval-job-test', 'tc-h5c-manifest-test',
  'tc-h5c-candidate', 'tc-h5c-failed-worker', 'tc-h5c-failed-job-v1',
  20260731, true, false, '{"stage": 2, "content_free": true}', -1
);
commit;
\endif

\if :mode_assert_failed_job
do $assert$
begin
  if (
    select count(*) from trace_research.evaluation_runs
    where id like 'tc-h5c-eval-job-%'
  ) <> 0 then
    raise exception 'failed evaluator job leaked partial staging rows';
  end if;
end
$assert$;
select 'H5C_FAILED_JOB_ATOMIC_OK';
\endif

\if :mode_promote_a
select set_config('application_name', 'tc-h5c-promote-a', false);
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status, content_sha256,
  signature, approved_by
) values (
  'tc-h5c-release-a', 'tc-h5c-candidate', 'tc-h5c-tenant',
  'tc-h5c-source-owner', 'team', 'tc-h5c-team', 1,
  array['trace-memory-research'], 'tc-h5c-policy-v1', 'active',
  repeat('3', 64), 'tc-h5c-signature-a', 'tc-h5c-reviewer'
);
select pg_advisory_xact_lock(85001);
commit;
select 'H5C_PROMOTE_A_COMMITTED';
\endif

\if :mode_promote_b
select set_config('application_name', 'tc-h5c-promote-b', false);
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status, content_sha256,
  signature, approved_by
) values (
  'tc-h5c-release-b', 'tc-h5c-candidate', 'tc-h5c-tenant',
  'tc-h5c-source-owner', 'team', 'tc-h5c-team', 1,
  array['trace-memory-research'], 'tc-h5c-policy-v1', 'active',
  repeat('3', 64), 'tc-h5c-signature-b', 'tc-h5c-reviewer'
);
commit;
\endif

\if :mode_assert_promotion
do $assert$
begin
  if (
    select count(*) from trace_research.artifact_releases
    where candidate_id = 'tc-h5c-candidate' and status = 'active'
  ) <> 1 then
    raise exception 'promotion race did not leave exactly one active release';
  end if;
  if not exists (
    select 1 from trace_research.artifact_releases
    where id = 'tc-h5c-release-a' and status = 'active'
  ) then
    raise exception 'deterministic promotion winner was not release A';
  end if;
  if exists (
    select 1 from trace_research.artifact_releases
    where id = 'tc-h5c-release-b'
  ) then
    raise exception 'losing promotion transaction left a row';
  end if;
end
$assert$;
select 'H5C_PROMOTION_SERIALIZED_OK';
\endif

\if :mode_withdraw_a
select set_config('application_name', 'tc-h5c-withdraw-a', false);
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
update trace_research.artifact_releases
set status = 'withdrawn'
where id = 'tc-h5c-release-a';
insert into trace_research.release_events (
  release_id, sequence, event_kind, actor_id, reason
) values (
  'tc-h5c-release-a', 0, 'withdrawn', 'tc-h5c-reviewer',
  'tc-h5c deterministic withdrawal race'
);
select pg_advisory_xact_lock(85002);
commit;
select 'H5C_WITHDRAW_A_COMMITTED';
\endif

\if :mode_promote_c
select set_config('application_name', 'tc-h5c-promote-c', false);
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status, content_sha256,
  signature, approved_by
) values (
  'tc-h5c-release-c', 'tc-h5c-candidate', 'tc-h5c-tenant',
  'tc-h5c-source-owner', 'team', 'tc-h5c-team', 1,
  array['trace-memory-research'], 'tc-h5c-policy-v1', 'active',
  repeat('3', 64), 'tc-h5c-signature-c', 'tc-h5c-reviewer'
);
commit;
select 'H5C_PROMOTE_C_COMMITTED';
\endif

\if :mode_assert_withdraw_promote
do $assert$
begin
  if not exists (
    select 1 from trace_research.artifact_releases
    where id = 'tc-h5c-release-a' and status = 'withdrawn'
  ) then
    raise exception 'release A withdrawal did not commit';
  end if;
  if not exists (
    select 1 from trace_research.artifact_releases
    where id = 'tc-h5c-release-c' and status = 'active'
  ) then
    raise exception 'release C promotion did not serialize after withdrawal';
  end if;
  if (
    select count(*) from trace_research.artifact_releases
    where candidate_id = 'tc-h5c-candidate' and status = 'active'
  ) <> 1 then
    raise exception 'withdraw/promotion race violated one-active invariant';
  end if;
end
$assert$;
select 'H5C_WITHDRAW_PROMOTE_SERIALIZED_OK';
\endif

\if :mode_expose_c
select set_config('application_name', 'tc-h5c-expose-c', false);
begin;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.release_exposures (
  id, release_id, tenant_id, subject_id, team_id
) values (
  'tc-h5c-exposure-c', 'tc-h5c-release-c', 'tc-h5c-tenant',
  'tc-h5c-analyst', null
);
select pg_advisory_xact_lock(85003);
commit;
select 'H5C_EXPOSURE_C_COMMITTED';
\endif

\if :mode_withdraw_c
select set_config('application_name', 'tc-h5c-withdraw-c', false);
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
update trace_research.artifact_releases
set status = 'withdrawn'
where id = 'tc-h5c-release-c';
insert into trace_research.release_events (
  release_id, sequence, event_kind, actor_id, reason
) values (
  'tc-h5c-release-c', 0, 'withdrawn', 'tc-h5c-reviewer',
  'tc-h5c concurrent exposure withdrawal'
);
commit;
select 'H5C_WITHDRAW_C_COMMITTED';
\endif

\if :mode_assert_withdraw_exposure
do $assert$
declare
  runtime_visible bigint;
  orphan_active bigint;
begin
  set local role trace_research_app;
  perform set_config('app.tenant_id', 'tc-h5c-tenant', true);
  perform set_config('app.subject_id', 'tc-h5c-analyst', true);
  perform set_config('app.authorization_epoch', '51', true);
  perform set_config('app.classification_ceiling', '2', true);
  perform set_config('app.purpose', 'trace-memory-research', true);
  select count(*) into runtime_visible
  from trace_research.release_exposures
  where id = 'tc-h5c-exposure-c';
  reset role;
  select count(*) into orphan_active
  from trace_research.release_exposures x
  join trace_research.artifact_releases r on r.id = x.release_id
  where x.id = 'tc-h5c-exposure-c'
    and x.status = 'active'
    and r.status <> 'active';
  if runtime_visible <> 0 then
    raise exception 'withdrawn release exposure remained runtime-visible';
  end if;
  if orphan_active <> 1 then
    raise exception
      'expected known H5C lifecycle gap was not reproduced: got %', orphan_active;
  end if;
end
$assert$;
select 'H5C_WITHDRAW_EXPOSURE_HIDDEN_OK';
select 'H5C_KNOWN_GAP|active_exposure_metadata_survives_withdrawal';
\endif

\if :mode_seed_release_d
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status, content_sha256,
  signature, approved_by
) values (
  'tc-h5c-release-d', 'tc-h5c-candidate', 'tc-h5c-tenant',
  'tc-h5c-source-owner', 'team', 'tc-h5c-team', 1,
  array['trace-memory-research'], 'tc-h5c-policy-v1', 'active',
  repeat('3', 64), 'tc-h5c-signature-d', 'tc-h5c-reviewer'
);
commit;
select 'H5C_RELEASE_D_READY';
\endif

\if :mode_epoch_reader_rc
select set_config('application_name', 'tc-h5c-epoch-reader-rc', false);
begin isolation level read committed;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select 'H5C_BEFORE|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
select pg_advisory_xact_lock(85004);
select 'H5C_AFTER|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
rollback;
\endif

\if :mode_epoch_reader_rr
select set_config('application_name', 'tc-h5c-epoch-reader-rr', false);
begin isolation level repeatable read;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select 'H5C_BEFORE|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
select pg_advisory_xact_lock(85005);
select 'H5C_AFTER|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
rollback;
\endif

\if :mode_epoch_reader_rr_guarded
-- Governed semantic-cache/trace reads must fail closed if a caller attempts
-- REPEATABLE READ: the transaction snapshot can retain a revoked epoch.
begin isolation level repeatable read;
do $guard$
begin
  if current_setting('transaction_isolation') <> 'read committed' then
    raise exception 'governed queries require READ COMMITTED; repeatable read rejected';
  end if;
end
$guard$;
rollback;
\endif

\if :mode_epoch_advance
begin;
set role trace_research_h5c_governance;
select trace_research.h5c_set_authorization_epoch(
  'tc-h5c-tenant', 'tc-h5c-analyst', 52
);
commit;
select 'H5C_EPOCH_ADVANCED';
\endif

\if :mode_epoch_restore
begin;
set role trace_research_h5c_governance;
select trace_research.h5c_set_authorization_epoch(
  'tc-h5c-tenant', 'tc-h5c-analyst', 51
);
commit;
select 'H5C_EPOCH_RESTORED';
\endif

\if :mode_membership_reader_rc
select set_config('application_name', 'tc-h5c-membership-reader-rc', false);
begin isolation level read committed;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select 'H5C_BEFORE|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
select pg_advisory_xact_lock(85006);
select 'H5C_AFTER|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
rollback;
\endif

\if :mode_membership_reader_rr
select set_config('application_name', 'tc-h5c-membership-reader-rr', false);
begin isolation level repeatable read;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select 'H5C_BEFORE|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
select pg_advisory_xact_lock(85007);
select 'H5C_AFTER|' || count(*)
from trace_research.artifact_releases where id = 'tc-h5c-release-d';
rollback;
\endif

\if :mode_membership_revoke
begin;
set role trace_research_h5c_governance;
select trace_research.h5c_set_membership_active(
  'tc-h5c-tenant', 'tc-h5c-team', 'tc-h5c-analyst', false
);
commit;
select 'H5C_MEMBERSHIP_REVOKED';
\endif

\if :mode_membership_restore
begin;
set role trace_research_h5c_governance;
select trace_research.h5c_set_membership_active(
  'tc-h5c-tenant', 'tc-h5c-team', 'tc-h5c-analyst', true
);
commit;
select 'H5C_MEMBERSHIP_RESTORED';
\endif

\if :mode_deletion_reader_rc
select set_config('application_name', 'tc-h5c-deletion-reader-rc', false);
begin isolation level read committed;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select 'H5C_BEFORE|' || count(*)
from trace_research.trajectories where id = 'tc-h5c-delete-target';
select pg_advisory_xact_lock(85008);
select 'H5C_AFTER|' || count(*)
from trace_research.trajectories where id = 'tc-h5c-delete-target';
rollback;
\endif

\if :mode_deletion_reader_rr
select set_config('application_name', 'tc-h5c-deletion-reader-rr', false);
begin isolation level repeatable read;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select 'H5C_BEFORE|' || count(*)
from trace_research.trajectories where id = 'tc-h5c-delete-target';
select pg_advisory_xact_lock(85009);
select 'H5C_AFTER|' || count(*)
from trace_research.trajectories where id = 'tc-h5c-delete-target';
rollback;
\endif

\if :mode_delete_target
begin;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
delete from trace_research.trajectories where id = 'tc-h5c-delete-target';
commit;
select 'H5C_DELETE_TARGET_COMMITTED';
\endif

\if :mode_restore_delete_target
begin;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
insert into trace_research.trajectories (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, source_dataset, source_revision,
  adapter_revision, task_id, harness, model_name, outcome, loss_receipt,
  raw_payload, content_sha256
) values (
  'tc-h5c-delete-target', 'tc-h5c-tenant', 'tc-h5c-source-owner', 'team',
  'tc-h5c-team', 1, array['trace-memory-research'],
  'tc-h5c-policy-v1', 'tc-h5c-content-free-fixture', 'tc-h5c-revision-v1',
  'tc-h5c-adapter-v1', 'tc-h5c-delete-task', null, null,
  '{"fixture": true}', '{"content_free": true}', '{}', repeat('2', 64)
);
commit;
select 'H5C_DELETE_TARGET_RESTORED';
\endif

\if :mode_delete_provenance_source
begin;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-h5c-tenant', true);
select set_config('app.subject_id', 'tc-h5c-analyst', true);
select set_config('app.authorization_epoch', '51', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
delete from trace_research.trajectories where id = 'tc-h5c-source';
commit;
\endif

\if :mode_assert_provenance_source
do $assert$
begin
  if (
    select count(*) from trace_research.trajectories
    where id = 'tc-h5c-source'
  ) <> 1 then
    raise exception 'failed provenance deletion did not roll back';
  end if;
end
$assert$;
select 'H5C_PROVENANCE_DELETE_RESTRICTED_OK';
\endif

\if :mode_final_assertions
do $assert$
declare
  empty_payload_violations bigint;
  trace_events bigint;
  unsafe_roles bigint;
begin
  select count(*) into empty_payload_violations
  from trace_research.trajectories
  where id like 'tc-h5c-%' and raw_payload <> '{}'::jsonb;
  if empty_payload_violations <> 0 then
    raise exception 'H5C fixture stored non-empty raw payloads';
  end if;

  select count(*) into trace_events
  from trace_research.events where trajectory_id like 'tc-h5c-%';
  if trace_events <> 0 then
    raise exception 'H5C fixture stored trace events or tool identifiers';
  end if;

  select count(*) into unsafe_roles
  from pg_roles
  where rolname in (
    'trace_research_app',
    'trace_research_evaluator',
    'trace_research_releaser',
    'trace_research_h5c_governance'
  )
    and (rolsuper or rolbypassrls or rolinherit);
  if unsafe_roles <> 0 then
    raise exception 'H5C runtime actor gained unsafe role attributes';
  end if;
end
$assert$;
select 'H5C_FINAL_CONTENT_FREE_AND_ROLE_ASSERTIONS_OK';
\endif

\if :mode_cleanup
begin;
reset role;
delete from trace_research.trajectory_influences
where trajectory_id like 'tc-h5c-%' or release_id like 'tc-h5c-%';
delete from trace_research.release_events
where release_id like 'tc-h5c-%';
delete from trace_research.release_exposures
where id like 'tc-h5c-%' or release_id like 'tc-h5c-%'
   or tenant_id like 'tc-h5c-%';
delete from trace_research.artifact_releases
where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
   or tenant_id like 'tc-h5c-%';
delete from trace_research.evaluation_runs
where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%';
delete from trace_research.replay_manifests
where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
   or tenant_id like 'tc-h5c-%';
delete from trace_research.candidate_sources
where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
   or source_trajectory_id like 'tc-h5c-%';
delete from trace_research.artifact_candidates
where id like 'tc-h5c-%' or tenant_id like 'tc-h5c-%';
delete from trace_research.events where trajectory_id like 'tc-h5c-%';
delete from trace_research.derived_artifacts
where id like 'tc-h5c-%' or source_trajectory_id like 'tc-h5c-%'
   or tenant_id like 'tc-h5c-%';
delete from trace_research.trajectories
where id like 'tc-h5c-%' or tenant_id like 'tc-h5c-%';
delete from trace_research.team_memberships
where tenant_id like 'tc-h5c-%' or team_id like 'tc-h5c-%'
   or subject_id like 'tc-h5c-%';
delete from trace_research.authority_epochs
where tenant_id like 'tc-h5c-%' or subject_id like 'tc-h5c-%';
commit;

drop function if exists trace_research.h5c_set_authorization_epoch(
  text, text, bigint
);
drop function if exists trace_research.h5c_set_membership_active(
  text, text, text, boolean
);
do $role$
begin
  if exists (
    select 1 from pg_roles
    where rolname = 'trace_research_h5c_governance'
  ) then
    revoke usage on schema trace_research
      from trace_research_h5c_governance;
    drop role trace_research_h5c_governance;
  end if;
end
$role$;
select 'H5C_CLEANUP_OK';
\endif

\if :mode_verify_zero
do $verify$
declare
  residue bigint;
  helpers bigint;
  roles bigint;
begin
  select sum(n) into residue
  from (
    select count(*) n from trace_research.trajectory_influences
      where trajectory_id like 'tc-h5c-%' or release_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.release_events
      where release_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.release_exposures
      where id like 'tc-h5c-%' or release_id like 'tc-h5c-%'
        or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.artifact_releases
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
        or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.evaluation_runs
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.replay_manifests
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
        or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.candidate_sources
      where id like 'tc-h5c-%' or candidate_id like 'tc-h5c-%'
        or source_trajectory_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.artifact_candidates
      where id like 'tc-h5c-%' or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.events
      where trajectory_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.derived_artifacts
      where id like 'tc-h5c-%' or source_trajectory_id like 'tc-h5c-%'
        or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.trajectories
      where id like 'tc-h5c-%' or tenant_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.team_memberships
      where tenant_id like 'tc-h5c-%' or team_id like 'tc-h5c-%'
        or subject_id like 'tc-h5c-%'
    union all
    select count(*) from trace_research.authority_epochs
      where tenant_id like 'tc-h5c-%' or subject_id like 'tc-h5c-%'
  ) q;
  select count(*) into helpers
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'trace_research' and p.proname like 'h5c_%';
  select count(*) into roles
  from pg_roles where rolname = 'trace_research_h5c_governance';

  if residue <> 0 or helpers <> 0 or roles <> 0 then
    raise exception
      'H5C zero-residue failure: rows %, helpers %, roles %',
      residue, helpers, roles;
  end if;
end
$verify$;
select 'H5C_ZERO_RESIDUE_OK';
\endif
