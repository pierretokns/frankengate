-- Disposable FinanceBench governed retrieval table.
--
-- This migration is intentionally separate from the 1024-dimensional E2 table:
-- it preserves the native 768-dimensional finance-specialized embedding and
-- exercises the same policy-before-ranking contract on a local pgvector stack.

create extension if not exists vector;
create schema if not exists trace_research;

do $roles$
begin
  if not exists (select 1 from pg_roles where rolname = 'trace_research_owner') then
    create role trace_research_owner nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'trace_research_app') then
    create role trace_research_app nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end
$roles$;

alter schema trace_research owner to trace_research_owner;
revoke all on schema trace_research from public;
grant usage on schema trace_research to trace_research_app;

create table if not exists trace_research.finance_retrieval_documents (
  id text primary key,
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience = 'private'),
  classification smallint not null check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  source_dataset text not null,
  source_revision text not null,
  source_document_id text not null,
  content_sha256 text not null check (content_sha256 ~ '^[a-f0-9]{64}$'),
  lexical_text text not null,
  dense_text text not null,
  structured_metadata jsonb not null default '{}',
  embedding public.vector(768) not null,
  visibility_state text not null default 'active'
    check (visibility_state in ('active', 'withdrawn', 'deleted')),
  withdrawn_at timestamptz,
  deleted_at timestamptz,
  lifecycle_receipt jsonb not null default '{}',
  content_tsv tsvector generated always as (
    to_tsvector('english', coalesce(lexical_text, ''))
  ) stored,
  created_at timestamptz not null default now(),
  unique (source_dataset, source_revision, source_document_id),
  check (
    (visibility_state = 'active' and withdrawn_at is null and deleted_at is null)
    or (visibility_state = 'withdrawn' and withdrawn_at is not null and deleted_at is null)
    or (visibility_state = 'deleted' and deleted_at is not null)
  )
);

create index if not exists finance_retrieval_authority_active_idx
  on trace_research.finance_retrieval_documents
    (tenant_id, owner_subject_id, classification, id)
  where visibility_state = 'active';
create index if not exists finance_retrieval_fts_active_idx
  on trace_research.finance_retrieval_documents using gin (content_tsv)
  where visibility_state = 'active';
create index if not exists finance_retrieval_embedding_hnsw_active_idx
  on trace_research.finance_retrieval_documents
  using hnsw (embedding public.vector_cosine_ops)
  where visibility_state = 'active';

alter table trace_research.finance_retrieval_documents owner to trace_research_owner;
revoke all on trace_research.finance_retrieval_documents from public;
grant select on trace_research.finance_retrieval_documents to trace_research_app;

create table if not exists trace_research.finance_authority_epochs (
  tenant_id text not null,
  subject_id text not null,
  authorization_epoch bigint not null check (authorization_epoch > 0),
  classification_ceiling smallint not null check (classification_ceiling between 0 and 9),
  active boolean not null default true,
  primary key (tenant_id, subject_id)
);

-- The function is replaced after the table exists so fresh and repeat runs
-- share the same definition without relying on the broader Wisp migration.
create or replace function trace_research.finance_authority_valid(
  row_tenant_id text,
  row_owner_subject_id text
) returns boolean
language sql stable security definer
set search_path = pg_catalog, trace_research
as $function$
  select exists (
    select 1
    from trace_research.finance_authority_epochs ae
    where ae.tenant_id = row_tenant_id
      and ae.subject_id = nullif(current_setting('app.subject_id', true), '')
      and ae.authorization_epoch = nullif(current_setting('app.authorization_epoch', true), '')::bigint
      and ae.classification_ceiling = nullif(current_setting('app.classification_ceiling', true), '')::smallint
      and ae.active
  );
$function$;

alter table trace_research.finance_authority_epochs owner to trace_research_owner;
revoke all on trace_research.finance_authority_epochs from public;
revoke all on function trace_research.finance_authority_valid(text, text) from public;
grant execute on function trace_research.finance_authority_valid(text, text) to trace_research_app;

alter table trace_research.finance_retrieval_documents enable row level security;
alter table trace_research.finance_retrieval_documents force row level security;
drop policy if exists finance_retrieval_authorized on trace_research.finance_retrieval_documents;
create policy finance_retrieval_authorized
  on trace_research.finance_retrieval_documents
  for select to trace_research_app
  using (
    visibility_state = 'active'
    and tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and owner_subject_id = nullif(current_setting('app.subject_id', true), '')
    and trace_research.finance_authority_valid(tenant_id, owner_subject_id)
    and classification <= nullif(current_setting('app.classification_ceiling', true), '')::smallint
    and nullif(current_setting('app.purpose', true), '') = any (allowed_purposes)
  );

comment on table trace_research.finance_retrieval_documents is
  'Disposable FinanceBench candidates with native 768-d finance embedding and forced RLS.';
