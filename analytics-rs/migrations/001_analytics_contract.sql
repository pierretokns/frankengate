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
  replay_of text references frankengate_analytics.jobs(id),
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists jobs_tenant_state_created_idx
  on frankengate_analytics.jobs (tenant_id, state, created_at, id);

-- Lease, heartbeat, checkpoint, and terminal transitions must advance the
-- timestamp used by recovery and operational dashboards.  Keep this trigger
-- idempotent so rolling migration retries do not fail.
create or replace function frankengate_analytics.touch_job_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists jobs_touch_updated_at on frankengate_analytics.jobs;
create trigger jobs_touch_updated_at
before update on frankengate_analytics.jobs
for each row execute function frankengate_analytics.touch_job_updated_at();

create table if not exists frankengate_analytics.run_attempts (
  id text primary key,
  tenant_id text not null,
  run_id text not null references frankengate_analytics.runs(id),
  attempt integer not null check (attempt > 0),
  worker_id text not null,
  job_id text not null references frankengate_analytics.jobs(id),
  outcome jsonb,
  created_at timestamptz not null default now(),
  unique (tenant_id, run_id, attempt),
  unique (tenant_id, job_id)
);

create index if not exists run_attempts_tenant_run_idx
  on frankengate_analytics.run_attempts (tenant_id, run_id, attempt);

-- The table predates replay lineage in early deployments.  Keep upgrades
-- idempotent for already-created tables as well as fresh installs.
alter table frankengate_analytics.jobs
  add column if not exists replay_of text references frankengate_analytics.jobs(id);

-- Re-running this migration must be safe during rolling deploys.  PostgreSQL
-- has no CREATE POLICY IF NOT EXISTS, so replace policies deterministically.
drop policy if exists experiments_tenant_isolation on frankengate_analytics.experiments;
drop policy if exists runs_tenant_isolation on frankengate_analytics.runs;
drop policy if exists run_attempts_tenant_isolation on frankengate_analytics.run_attempts;
drop policy if exists evaluations_tenant_isolation on frankengate_analytics.evaluation_results;
drop policy if exists artifacts_tenant_isolation on frankengate_analytics.artifact_manifests;
drop policy if exists jobs_tenant_isolation on frankengate_analytics.jobs;

alter table frankengate_analytics.experiments enable row level security;
alter table frankengate_analytics.experiments force row level security;
alter table frankengate_analytics.runs enable row level security;
alter table frankengate_analytics.runs force row level security;
alter table frankengate_analytics.run_attempts enable row level security;
alter table frankengate_analytics.run_attempts force row level security;
alter table frankengate_analytics.evaluation_results enable row level security;
alter table frankengate_analytics.evaluation_results force row level security;
alter table frankengate_analytics.artifact_manifests enable row level security;
alter table frankengate_analytics.artifact_manifests force row level security;
alter table frankengate_analytics.jobs enable row level security;
alter table frankengate_analytics.jobs force row level security;

-- The connection pool must set app.tenant_id for every transaction. Missing
-- tenant context fails closed rather than exposing cross-tenant analytics.
create policy experiments_tenant_isolation on frankengate_analytics.experiments
  using (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
  with check (tenant_id = nullif(current_setting('app.tenant_id', true), ''));
create policy runs_tenant_isolation on frankengate_analytics.runs
  using (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and exists (
      select 1 from frankengate_analytics.experiments e
      where e.id = experiment_id and e.tenant_id = runs.tenant_id
    )
  )
  with check (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and exists (
      select 1 from frankengate_analytics.experiments e
      where e.id = experiment_id and e.tenant_id = runs.tenant_id
    )
  );
create policy run_attempts_tenant_isolation on frankengate_analytics.run_attempts
  using (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and exists (
      select 1 from frankengate_analytics.runs r
      where r.id = frankengate_analytics.run_attempts.run_id
        and r.tenant_id = frankengate_analytics.run_attempts.tenant_id
    )
    and exists (
      select 1 from frankengate_analytics.jobs j
      where j.id = frankengate_analytics.run_attempts.job_id
        and j.tenant_id = frankengate_analytics.run_attempts.tenant_id
    )
  )
  with check (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and exists (
      select 1 from frankengate_analytics.runs r
      where r.id = frankengate_analytics.run_attempts.run_id
        and r.tenant_id = frankengate_analytics.run_attempts.tenant_id
    )
    and exists (
      select 1 from frankengate_analytics.jobs j
      where j.id = frankengate_analytics.run_attempts.job_id
        and j.tenant_id = frankengate_analytics.run_attempts.tenant_id
    )
  );
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

comment on table frankengate_analytics.run_attempts is
  'Tenant-scoped execution evidence linking a run attempt to one durable worker job.';

comment on table frankengate_analytics.jobs is
  'Durable worker lease state; request inference workers must not write this table.';
