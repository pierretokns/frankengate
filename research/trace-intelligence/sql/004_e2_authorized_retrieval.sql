-- E2 authorized-retrieval research extension and transaction-scoped assertions.
--
-- This is an idempotent, disposable research schema extension. It does not alter
-- production schemas and does not load the CodeTraceBench corpus. The fixture
-- rows below are synthetic and are rolled back after the assertions run.
--
-- Contract under test:
--   * authorization, purpose, classification, and lifecycle filters apply before
--     exact, lexical, trigram, or vector ranking;
--   * missing, wrong, or stale authority produces zero retrieval candidates;
--   * withdrawn and soft-deleted documents are not retrieval candidates;
--   * Qwen/Qwen3-Embedding-0.6B vectors retain their native 1024 dimensions.

\set ON_ERROR_STOP on

create table if not exists trace_research.e2_retrieval_documents (
  id text primary key,
  tenant_id text not null,
  owner_subject_id text not null,
  audience text not null check (audience in ('private', 'team')),
  team_id text,
  classification smallint not null default 0
    check (classification between 0 and 9),
  allowed_purposes text[] not null,
  policy_revision text not null,
  source_dataset text not null,
  source_revision text not null,
  source_document_id text not null,
  content_sha256 text not null check (content_sha256 ~ '^[a-f0-9]{64}$'),
  objective_text text not null,
  lexical_text text not null,
  dense_text text not null,
  exact_identifiers text[] not null default '{}',
  structured_metadata jsonb not null default '{}',
  embedding public.vector(1024) not null,
  visibility_state text not null default 'active'
    check (visibility_state in ('active', 'withdrawn', 'deleted')),
  withdrawn_at timestamptz,
  deleted_at timestamptz,
  lifecycle_receipt jsonb not null default '{}',
  content_tsv tsvector generated always as (
    to_tsvector(
      'english',
      coalesce(objective_text, '') || ' ' || coalesce(lexical_text, '')
    )
  ) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_dataset, source_revision, source_document_id),
  check (
    (audience = 'private' and team_id is null)
    or (audience = 'team' and team_id is not null)
  ),
  check (
    (visibility_state = 'active'
      and withdrawn_at is null
      and deleted_at is null)
    or
    (visibility_state = 'withdrawn'
      and withdrawn_at is not null
      and deleted_at is null)
    or
    (visibility_state = 'deleted'
      and deleted_at is not null)
  )
);

create index if not exists e2_retrieval_authority_active_idx
  on trace_research.e2_retrieval_documents (
    tenant_id,
    owner_subject_id,
    team_id,
    classification,
    id
  )
  where visibility_state = 'active';

create index if not exists e2_retrieval_identifiers_active_idx
  on trace_research.e2_retrieval_documents
  using gin (exact_identifiers)
  where visibility_state = 'active';

create index if not exists e2_retrieval_structured_active_idx
  on trace_research.e2_retrieval_documents
  using gin (structured_metadata jsonb_path_ops)
  where visibility_state = 'active';

create index if not exists e2_retrieval_fts_active_idx
  on trace_research.e2_retrieval_documents
  using gin (content_tsv)
  where visibility_state = 'active';

-- pg_trgm is bundled by PostgreSQL and available on Aurora PostgreSQL, but keep
-- the disposable fixture runnable on reduced PostgreSQL images that omit it.
do $trigram$
begin
  if exists (
    select 1
    from pg_catalog.pg_available_extensions
    where name = 'pg_trgm'
  ) then
    execute 'create extension if not exists pg_trgm';
    execute $index$
      create index if not exists e2_retrieval_trigram_active_idx
      on trace_research.e2_retrieval_documents
      using gin (lexical_text public.gin_trgm_ops)
      where visibility_state = 'active'
    $index$;
  end if;
end
$trigram$;

-- Exact vector search needs no ANN index. Add HNSW only when the installed
-- pgvector build exposes both the access method and cosine operator class.
do $hnsw$
begin
  if exists (
    select 1
    from pg_catalog.pg_am
    where amname = 'hnsw'
  ) and exists (
    select 1
    from pg_catalog.pg_opclass
    where opcname = 'vector_cosine_ops'
  ) then
    execute $index$
      create index if not exists e2_retrieval_embedding_hnsw_active_idx
      on trace_research.e2_retrieval_documents
      using hnsw (embedding public.vector_cosine_ops)
      where visibility_state = 'active'
    $index$;
  end if;
end
$hnsw$;

alter table trace_research.e2_retrieval_documents
  owner to trace_research_owner;
revoke all on trace_research.e2_retrieval_documents from public;
grant select on trace_research.e2_retrieval_documents
  to trace_research_app;

alter table trace_research.e2_retrieval_documents enable row level security;
alter table trace_research.e2_retrieval_documents force row level security;

drop policy if exists e2_retrieval_documents_authorized
  on trace_research.e2_retrieval_documents;
create policy e2_retrieval_documents_authorized
  on trace_research.e2_retrieval_documents
  for select
  to trace_research_app
  using (
    visibility_state = 'active'
    and tenant_id = nullif(current_setting('app.tenant_id', true), '')
    and trace_research.current_authority_valid(
      tenant_id,
      owner_subject_id
    )
    and classification <=
      nullif(
        current_setting('app.classification_ceiling', true),
        ''
      )::smallint
    and nullif(current_setting('app.purpose', true), '') =
      any (allowed_purposes)
    and (
      (
        audience = 'private'
        and owner_subject_id =
          nullif(current_setting('app.subject_id', true), '')
      )
      or
      (
        audience = 'team'
        and trace_research.current_team_member(tenant_id, team_id)
      )
    )
  );

comment on table trace_research.e2_retrieval_documents is
  'Disposable E2 retrieval candidates with 1024-d embeddings and forced RLS.';
comment on column trace_research.e2_retrieval_documents.embedding is
  'Native 1024-d output from the pinned Qwen/Qwen3-Embedding-0.6B experiment.';
comment on column trace_research.e2_retrieval_documents.lifecycle_receipt is
  'Testable provenance for withdrawal or deletion; never used as an authorization substitute.';

-- Transaction-scoped conformance fixture. No fixture row survives this file.
begin;

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

create or replace function pg_temp.assert_text(
  label text,
  actual text,
  expected text
) returns void
language plpgsql
as $function$
begin
  if actual is distinct from expected then
    raise exception '%: got %, expected %', label, actual, expected;
  end if;
end
$function$;

insert into trace_research.authority_epochs (
  tenant_id,
  subject_id,
  authorization_epoch,
  classification_ceiling,
  active
) values
  ('e2-tenant-a', 'e2-alice', 17, 2, true),
  ('e2-tenant-a', 'e2-bob', 23, 1, true),
  ('e2-tenant-b', 'e2-eve', 31, 3, true)
on conflict (tenant_id, subject_id) do update set
  authorization_epoch = excluded.authorization_epoch,
  classification_ceiling = excluded.classification_ceiling,
  active = excluded.active;

insert into trace_research.team_memberships (
  tenant_id,
  team_id,
  subject_id,
  active
) values
  ('e2-tenant-a', 'e2-platform', 'e2-alice', true),
  ('e2-tenant-a', 'e2-platform', 'e2-bob', true)
on conflict (tenant_id, team_id, subject_id) do update set
  active = excluded.active;

insert into trace_research.e2_retrieval_documents (
  id,
  tenant_id,
  owner_subject_id,
  audience,
  team_id,
  classification,
  allowed_purposes,
  policy_revision,
  source_dataset,
  source_revision,
  source_document_id,
  content_sha256,
  objective_text,
  lexical_text,
  dense_text,
  exact_identifiers,
  structured_metadata,
  embedding
) values
  (
    'e2-alice-private',
    'e2-tenant-a',
    'e2-alice',
    'private',
    null,
    1,
    array['history', 'quality-improvement'],
    'e2-policy-v1',
    'e2-synthetic-conformance',
    'v1',
    'alice-private',
    repeat('a', 64),
    'diagnose deployment timeout',
    'diagnose deployment timeout in cloud mantle endpoint',
    'repeated deployment timeout recovered by regional failover',
    array['MantleEndpoint', 'RequestTimeout'],
    '{"task_family":"cloud-debugging","outcome":"recovered"}',
    (
      '[' ||
      array_to_string(
        array_prepend(1, array_fill(0, array[1023])),
        ','
      ) ||
      ']'
    )::public.vector(1024)
  ),
  (
    'e2-platform-shared',
    'e2-tenant-a',
    'e2-alice',
    'team',
    'e2-platform',
    1,
    array['history', 'quality-improvement'],
    'e2-policy-v1',
    'e2-synthetic-conformance',
    'v1',
    'platform-shared',
    repeat('b', 64),
    'repair regional routing',
    'repair regional routing for mantle availability',
    'multi-region routing recovered after availability failure',
    array['MantleEndpoint', 'RoutePolicy'],
    '{"task_family":"cloud-debugging","outcome":"recovered"}',
    (
      '[' ||
      array_to_string(
        array_prepend(
          0,
          array_prepend(1, array_fill(0, array[1022]))
        ),
        ','
      ) ||
      ']'
    )::public.vector(1024)
  ),
  (
    -- This unauthorized row is the exact vector nearest neighbour. It must
    -- disappear under RLS before ORDER BY or LIMIT can observe it.
    'e2-bob-private-nearest-decoy',
    'e2-tenant-a',
    'e2-bob',
    'private',
    null,
    1,
    array['history', 'quality-improvement'],
    'e2-policy-v1',
    'e2-synthetic-conformance',
    'v1',
    'bob-private-nearest-decoy',
    repeat('c', 64),
    'diagnose deployment timeout',
    'diagnose deployment timeout MantleEndpoint RequestTimeout',
    'deployment timeout',
    array['MantleEndpoint', 'RequestTimeout'],
    '{"task_family":"cloud-debugging","outcome":"failed"}',
    (
      '[' ||
      array_to_string(
        array_prepend(1, array_fill(0, array[1023])),
        ','
      ) ||
      ']'
    )::public.vector(1024)
  ),
  (
    'e2-other-tenant-nearest-decoy',
    'e2-tenant-b',
    'e2-eve',
    'private',
    null,
    1,
    array['history', 'quality-improvement'],
    'e2-policy-v1',
    'e2-synthetic-conformance',
    'v1',
    'other-tenant-nearest-decoy',
    repeat('d', 64),
    'diagnose deployment timeout',
    'diagnose deployment timeout MantleEndpoint RequestTimeout',
    'deployment timeout',
    array['MantleEndpoint', 'RequestTimeout'],
    '{"task_family":"cloud-debugging","outcome":"failed"}',
    (
      '[' ||
      array_to_string(
        array_prepend(1, array_fill(0, array[1023])),
        ','
      ) ||
      ']'
    )::public.vector(1024)
  ),
  (
    'e2-alice-withdrawn',
    'e2-tenant-a',
    'e2-alice',
    'private',
    null,
    1,
    array['history'],
    'e2-policy-v1',
    'e2-synthetic-conformance',
    'v1',
    'alice-withdrawn',
    repeat('e', 64),
    'withdrawn deployment timeout',
    'withdrawn deployment timeout MantleEndpoint',
    'withdrawn deployment timeout',
    array['MantleEndpoint'],
    '{"task_family":"cloud-debugging","outcome":"withdrawn"}',
    (
      '[' ||
      array_to_string(
        array_prepend(1, array_fill(0, array[1023])),
        ','
      ) ||
      ']'
    )::public.vector(1024)
  ),
  (
    'e2-alice-deleted',
    'e2-tenant-a',
    'e2-alice',
    'private',
    null,
    1,
    array['history'],
    'e2-policy-v1',
    'e2-synthetic-conformance',
    'v1',
    'alice-deleted',
    repeat('f', 64),
    'deleted deployment timeout',
    'deleted deployment timeout MantleEndpoint',
    'deleted deployment timeout',
    array['MantleEndpoint'],
    '{"task_family":"cloud-debugging","outcome":"deleted"}',
    (
      '[' ||
      array_to_string(
        array_prepend(1, array_fill(0, array[1023])),
        ','
      ) ||
      ']'
    )::public.vector(1024)
  );

update trace_research.e2_retrieval_documents
set
  visibility_state = 'withdrawn',
  withdrawn_at = statement_timestamp(),
  updated_at = statement_timestamp(),
  lifecycle_receipt = '{"reason":"conformance-withdrawal"}'
where id = 'e2-alice-withdrawn';

update trace_research.e2_retrieval_documents
set
  visibility_state = 'deleted',
  deleted_at = statement_timestamp(),
  updated_at = statement_timestamp(),
  lifecycle_receipt = '{"reason":"conformance-soft-delete"}'
where id = 'e2-alice-deleted';

set role trace_research_app;

select set_config('app.tenant_id', 'e2-tenant-a', true);
select set_config('app.subject_id', 'e2-alice', true);
select set_config('app.authorization_epoch', '17', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'history', true);

select pg_temp.assert_count(
  'authorized active candidates only',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
  ),
  2
);

select pg_temp.assert_count(
  'exact identifier candidates are authorization-filtered',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
    where exact_identifiers @> array['MantleEndpoint']
  ),
  2
);

select pg_temp.assert_count(
  'FTS candidates are authorization-filtered',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
    where content_tsv @@
      websearch_to_tsquery('english', '"deployment timeout"')
  ),
  1
);

select pg_temp.assert_text(
  'unauthorized exact nearest neighbours are removed before vector ranking',
  (
    select id
    from trace_research.e2_retrieval_documents
    order by embedding <=> (
      '[' ||
      array_to_string(
        array_prepend(1, array_fill(0, array[1023])),
        ','
      ) ||
      ']'
    )::public.vector(1024)
    limit 1
  ),
  'e2-alice-private'
);

select pg_temp.assert_count(
  'withdrawal is absent from ranked candidates',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
    where id = 'e2-alice-withdrawn'
  ),
  0
);

select pg_temp.assert_count(
  'soft deletion is absent from ranked candidates',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
    where id = 'e2-alice-deleted'
  ),
  0
);

-- If pg_trgm exists, prove its ranked candidate set is RLS-filtered too.
do $trigram_assertion$
declare
  candidate_count bigint;
begin
  if exists (
    select 1
    from pg_catalog.pg_extension
    where extname = 'pg_trgm'
  ) then
    select count(*)
    into candidate_count
    from trace_research.e2_retrieval_documents
    where lexical_text % 'deployment timeout MantleEndpoint';

    if candidate_count <> 1 then
      raise exception
        'trigram candidates are authorization-filtered: got %, expected 1',
        candidate_count;
    end if;
  end if;
end
$trigram_assertion$;

-- Missing epoch: zero candidates even though every retrieval representation
-- (identifier, FTS, trigram, and vector) has matching rows.
select set_config('app.authorization_epoch', '', true);
select pg_temp.assert_count(
  'missing epoch yields zero ranked candidates',
  (
    select count(*)
    from (
      select id
      from trace_research.e2_retrieval_documents
      order by embedding <=> (
        '[' ||
        array_to_string(
          array_prepend(1, array_fill(0, array[1023])),
          ','
        ) ||
        ']'
      )::public.vector(1024)
      limit 20
    ) ranked
  ),
  0
);

-- Stale epoch.
select set_config('app.authorization_epoch', '16', true);
select pg_temp.assert_count(
  'stale epoch yields zero ranked candidates',
  (
    select count(*)
    from (
      select id
      from trace_research.e2_retrieval_documents
      where content_tsv @@
        websearch_to_tsquery('english', 'deployment timeout')
      order by ts_rank_cd(
        content_tsv,
        websearch_to_tsquery('english', 'deployment timeout')
      ) desc
      limit 20
    ) ranked
  ),
  0
);

-- Wrong subject and wrong tenant each fail closed.
select set_config('app.authorization_epoch', '17', true);
select set_config('app.subject_id', 'e2-mallory', true);
select pg_temp.assert_count(
  'wrong subject yields zero candidates',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
  ),
  0
);

select set_config('app.subject_id', 'e2-alice', true);
select set_config('app.tenant_id', 'e2-tenant-b', true);
select pg_temp.assert_count(
  'wrong tenant yields zero candidates',
  (
    select count(*)
    from trace_research.e2_retrieval_documents
  ),
  0
);

reset role;

do $index_assertions$
declare
  vector_dimension integer;
  hnsw_available boolean;
  hnsw_index_present boolean;
begin
  select atttypmod
  into vector_dimension
  from pg_catalog.pg_attribute
  where attrelid = 'trace_research.e2_retrieval_documents'::regclass
    and attname = 'embedding'
    and not attisdropped;

  if vector_dimension <> 1024 then
    raise exception
      'E2 embedding dimension: got %, expected 1024',
      vector_dimension;
  end if;

  select exists (
    select 1
    from pg_catalog.pg_am
    where amname = 'hnsw'
  ) and exists (
    select 1
    from pg_catalog.pg_opclass
    where opcname = 'vector_cosine_ops'
  )
  into hnsw_available;

  select to_regclass(
    'trace_research.e2_retrieval_embedding_hnsw_active_idx'
  ) is not null
  into hnsw_index_present;

  if hnsw_available and not hnsw_index_present then
    raise exception 'HNSW is available but the E2 HNSW index is missing';
  end if;
end
$index_assertions$;

rollback;

select 'E2 authorized retrieval assertions passed' as result;
