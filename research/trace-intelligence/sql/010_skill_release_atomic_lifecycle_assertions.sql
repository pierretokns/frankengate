\set ON_ERROR_STOP on

-- Rollback-only conformance for the 009 procedure contract. The fixture is
-- synthetic and content-free; no trace payloads or user content are stored.
begin;

insert into trace_research.authority_epochs (
  tenant_id, subject_id, authorization_epoch, classification_ceiling
) values ('tc-atomic-tenant', 'tc-atomic-actor', 7, 2);

insert into trace_research.artifact_candidates (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, kind, lifecycle, generator_name,
  generator_revision, generator_config, content_text, content_sha256,
  evidence_summary
) values (
  'tc-atomic-candidate', 'tc-atomic-tenant', 'tc-atomic-actor', 'private',
  null, 1, array['trace-memory-research'], 'tc-atomic-policy-v1', 'procedure',
  'selected', 'tc-atomic-fixture', 'v1', '{}',
  'content-free lifecycle fixture', repeat('a', 64), '{}'
);

insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status, content_sha256,
  signature, approved_by
) values (
  'tc-atomic-release', 'tc-atomic-candidate', 'tc-atomic-tenant',
  'tc-atomic-actor', 'private', null, 1,
  array['trace-memory-research'], 'tc-atomic-policy-v1', 'active',
  repeat('a', 64), 'tc-atomic-signature', 'tc-atomic-reviewer'
);

select set_config('app.tenant_id', 'tc-atomic-tenant', true);
select set_config('app.subject_id', 'tc-atomic-actor', true);
select set_config('app.authorization_epoch', '7', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);

set local role trace_research_app;
select trace_research.begin_release_exposure(
  'tc-atomic-exposure', 'tc-atomic-release', 'tc-atomic-tenant',
  'tc-atomic-actor', null
);

set local role trace_research_releaser;
select trace_research.transition_release(
  'tc-atomic-release', 'withdrawn', 'tc-atomic-reviewer',
  'tc-atomic lifecycle contract assertion'
);

reset role;

do $assert$
declare
  release_status text;
  exposure_status text;
  exposure_ended boolean;
  event_count bigint;
begin
  select status into release_status
    from trace_research.artifact_releases
   where id = 'tc-atomic-release';
  select status, ended_at is not null
    into exposure_status, exposure_ended
    from trace_research.release_exposures
   where id = 'tc-atomic-exposure';
  select count(*) into event_count
    from trace_research.release_events
   where release_id = 'tc-atomic-release'
     and event_kind = 'withdrawn';

  if release_status <> 'withdrawn'
     or exposure_status <> 'ended'
     or not exposure_ended
     or event_count <> 1 then
    raise exception
      'atomic lifecycle mismatch: release=%, exposure=%, ended=%, events=%',
      release_status, exposure_status, exposure_ended, event_count;
  end if;
end
$assert$;

-- A second exposure cannot pass the post-lock active check after withdrawal.
select set_config('app.tenant_id', 'tc-atomic-tenant', true);
select set_config('app.subject_id', 'tc-atomic-actor', true);
select set_config('app.authorization_epoch', '7', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'trace-memory-research', true);
set local role trace_research_app;
do $denial$
begin
  begin
    perform trace_research.begin_release_exposure(
      'tc-atomic-exposure-2', 'tc-atomic-release', 'tc-atomic-tenant',
      'tc-atomic-actor', null
    );
    raise exception 'withdrawn release accepted a new exposure';
  exception
    when others then
      if sqlerrm = 'withdrawn release accepted a new exposure' then
        raise;
      end if;
  end;
end
$denial$;
reset role;

select 'ATOMIC_LIFECYCLE_CONTRACT_OK';
rollback;
