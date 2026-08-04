-- Governed candidate -> replay -> evaluation -> release lifecycle.
--
-- Research-only Aurora-compatible PostgreSQL schema. This migration adds the
-- first-class records missing from 001 without turning Markdown projections
-- into an authority boundary.

do $roles$
begin
  if not exists (select 1 from pg_roles where rolname = 'trace_research_miner') then
    create role trace_research_miner
      nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'trace_research_evaluator') then
    create role trace_research_evaluator
      nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'trace_research_releaser') then
    create role trace_research_releaser
      nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end
$roles$;

grant usage on schema trace_research
  to trace_research_miner, trace_research_evaluator, trace_research_releaser;

create table if not exists trace_research.artifact_candidates (
  id text primary key,
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience in ('private', 'team')),
  team_id text,
  classification smallint not null check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  kind text not null check (kind in ('memory', 'procedure', 'eval')),
  lifecycle text not null default 'proposal'
    check (lifecycle in ('proposal', 'rejected', 'selected', 'withdrawn')),
  parent_candidate_id text
    references trace_research.artifact_candidates(id),
  generator_name text not null,
  generator_revision text not null,
  generator_config jsonb not null,
  seed bigint,
  content_text text not null,
  content_sha256 text not null check (content_sha256 ~ '^[a-f0-9]{64}$'),
  evidence_summary jsonb not null,
  created_at timestamptz not null default now(),
  check (
    (audience = 'private' and team_id is null)
    or (audience = 'team' and team_id is not null)
  )
);

-- Owner-only provenance edges. Callers discover evidence through authorized
-- candidates; raw source IDs are not directly granted to runtime roles.
create table if not exists trace_research.candidate_sources (
  id text primary key,
  candidate_id text not null
    references trace_research.artifact_candidates(id) on delete cascade,
  source_trajectory_id text not null
    references trace_research.trajectories(id),
  source_event_sequence integer,
  evidence_role text not null
    check (evidence_role in ('support', 'counterexample', 'conflict')),
  unique nulls not distinct (
    candidate_id,
    source_trajectory_id,
    source_event_sequence,
    evidence_role
  ),
  foreign key (source_trajectory_id, source_event_sequence)
    references trace_research.events(trajectory_id, sequence)
);

create table if not exists trace_research.replay_manifests (
  id text primary key,
  candidate_id text
    references trace_research.artifact_candidates(id),
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience in ('private', 'team')),
  team_id text,
  classification smallint not null check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  split_name text not null check (split_name in ('evidence', 'selection', 'test')),
  task_family text not null,
  task_manifest_sha256 text not null check (task_manifest_sha256 ~ '^[a-f0-9]{64}$'),
  environment_sha256 text not null check (environment_sha256 ~ '^[a-f0-9]{64}$'),
  tool_schema_sha256 text not null check (tool_schema_sha256 ~ '^[a-f0-9]{64}$'),
  evaluator_revision text not null,
  hidden_from_proposer boolean not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (split_name <> 'test' or hidden_from_proposer),
  check (
    (audience = 'private' and team_id is null)
    or (audience = 'team' and team_id is not null)
  )
);

create table if not exists trace_research.evaluation_runs (
  id text primary key,
  replay_manifest_id text not null
    references trace_research.replay_manifests(id),
  candidate_id text
    references trace_research.artifact_candidates(id),
  evaluator_name text not null,
  evaluator_revision text not null,
  model_name text,
  seed bigint,
  passed boolean not null,
  security_violation boolean not null default false,
  outcome jsonb not null,
  latency_ms bigint check (latency_ms is null or latency_ms >= 0),
  cost_microunits bigint check (cost_microunits is null or cost_microunits >= 0),
  created_at timestamptz not null default now(),
  unique (replay_manifest_id, candidate_id, evaluator_revision, seed)
);

create table if not exists trace_research.artifact_releases (
  id text primary key,
  candidate_id text not null
    references trace_research.artifact_candidates(id),
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience in ('private', 'team')),
  team_id text,
  classification smallint not null check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  status text not null default 'active'
    check (status in ('active', 'withdrawn', 'rolled_back')),
  prior_release_id text
    references trace_research.artifact_releases(id),
  content_sha256 text not null check (content_sha256 ~ '^[a-f0-9]{64}$'),
  signature text not null,
  approved_by text not null,
  approved_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  check (
    (audience = 'private' and team_id is null)
    or (audience = 'team' and team_id is not null)
  )
);

create table if not exists trace_research.release_exposures (
  id text primary key,
  release_id text not null
    references trace_research.artifact_releases(id),
  tenant_id text not null,
  subject_id text,
  team_id text,
  status text not null default 'active'
    check (status in ('active', 'ended', 'rolled_back')),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  check ((subject_id is null) <> (team_id is null)),
  check (ended_at is null or ended_at >= started_at)
);

create table if not exists trace_research.trajectory_influences (
  trajectory_id text not null
    references trace_research.trajectories(id) on delete cascade,
  release_id text not null
    references trace_research.artifact_releases(id),
  exposure_id text
    references trace_research.release_exposures(id),
  influence_kind text not null
    check (influence_kind in ('prompt', 'skill', 'memory', 'retrieval')),
  observed_at timestamptz not null default now(),
  primary key (trajectory_id, release_id, influence_kind)
);

create table if not exists trace_research.release_events (
  release_id text not null
    references trace_research.artifact_releases(id),
  sequence integer not null check (sequence >= 0),
  event_kind text not null
    check (event_kind in ('published', 'withdrawn', 'rolled_back')),
  actor_id text not null,
  reason text not null,
  rollback_target_release_id text
    references trace_research.artifact_releases(id),
  created_at timestamptz not null default now(),
  primary key (release_id, sequence)
);

alter table trace_research.artifact_candidates owner to trace_research_owner;
alter table trace_research.candidate_sources owner to trace_research_owner;
alter table trace_research.replay_manifests owner to trace_research_owner;
alter table trace_research.evaluation_runs owner to trace_research_owner;
alter table trace_research.artifact_releases owner to trace_research_owner;
alter table trace_research.release_exposures owner to trace_research_owner;
alter table trace_research.trajectory_influences owner to trace_research_owner;
alter table trace_research.release_events owner to trace_research_owner;

create index if not exists artifact_candidates_scope_idx
  on trace_research.artifact_candidates
  (tenant_id, owner_subject_id, lifecycle, kind, created_at);
create index if not exists candidate_sources_trajectory_idx
  on trace_research.candidate_sources (source_trajectory_id, candidate_id);
create index if not exists replay_manifests_split_idx
  on trace_research.replay_manifests (split_name, task_family, candidate_id);
create index if not exists evaluation_runs_candidate_idx
  on trace_research.evaluation_runs
  (candidate_id, passed, security_violation, created_at);
create unique index if not exists artifact_releases_one_active_candidate_idx
  on trace_research.artifact_releases (candidate_id)
  where status = 'active';
create index if not exists release_exposures_scope_idx
  on trace_research.release_exposures
  (tenant_id, subject_id, team_id, status);
create index if not exists trajectory_influences_release_idx
  on trace_research.trajectory_influences (release_id, trajectory_id);

create or replace function trace_research.current_scope_authorized(
  row_tenant_id text,
  row_owner_subject_id text,
  row_audience text,
  row_team_id text,
  row_classification smallint,
  row_allowed_purposes text[]
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select
    row_tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and trace_research.current_authority_valid(
      row_tenant_id,
      row_owner_subject_id
    )
    and row_classification <=
      nullif(current_setting('app.classification_ceiling', true), '')::smallint
    and nullif(current_setting('app.purpose', true), '') =
      any (row_allowed_purposes)
    and (
      (
        row_audience = 'private'
        and row_owner_subject_id =
          nullif(current_setting('app.subject_id', true), '')
      )
      or (
        row_audience = 'team'
        and trace_research.current_team_member(row_tenant_id, row_team_id)
      )
    )
$function$;

-- The nologin owner is trusted only inside security-definer checks. It is not
-- granted to any runtime role. FORCE RLS remains active for runtime callers.
drop policy if exists trajectories_owner_internal
  on trace_research.trajectories;
create policy trajectories_owner_internal on trace_research.trajectories
  for select to trace_research_owner using (true);

create or replace function trace_research.candidate_sources_authorized(
  row_candidate_id text
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select
    exists (
      select 1
      from trace_research.candidate_sources cs
      where cs.candidate_id = row_candidate_id
    )
    and not exists (
      select 1
      from trace_research.candidate_sources cs
      join trace_research.trajectories t
        on t.id = cs.source_trajectory_id
      where cs.candidate_id = row_candidate_id
        and not trace_research.current_scope_authorized(
          t.tenant_id,
          t.owner_subject_id,
          t.audience,
          t.team_id,
          t.classification,
          t.allowed_purposes
        )
    )
$function$;

alter function trace_research.current_scope_authorized(
  text, text, text, text, smallint, text[]
) owner to trace_research_owner;
alter function trace_research.candidate_sources_authorized(text)
  owner to trace_research_owner;
revoke all on function trace_research.current_scope_authorized(
  text, text, text, text, smallint, text[]
) from public;
revoke all on function trace_research.candidate_sources_authorized(text)
  from public;
grant execute on function trace_research.current_scope_authorized(
  text, text, text, text, smallint, text[]
) to trace_research_miner, trace_research_evaluator,
  trace_research_releaser, trace_research_app;
grant execute on function trace_research.candidate_sources_authorized(text)
  to trace_research_miner, trace_research_evaluator,
  trace_research_releaser, trace_research_app;

grant select on trace_research.artifact_candidates
  to trace_research_miner, trace_research_evaluator,
    trace_research_releaser, trace_research_app;
grant insert on trace_research.artifact_candidates to trace_research_miner;
revoke update on trace_research.artifact_candidates
  from trace_research_miner;
grant update (lifecycle) on trace_research.artifact_candidates
  to trace_research_miner;

grant select on trace_research.replay_manifests
  to trace_research_miner, trace_research_evaluator, trace_research_releaser;
grant insert on trace_research.replay_manifests to trace_research_miner;

grant select, insert on trace_research.evaluation_runs
  to trace_research_evaluator;
grant select on trace_research.evaluation_runs to trace_research_releaser;

grant select on trace_research.artifact_releases
  to trace_research_miner, trace_research_evaluator,
    trace_research_releaser, trace_research_app;
grant insert on trace_research.artifact_releases to trace_research_releaser;
revoke update on trace_research.artifact_releases
  from trace_research_releaser;
grant update (status) on trace_research.artifact_releases
  to trace_research_releaser;

grant select, insert on trace_research.release_exposures
  to trace_research_releaser, trace_research_app;
revoke update on trace_research.release_exposures
  from trace_research_releaser, trace_research_app;
grant update (status, ended_at) on trace_research.release_exposures
  to trace_research_releaser, trace_research_app;
grant select, insert on trace_research.trajectory_influences
  to trace_research_app;
grant select on trace_research.release_events
  to trace_research_releaser, trace_research_app;
grant insert on trace_research.release_events to trace_research_releaser;

alter table trace_research.artifact_candidates enable row level security;
alter table trace_research.artifact_candidates force row level security;
alter table trace_research.replay_manifests enable row level security;
alter table trace_research.replay_manifests force row level security;
alter table trace_research.evaluation_runs enable row level security;
alter table trace_research.evaluation_runs force row level security;
alter table trace_research.artifact_releases enable row level security;
alter table trace_research.artifact_releases force row level security;
alter table trace_research.release_exposures enable row level security;
alter table trace_research.release_exposures force row level security;
alter table trace_research.trajectory_influences enable row level security;
alter table trace_research.trajectory_influences force row level security;
alter table trace_research.release_events enable row level security;
alter table trace_research.release_events force row level security;

drop policy if exists artifact_candidates_owner_internal
  on trace_research.artifact_candidates;
create policy artifact_candidates_owner_internal
  on trace_research.artifact_candidates
  for all to trace_research_owner using (true) with check (true);
drop policy if exists artifact_candidates_read
  on trace_research.artifact_candidates;
create policy artifact_candidates_read on trace_research.artifact_candidates
  for select to trace_research_miner, trace_research_evaluator,
    trace_research_releaser, trace_research_app
  using (
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and trace_research.candidate_sources_authorized(id)
  );
drop policy if exists artifact_candidates_mine
  on trace_research.artifact_candidates;
create policy artifact_candidates_mine on trace_research.artifact_candidates
  for all to trace_research_miner
  using (
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and trace_research.candidate_sources_authorized(id)
  )
  with check (
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
  );

create or replace function trace_research.candidate_scope_matches(
  row_candidate_id text,
  row_tenant_id text,
  row_owner_subject_id text,
  row_audience text,
  row_team_id text,
  row_classification smallint,
  row_allowed_purposes text[]
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select
    row_candidate_id is null
    or exists (
      select 1
      from trace_research.artifact_candidates c
      where c.id = row_candidate_id
        and c.tenant_id = row_tenant_id
        and c.owner_subject_id = row_owner_subject_id
        and c.audience = row_audience
        and c.team_id is not distinct from row_team_id
        and c.classification = row_classification
        and c.allowed_purposes = row_allowed_purposes
        and trace_research.candidate_sources_authorized(c.id)
    )
$function$;

alter function trace_research.candidate_scope_matches(
  text, text, text, text, text, smallint, text[]
) owner to trace_research_owner;
revoke all on function trace_research.candidate_scope_matches(
  text, text, text, text, text, smallint, text[]
) from public;
grant execute on function trace_research.candidate_scope_matches(
  text, text, text, text, text, smallint, text[]
) to trace_research_miner, trace_research_evaluator,
  trace_research_releaser;

drop policy if exists replay_manifests_owner_internal
  on trace_research.replay_manifests;
create policy replay_manifests_owner_internal on trace_research.replay_manifests
  for all to trace_research_owner using (true) with check (true);
drop policy if exists replay_manifests_proposer_read
  on trace_research.replay_manifests;
create policy replay_manifests_proposer_read on trace_research.replay_manifests
  for select to trace_research_miner
  using (
    split_name <> 'test'
    and trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and trace_research.candidate_scope_matches(
      candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
  );
drop policy if exists replay_manifests_proposer_write
  on trace_research.replay_manifests;
create policy replay_manifests_proposer_write on trace_research.replay_manifests
  for insert to trace_research_miner
  with check (
    split_name in ('evidence', 'selection')
    and not hidden_from_proposer
    and trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and trace_research.candidate_scope_matches(
      candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
  );
drop policy if exists replay_manifests_independent_read
  on trace_research.replay_manifests;
create policy replay_manifests_independent_read on trace_research.replay_manifests
  for select to trace_research_evaluator, trace_research_releaser
  using (
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and trace_research.candidate_scope_matches(
      candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
  );

drop policy if exists evaluation_runs_owner_internal
  on trace_research.evaluation_runs;
create policy evaluation_runs_owner_internal on trace_research.evaluation_runs
  for all to trace_research_owner using (true) with check (true);
drop policy if exists evaluation_runs_independent
  on trace_research.evaluation_runs;
create policy evaluation_runs_independent on trace_research.evaluation_runs
  for all to trace_research_evaluator
  using (
    exists (
      select 1 from trace_research.replay_manifests rm
      where rm.id = replay_manifest_id
        and rm.candidate_id is not distinct from
          evaluation_runs.candidate_id
    )
  )
  with check (
    exists (
      select 1 from trace_research.replay_manifests rm
      where rm.id = replay_manifest_id
        and rm.candidate_id is not distinct from
          evaluation_runs.candidate_id
    )
  );
drop policy if exists evaluation_runs_releaser_read
  on trace_research.evaluation_runs;
create policy evaluation_runs_releaser_read
  on trace_research.evaluation_runs
  for select to trace_research_releaser
  using (
    exists (
      select 1 from trace_research.replay_manifests rm
      where rm.id = replay_manifest_id
    )
  );

create or replace function trace_research.release_gate_passes(
  row_candidate_id text
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select
    exists (
      select 1
      from trace_research.artifact_candidates c
      where c.id = row_candidate_id
        and c.lifecycle = 'selected'
    )
    and exists (
      select 1
      from trace_research.evaluation_runs er
      join trace_research.replay_manifests rm
        on rm.id = er.replay_manifest_id
      where er.candidate_id = row_candidate_id
        and rm.split_name = 'selection'
        and er.passed
        and not er.security_violation
    )
    and exists (
      select 1
      from trace_research.evaluation_runs er
      join trace_research.replay_manifests rm
        on rm.id = er.replay_manifest_id
      where er.candidate_id = row_candidate_id
        and rm.split_name = 'test'
        and rm.hidden_from_proposer
        and er.passed
        and not er.security_violation
    )
    and not exists (
      select 1
      from trace_research.evaluation_runs er
      where er.candidate_id = row_candidate_id
        and er.security_violation
    )
$function$;

alter function trace_research.release_gate_passes(text)
  owner to trace_research_owner;
revoke all on function trace_research.release_gate_passes(text) from public;
grant execute on function trace_research.release_gate_passes(text)
  to trace_research_releaser;

create or replace function trace_research.release_matches_candidate(
  row_candidate_id text,
  row_tenant_id text,
  row_owner_subject_id text,
  row_audience text,
  row_team_id text,
  row_classification smallint,
  row_allowed_purposes text[],
  row_content_sha256 text
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select exists (
    select 1
    from trace_research.artifact_candidates c
    where c.id = row_candidate_id
      and c.tenant_id = row_tenant_id
      and c.owner_subject_id = row_owner_subject_id
      and c.audience = row_audience
      and c.team_id is not distinct from row_team_id
      and c.classification = row_classification
      -- A release may narrow purposes, but can never add one.
      and c.allowed_purposes @> row_allowed_purposes
      and c.content_sha256 = row_content_sha256
  )
$function$;

alter function trace_research.release_matches_candidate(
  text, text, text, text, text, smallint, text[], text
) owner to trace_research_owner;
revoke all on function trace_research.release_matches_candidate(
  text, text, text, text, text, smallint, text[], text
) from public;
grant execute on function trace_research.release_matches_candidate(
  text, text, text, text, text, smallint, text[], text
) to trace_research_releaser;

drop policy if exists artifact_releases_owner_internal
  on trace_research.artifact_releases;
create policy artifact_releases_owner_internal on trace_research.artifact_releases
  for all to trace_research_owner using (true) with check (true);
drop policy if exists artifact_releases_read
  on trace_research.artifact_releases;
create policy artifact_releases_read on trace_research.artifact_releases
  for select to trace_research_miner, trace_research_evaluator,
    trace_research_releaser
  using (
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and exists (
      select 1 from trace_research.artifact_candidates c
      where c.id = candidate_id
    )
  );
drop policy if exists artifact_releases_app_read
  on trace_research.artifact_releases;
create policy artifact_releases_app_read on trace_research.artifact_releases
  for select to trace_research_app
  using (
    status = 'active'
    and trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and exists (
      select 1 from trace_research.artifact_candidates c
      where c.id = candidate_id
    )
  );
drop policy if exists artifact_releases_publish
  on trace_research.artifact_releases;
create policy artifact_releases_publish on trace_research.artifact_releases
  for insert to trace_research_releaser
  with check (
    status = 'active'
    and
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
    and trace_research.release_gate_passes(candidate_id)
    and trace_research.release_matches_candidate(
      candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, content_sha256
    )
  );
drop policy if exists artifact_releases_update
  on trace_research.artifact_releases;
create policy artifact_releases_update on trace_research.artifact_releases
  for update to trace_research_releaser
  using (
    trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
  )
  with check (
    status in ('withdrawn', 'rolled_back')
    and trace_research.current_scope_authorized(
      tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes
    )
  );

drop policy if exists release_exposures_owner_internal
  on trace_research.release_exposures;
create policy release_exposures_owner_internal on trace_research.release_exposures
  for all to trace_research_owner using (true) with check (true);
drop policy if exists release_exposures_authorized
  on trace_research.release_exposures;
create policy release_exposures_authorized on trace_research.release_exposures
  for all to trace_research_releaser, trace_research_app
  using (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
    and (
      subject_id = nullif(current_setting('app.subject_id', true), '')
      or (
        team_id is not null
        and trace_research.current_team_member(tenant_id, team_id)
      )
    )
  )
  with check (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
    and (
      subject_id = nullif(current_setting('app.subject_id', true), '')
      or (
        team_id is not null
        and trace_research.current_team_member(tenant_id, team_id)
      )
    )
  );

drop policy if exists trajectory_influences_owner_internal
  on trace_research.trajectory_influences;
create policy trajectory_influences_owner_internal
  on trace_research.trajectory_influences
  for all to trace_research_owner using (true) with check (true);
drop policy if exists trajectory_influences_authorized
  on trace_research.trajectory_influences;
create policy trajectory_influences_authorized
  on trace_research.trajectory_influences
  for all to trace_research_app
  using (
    exists (
      select 1 from trace_research.trajectories t
      where t.id = trajectory_id
    )
    and exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
    and (
      exposure_id is null
      or exists (
        select 1
        from trace_research.release_exposures x
        where x.id = exposure_id
          and x.release_id = trajectory_influences.release_id
      )
    )
  )
  with check (
    exists (
      select 1 from trace_research.trajectories t
      where t.id = trajectory_id
    )
    and exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
    and (
      exposure_id is null
      or exists (
        select 1
        from trace_research.release_exposures x
        where x.id = exposure_id
          and x.release_id = trajectory_influences.release_id
      )
    )
  );

drop policy if exists release_events_owner_internal
  on trace_research.release_events;
create policy release_events_owner_internal on trace_research.release_events
  for all to trace_research_owner using (true) with check (true);
drop policy if exists release_events_authorized
  on trace_research.release_events;
create policy release_events_authorized on trace_research.release_events
  for all to trace_research_releaser
  using (
    exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
  )
  with check (
    exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
  );
drop policy if exists release_events_app_read
  on trace_research.release_events;
create policy release_events_app_read on trace_research.release_events
  for select to trace_research_app
  using (
    exists (
      select 1 from trace_research.artifact_releases r
      where r.id = release_id
    )
  );

comment on table trace_research.artifact_candidates is
  'Immutable-ish proposal registry. Live harness files are projections, not authority.';
comment on table trace_research.replay_manifests is
  'Frozen evidence/selection/test task and environment identity.';
comment on table trace_research.evaluation_runs is
  'Independent, versioned environment outcomes; proposer role has no access.';
comment on table trace_research.artifact_releases is
  'Signed release pointers admitted only after selection and hidden-test gates.';
comment on table trace_research.trajectory_influences is
  'Release IDs that influenced a later trace, required for leakage exclusion.';
