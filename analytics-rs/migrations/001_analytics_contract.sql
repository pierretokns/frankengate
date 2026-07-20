-- FrankenGate analytics contract v1.
-- PostgreSQL is authoritative; artifact bytes remain in object storage.

create schema if not exists frankengate_analytics;

create table if not exists frankengate_analytics.experiments (
  id text primary key,
  tenant_id text not null,
  actor_id text not null,
  revision text not null,
  created_at timestamptz not null default now(),
  unique (tenant_id, id)
);

create table if not exists frankengate_analytics.runs (
  id text primary key,
  tenant_id text not null,
  experiment_id text not null references frankengate_analytics.experiments(id),
  dataset_revision text not null,
  evaluator_revision text not null,
  model_revision text not null,
  prompt_revision text not null,
  terminal_outcome text,
  created_at timestamptz not null default now(),
  unique (tenant_id, id)
);

create table if not exists frankengate_analytics.evaluation_results (
  run_id text not null references frankengate_analytics.runs(id),
  example_id text not null,
  evaluator_revision text not null,
  score jsonb not null,
  created_at timestamptz not null default now(),
  primary key (run_id, example_id, evaluator_revision)
);

create table if not exists frankengate_analytics.artifact_manifests (
  run_id text not null references frankengate_analytics.runs(id),
  digest text not null,
  media_type text not null,
  object_uri text not null,
  created_at timestamptz not null default now(),
  primary key (run_id, digest)
);

create table if not exists frankengate_analytics.jobs (
  id text primary key,
  tenant_id text not null,
  kind text not null,
  state text not null check (state in ('queued', 'leased', 'cancelled', 'completed', 'failed')),
  attempt integer not null default 0 check (attempt >= 0),
  worker_id text,
  lease_until timestamptz,
  checkpoint text,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists jobs_tenant_state_created_idx
  on frankengate_analytics.jobs (tenant_id, state, created_at, id);

-- Re-running this migration must be safe during rolling deploys.  PostgreSQL
-- has no CREATE POLICY IF NOT EXISTS, so replace policies deterministically.
drop policy if exists experiments_tenant_isolation on frankengate_analytics.experiments;
drop policy if exists runs_tenant_isolation on frankengate_analytics.runs;
drop policy if exists evaluations_tenant_isolation on frankengate_analytics.evaluation_results;
drop policy if exists artifacts_tenant_isolation on frankengate_analytics.artifact_manifests;
drop policy if exists jobs_tenant_isolation on frankengate_analytics.jobs;

alter table frankengate_analytics.experiments enable row level security;
alter table frankengate_analytics.runs enable row level security;
alter table frankengate_analytics.evaluation_results enable row level security;
alter table frankengate_analytics.artifact_manifests enable row level security;
alter table frankengate_analytics.jobs enable row level security;

-- The connection pool must set app.tenant_id for every transaction. Missing
-- tenant context fails closed rather than exposing cross-tenant analytics.
create policy experiments_tenant_isolation on frankengate_analytics.experiments
  using (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
  with check (tenant_id = nullif(current_setting('app.tenant_id', true), ''));
create policy runs_tenant_isolation on frankengate_analytics.runs
  using (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
  with check (tenant_id = nullif(current_setting('app.tenant_id', true), ''));
create policy evaluations_tenant_isolation on frankengate_analytics.evaluation_results
  using (exists (
    select 1 from frankengate_analytics.runs r
    where r.id = run_id and r.tenant_id = nullif(current_setting('app.tenant_id', true), '')
  ))
  with check (exists (
    select 1 from frankengate_analytics.runs r
    where r.id = run_id and r.tenant_id = nullif(current_setting('app.tenant_id', true), '')
  ));
create policy artifacts_tenant_isolation on frankengate_analytics.artifact_manifests
  using (exists (
    select 1 from frankengate_analytics.runs r
    where r.id = run_id and r.tenant_id = nullif(current_setting('app.tenant_id', true), '')
  ))
  with check (exists (
    select 1 from frankengate_analytics.runs r
    where r.id = run_id and r.tenant_id = nullif(current_setting('app.tenant_id', true), '')
  ));
create policy jobs_tenant_isolation on frankengate_analytics.jobs
  using (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
  with check (tenant_id = nullif(current_setting('app.tenant_id', true), ''));

comment on table frankengate_analytics.runs is
  'Immutable run intent and revision lineage; retry attempts belong in a separate leased-job table.';

comment on table frankengate_analytics.jobs is
  'Durable worker lease state; request inference workers must not write this table.';
