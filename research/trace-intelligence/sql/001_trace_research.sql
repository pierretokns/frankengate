-- Disposable trace-intelligence research schema.
--
-- This schema is deliberately separate from the production analytics contract.
-- It validates Aurora-compatible PostgreSQL semantics: typed authorization fields,
-- JSONB evidence, full-text search, pgvector, and RLS-before-retrieval.

create schema if not exists trace_research;

do $roles$
begin
  if not exists (select 1 from pg_roles where rolname = 'trace_research_owner') then
    create role trace_research_owner
      nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'trace_research_app') then
    create role trace_research_app
      nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end
$roles$;

alter schema trace_research owner to trace_research_owner;
revoke all on schema trace_research from public;
grant usage on schema trace_research to trace_research_app;
-- pgvector is installed in public by the shared fixture. USAGE resolves its type
-- and operators; it does not grant access to unrelated public tables.
grant usage on schema public to trace_research_app;

create table if not exists trace_research.authority_epochs (
  tenant_id text not null,
  subject_id text not null,
  authorization_epoch bigint not null check (authorization_epoch > 0),
  classification_ceiling smallint not null check (classification_ceiling between 0 and 9),
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, subject_id)
);

create table if not exists trace_research.team_memberships (
  tenant_id text not null,
  team_id text not null,
  subject_id text not null,
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, team_id, subject_id),
  foreign key (tenant_id, subject_id)
    references trace_research.authority_epochs (tenant_id, subject_id)
);

create table if not exists trace_research.trajectories (
  id text primary key,
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience in ('private', 'team')),
  team_id text,
  classification smallint not null default 0 check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  source_dataset text not null,
  source_revision text not null,
  adapter_revision text not null,
  task_id text not null,
  harness text,
  model_name text,
  outcome jsonb not null,
  loss_receipt jsonb not null,
  raw_payload jsonb not null,
  content_sha256 text not null check (content_sha256 ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now(),
  check (
    (audience = 'private' and team_id is null)
    or (audience = 'team' and team_id is not null)
  )
);

create table if not exists trace_research.events (
  trajectory_id text not null references trace_research.trajectories(id) on delete cascade,
  sequence integer not null check (sequence >= 0),
  event_id text not null,
  parent_event_id text,
  kind text not null,
  observation_status text not null
    check (observation_status in ('observed', 'reconstructed', 'inferred', 'missing')),
  source_role text not null,
  tool_call_id text,
  tool_name text,
  content_text text,
  payload jsonb not null,
  content_tsv tsvector generated always as
    (to_tsvector('english', coalesce(content_text, ''))) stored,
  primary key (trajectory_id, sequence),
  unique (trajectory_id, event_id)
);

create table if not exists trace_research.derived_artifacts (
  id text primary key,
  source_trajectory_id text not null
    references trace_research.trajectories(id) on delete cascade,
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience in ('private', 'team')),
  team_id text,
  classification smallint not null check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  kind text not null check (
    kind in (
      'signal',
      'diagnosis_proposal',
      'eval_proposal',
      'fact_proposal',
      'procedure_proposal',
      'cluster_assignment'
    )
  ),
  lifecycle text not null default 'proposal'
    check (lifecycle in ('proposal', 'reviewed', 'released', 'withdrawn')),
  content_text text,
  payload jsonb not null,
  embedding vector(8),
  content_tsv tsvector generated always as
    (to_tsvector('english', coalesce(content_text, ''))) stored,
  source_content_sha256 text not null,
  derivation_revision text not null,
  created_at timestamptz not null default now(),
  check (
    (audience = 'private' and team_id is null)
    or (audience = 'team' and team_id is not null)
  )
);

create index if not exists trajectories_tenant_owner_created_idx
  on trace_research.trajectories (tenant_id, owner_subject_id, created_at, id);
create index if not exists trajectories_tenant_team_created_idx
  on trace_research.trajectories (tenant_id, team_id, created_at, id)
  where audience = 'team';
create index if not exists trajectories_task_idx
  on trace_research.trajectories (source_dataset, task_id, model_name);
create index if not exists events_content_tsv_idx
  on trace_research.events using gin (content_tsv);
create index if not exists events_tool_idx
  on trace_research.events (kind, tool_name, trajectory_id, sequence);
create index if not exists derived_content_tsv_idx
  on trace_research.derived_artifacts using gin (content_tsv);
create index if not exists derived_embedding_hnsw_idx
  on trace_research.derived_artifacts using hnsw (embedding vector_cosine_ops);

alter table trace_research.authority_epochs owner to trace_research_owner;
alter table trace_research.team_memberships owner to trace_research_owner;
alter table trace_research.trajectories owner to trace_research_owner;
alter table trace_research.events owner to trace_research_owner;
alter table trace_research.derived_artifacts owner to trace_research_owner;

create or replace function trace_research.current_authority_valid(
  row_tenant_id text,
  row_owner_subject_id text
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select exists (
    select 1
    from trace_research.authority_epochs ae
    where ae.tenant_id = row_tenant_id
      and ae.subject_id = nullif(current_setting('app.subject_id', true), '')
      and ae.authorization_epoch =
        nullif(current_setting('app.authorization_epoch', true), '')::bigint
      and ae.classification_ceiling =
        nullif(current_setting('app.classification_ceiling', true), '')::smallint
      and ae.active
  )
$function$;

create or replace function trace_research.current_team_member(
  row_tenant_id text,
  row_team_id text
) returns boolean
language sql
stable
security definer
set search_path = pg_catalog, trace_research
as $function$
  select exists (
    select 1
    from trace_research.team_memberships tm
    where tm.tenant_id = row_tenant_id
      and tm.team_id = row_team_id
      and tm.subject_id = nullif(current_setting('app.subject_id', true), '')
      and tm.active
  )
$function$;

alter function trace_research.current_authority_valid(text, text)
  owner to trace_research_owner;
alter function trace_research.current_team_member(text, text)
  owner to trace_research_owner;
revoke all on function trace_research.current_authority_valid(text, text) from public;
revoke all on function trace_research.current_team_member(text, text) from public;
grant execute on function trace_research.current_authority_valid(text, text)
  to trace_research_app;
grant execute on function trace_research.current_team_member(text, text)
  to trace_research_app;

grant select, insert, update, delete on trace_research.trajectories
  to trace_research_app;
grant select, insert, update, delete on trace_research.events
  to trace_research_app;
grant select, insert, update, delete on trace_research.derived_artifacts
  to trace_research_app;

alter table trace_research.trajectories enable row level security;
alter table trace_research.trajectories force row level security;
alter table trace_research.events enable row level security;
alter table trace_research.events force row level security;
alter table trace_research.derived_artifacts enable row level security;
alter table trace_research.derived_artifacts force row level security;

drop policy if exists trajectories_authorized on trace_research.trajectories;
create policy trajectories_authorized on trace_research.trajectories
  for all to trace_research_app
  using (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and trace_research.current_authority_valid(tenant_id, owner_subject_id)
    and classification <=
      nullif(current_setting('app.classification_ceiling', true), '')::smallint
    and nullif(current_setting('app.purpose', true), '') = any (allowed_purposes)
    and (
      (audience = 'private'
        and owner_subject_id = nullif(current_setting('app.subject_id', true), ''))
      or
      (audience = 'team'
        and trace_research.current_team_member(tenant_id, team_id))
    )
  )
  with check (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and trace_research.current_authority_valid(tenant_id, owner_subject_id)
    and classification <=
      nullif(current_setting('app.classification_ceiling', true), '')::smallint
    and nullif(current_setting('app.purpose', true), '') = any (allowed_purposes)
    and (
      (audience = 'private'
        and owner_subject_id = nullif(current_setting('app.subject_id', true), ''))
      or
      (audience = 'team'
        and trace_research.current_team_member(tenant_id, team_id))
    )
  );

drop policy if exists events_authorized on trace_research.events;
create policy events_authorized on trace_research.events
  for all to trace_research_app
  using (
    exists (
      select 1
      from trace_research.trajectories t
      where t.id = trajectory_id
    )
  )
  with check (
    exists (
      select 1
      from trace_research.trajectories t
      where t.id = trajectory_id
    )
  );

drop policy if exists derived_artifacts_authorized
  on trace_research.derived_artifacts;
create policy derived_artifacts_authorized on trace_research.derived_artifacts
  for all to trace_research_app
  using (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and trace_research.current_authority_valid(tenant_id, owner_subject_id)
    and classification <=
      nullif(current_setting('app.classification_ceiling', true), '')::smallint
    and nullif(current_setting('app.purpose', true), '') = any (allowed_purposes)
    and exists (
      select 1
      from trace_research.trajectories t
      where t.id = source_trajectory_id
    )
  )
  with check (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and trace_research.current_authority_valid(tenant_id, owner_subject_id)
    and classification <=
      nullif(current_setting('app.classification_ceiling', true), '')::smallint
    and nullif(current_setting('app.purpose', true), '') = any (allowed_purposes)
    and exists (
      select 1
      from trace_research.trajectories t
      where t.id = source_trajectory_id
    )
  );

comment on schema trace_research is
  'Disposable empirical schema; not a production migration or Aurora emulator.';
comment on table trace_research.trajectories is
  'Canonical trace envelope with typed authorization and raw loss-aware evidence.';
comment on table trace_research.derived_artifacts is
  'Copy-on-write signal, diagnosis, eval, memory, and clustering proposals with source lineage.';
