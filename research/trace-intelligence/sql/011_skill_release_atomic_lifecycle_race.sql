\set ON_ERROR_STOP on

-- Two-session race for the 009 lifecycle contract. The runner owns advisory
-- barriers; every persisted fixture is synthetic and content-free.
select
  :'mode' = 'setup' as mode_setup,
  :'mode' = 'expose_hold' as mode_expose_hold,
  :'mode' = 'withdraw' as mode_withdraw,
  :'mode' = 'assert' as mode_assert,
  :'mode' = 'cleanup' as mode_cleanup,
  :'mode' = 'verify_zero' as mode_verify_zero
\gset

\if :mode_setup
begin;
insert into trace_research.authority_epochs (
  tenant_id, subject_id, authorization_epoch, classification_ceiling
) values ('tc-atomicc-tenant', 'tc-atomicc-actor', 9, 2);
insert into trace_research.artifact_candidates (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, kind, lifecycle, generator_name,
  generator_revision, generator_config, content_text, content_sha256,
  evidence_summary
) values (
  'tc-atomicc-candidate', 'tc-atomicc-tenant', 'tc-atomicc-actor', 'private',
  null, 1, array['trace-memory-research'], 'tc-atomicc-policy-v1', 'procedure',
  'selected', 'tc-atomicc-fixture', 'v1', '{}',
  'content-free race fixture', repeat('b', 64), '{}'
);
insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status, content_sha256,
  signature, approved_by
) values (
  'tc-atomicc-release', 'tc-atomicc-candidate', 'tc-atomicc-tenant',
  'tc-atomicc-actor', 'private', null, 1,
  array['trace-memory-research'], 'tc-atomicc-policy-v1', 'active',
  repeat('b', 64), 'tc-atomicc-signature', 'tc-atomicc-reviewer'
);
commit;
select 'ATOMICC_SETUP_OK';
\endif

\if :mode_expose_hold
select set_config('application_name', 'tc-atomicc-expose', false);
begin;
set role trace_research_app;
select set_config('app.tenant_id', 'tc-atomicc-tenant', true);
select set_config('app.subject_id', 'tc-atomicc-actor', true);
select set_config('app.authorization_epoch', '9', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select trace_research.begin_release_exposure(
  'tc-atomicc-exposure', 'tc-atomicc-release', 'tc-atomicc-tenant',
  'tc-atomicc-actor', null
);
-- The controller holds this advisory lock. The worker remains in this
-- transaction with the release row lock until the controller releases it.
select pg_advisory_xact_lock(85101);
commit;
select 'ATOMICC_EXPOSE_COMMITTED';
\endif

\if :mode_withdraw
select set_config('application_name', 'tc-atomicc-withdraw', false);
begin;
set role trace_research_releaser;
select set_config('app.tenant_id', 'tc-atomicc-tenant', true);
select set_config('app.subject_id', 'tc-atomicc-actor', true);
select set_config('app.authorization_epoch', '9', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
select trace_research.transition_release(
  'tc-atomicc-release', 'withdrawn', 'tc-atomicc-reviewer',
  'tc-atomicc concurrent withdrawal'
);
commit;
select 'ATOMICC_WITHDRAW_COMMITTED';
\endif

\if :mode_assert
do $assert$
declare
  release_status text;
  exposure_status text;
  ended boolean;
  event_count bigint;
begin
  select status into release_status
    from trace_research.artifact_releases
   where id = 'tc-atomicc-release';
  select status, ended_at is not null into exposure_status, ended
    from trace_research.release_exposures
   where id = 'tc-atomicc-exposure';
  select count(*) into event_count
    from trace_research.release_events
   where release_id = 'tc-atomicc-release';
  if release_status <> 'withdrawn'
     or exposure_status <> 'ended'
     or not ended
     or event_count <> 1 then
    raise exception
      'race contract mismatch: release=%, exposure=%, ended=%, events=%',
      release_status, exposure_status, ended, event_count;
  end if;
end
$assert$;
select 'ATOMICC_RACE_CONTRACT_OK';
\endif

\if :mode_cleanup
begin;
delete from trace_research.release_events where release_id like 'tc-atomicc-%';
delete from trace_research.release_exposures where id like 'tc-atomicc-%';
delete from trace_research.artifact_releases where id like 'tc-atomicc-%';
delete from trace_research.artifact_candidates where id like 'tc-atomicc-%';
delete from trace_research.authority_epochs where tenant_id like 'tc-atomicc-%';
commit;
select 'ATOMICC_CLEANUP_OK';
\endif

\if :mode_verify_zero
select case when (
  select sum(n) from (
    select count(*) n from trace_research.release_events where release_id like 'tc-atomicc-%'
    union all
    select count(*) from trace_research.release_exposures where id like 'tc-atomicc-%'
    union all
    select count(*) from trace_research.artifact_releases where id like 'tc-atomicc-%'
    union all
    select count(*) from trace_research.artifact_candidates where id like 'tc-atomicc-%'
    union all
    select count(*) from trace_research.authority_epochs where tenant_id like 'tc-atomicc-%'
  ) counts
) = 0 then 'ATOMICC_ZERO_RESIDUE_OK' else 'ATOMICC_RESIDUE_PRESENT' end;
\endif
