\set ON_ERROR_STOP on

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

set role trace_research_app;

begin;
select set_config('app.tenant_id', 'tenant-a', true);
select set_config('app.subject_id', 'alice', true);
select set_config('app.authorization_epoch', '7', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'history', true);
select pg_temp.assert_count(
  'alice history',
  (select count(*) from trace_research.trajectories),
  3
);
select pg_temp.assert_count(
  'alice event search',
  (
    select count(*)
    from trace_research.events
    where content_tsv @@ websearch_to_tsquery('english', 'deployment timeout')
  ),
  3
);
select pg_temp.assert_count(
  'alice vector candidates',
  (
    select count(*)
    from (
      select id
      from trace_research.derived_artifacts
      order by embedding <=> '[1,0,0,0,0,0,0,0]'::public.vector
      limit 10
    ) authorized_candidates
  ),
  3
);
rollback;

begin;
select set_config('app.tenant_id', 'tenant-a', true);
select set_config('app.subject_id', 'bob', true);
select set_config('app.authorization_epoch', '11', true);
select set_config('app.classification_ceiling', '1', true);
select set_config('app.purpose', 'history', true);
select pg_temp.assert_count(
  'bob history',
  (select count(*) from trace_research.trajectories),
  2
);
select pg_temp.assert_count(
  'bob cannot see alice private in vector ranking',
  (
    select count(*)
    from trace_research.derived_artifacts
    where id = 'alice-private-signal'
  ),
  0
);
rollback;

begin;
select set_config('app.tenant_id', 'tenant-b', true);
select set_config('app.subject_id', 'eve', true);
select set_config('app.authorization_epoch', '3', true);
select set_config('app.classification_ceiling', '3', true);
select set_config('app.purpose', 'history', true);
select pg_temp.assert_count(
  'tenant isolation',
  (select count(*) from trace_research.trajectories),
  1
);
rollback;

begin;
select set_config('app.tenant_id', 'tenant-a', true);
select set_config('app.subject_id', 'alice', true);
select set_config('app.authorization_epoch', '6', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'history', true);
select pg_temp.assert_count(
  'stale epoch fails closed',
  (select count(*) from trace_research.trajectories),
  0
);
rollback;

begin;
select set_config('app.tenant_id', 'tenant-a', true);
select set_config('app.subject_id', 'alice', true);
select set_config('app.authorization_epoch', '7', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'unapproved-purpose', true);
select pg_temp.assert_count(
  'purpose mismatch fails closed',
  (select count(*) from trace_research.trajectories),
  0
);
rollback;

begin;
select set_config('app.tenant_id', 'tenant-a', true);
select set_config('app.subject_id', 'alice', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'history', true);
select pg_temp.assert_count(
  'missing epoch fails closed',
  (select count(*) from trace_research.trajectories),
  0
);
rollback;

reset role;

do $role_assertions$
declare
  unsafe_count bigint;
begin
  select count(*)
  into unsafe_count
  from pg_roles
  where rolname = 'trace_research_app'
    and (rolsuper or rolbypassrls or rolcreaterole or rolcreatedb);

  if unsafe_count <> 0 then
    raise exception 'trace_research_app has an unsafe role capability';
  end if;
end
$role_assertions$;

select 'trace research RLS assertions passed' as result;
