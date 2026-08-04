-- Atomic lifecycle procedures for the disposable governed release schema.
--
-- H5 found that direct table writes can leave an active exposure attached to a
-- withdrawn release and can record a status transition without its event. The
-- procedures below are the narrow research contract: exposure creation and
-- release transition serialize on the release row, re-check authority after
-- locking, and couple status/exposure/event writes in one transaction.
--
-- This is research-only PostgreSQL SQL. It does not claim Aurora failover or
-- RDS Proxy behavior.

create or replace function trace_research.begin_release_exposure(
  p_exposure_id text,
  p_release_id text,
  p_tenant_id text,
  p_subject_id text,
  p_team_id text
) returns void
language plpgsql
security definer
set search_path = pg_catalog, trace_research
as $function$
declare
  release_row trace_research.artifact_releases%rowtype;
  actor_tenant text := nullif(current_setting('app.tenant_id', true), '');
  actor_subject text := nullif(current_setting('app.subject_id', true), '');
begin
  if p_tenant_id is distinct from actor_tenant then
    raise exception 'release exposure tenant does not match caller scope';
  end if;
  if (p_subject_id is null) = (p_team_id is null) then
    raise exception 'release exposure requires exactly one subject or team';
  end if;

  -- The same row lock is taken by withdraw_release. The status check therefore
  -- happens after any concurrent withdrawal commits, not before it.
  select *
    into release_row
    from trace_research.artifact_releases
   where id = p_release_id
   for update;

  if not found then
    raise exception 'release % does not exist', p_release_id;
  end if;
  if release_row.status <> 'active' then
    raise exception 'release % is not active', p_release_id;
  end if;
  if release_row.tenant_id is distinct from p_tenant_id then
    raise exception 'release % belongs to another tenant', p_release_id;
  end if;
  if not trace_research.current_scope_authorized(
    release_row.tenant_id,
    release_row.owner_subject_id,
    release_row.audience,
    release_row.team_id,
    release_row.classification,
    release_row.allowed_purposes
  ) then
    raise exception 'release % is outside the caller authorization scope', p_release_id;
  end if;
  if p_subject_id is not null and p_subject_id is distinct from actor_subject then
    raise exception 'subject exposure does not match caller subject';
  end if;
  if p_team_id is not null
     and not trace_research.current_team_member(p_tenant_id, p_team_id) then
    raise exception 'caller is not a member of exposure team';
  end if;

  insert into trace_research.release_exposures (
    id, release_id, tenant_id, subject_id, team_id, status
  ) values (
    p_exposure_id, p_release_id, p_tenant_id, p_subject_id, p_team_id, 'active'
  );
end
$function$;

create or replace function trace_research.transition_release(
  p_release_id text,
  p_event_kind text,
  p_actor_id text,
  p_reason text
) returns text
language plpgsql
security definer
set search_path = pg_catalog, trace_research
as $function$
declare
  release_row trace_research.artifact_releases%rowtype;
  next_status text;
  exposure_status text;
  event_sequence integer;
  ended_at_value timestamptz := clock_timestamp();
begin
  if p_event_kind not in ('withdrawn', 'rolled_back') then
    raise exception 'unsupported release transition %', p_event_kind;
  end if;
  if nullif(p_actor_id, '') is null or nullif(p_reason, '') is null then
    raise exception 'release transition requires actor and reason';
  end if;

  -- This is the same lock used by begin_release_exposure, so no exposure can
  -- commit after this transition while still observing the old active state.
  select *
    into release_row
    from trace_research.artifact_releases
   where id = p_release_id
   for update;

  if not found then
    raise exception 'release % does not exist', p_release_id;
  end if;
  if release_row.status <> 'active' then
    raise exception 'release % is not active', p_release_id;
  end if;
  if not trace_research.current_scope_authorized(
    release_row.tenant_id,
    release_row.owner_subject_id,
    release_row.audience,
    release_row.team_id,
    release_row.classification,
    release_row.allowed_purposes
  ) then
    raise exception 'release % is outside the caller authorization scope', p_release_id;
  end if;

  next_status := p_event_kind;
  exposure_status := case p_event_kind
    when 'rolled_back' then 'rolled_back'
    else 'ended'
  end;

  update trace_research.artifact_releases
     set status = next_status
   where id = p_release_id;

  update trace_research.release_exposures
     set status = exposure_status,
         ended_at = coalesce(ended_at, ended_at_value)
   where release_id = p_release_id
     and status = 'active';

  select coalesce(max(sequence), -1) + 1
    into event_sequence
    from trace_research.release_events
   where release_id = p_release_id;

  insert into trace_research.release_events (
    release_id, sequence, event_kind, actor_id, reason, created_at
  ) values (
    p_release_id, event_sequence, p_event_kind, p_actor_id, p_reason,
    ended_at_value
  );

  return next_status;
end
$function$;

alter function trace_research.begin_release_exposure(text, text, text, text, text)
  owner to trace_research_owner;
alter function trace_research.transition_release(text, text, text, text)
  owner to trace_research_owner;
revoke all on function trace_research.begin_release_exposure(text, text, text, text, text)
  from public;
revoke all on function trace_research.transition_release(text, text, text, text)
  from public;
grant execute on function trace_research.begin_release_exposure(text, text, text, text, text)
  to trace_research_app, trace_research_releaser;
grant execute on function trace_research.transition_release(text, text, text, text)
  to trace_research_releaser;

comment on function trace_research.begin_release_exposure(text, text, text, text, text) is
  'Lock and re-check an active release before creating an exposure; research lifecycle contract.';
comment on function trace_research.transition_release(text, text, text, text) is
  'Atomically transition a release, end active exposures, and append its lifecycle event.';
