\set ON_ERROR_STOP on

-- Transaction-scoped conformance test for the governed candidate -> replay ->
-- evaluation -> release lifecycle. No synthetic row survives this script.
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

create or replace function pg_temp.assert_raises(
  label text,
  statement text
) returns void
language plpgsql
as $function$
begin
  begin
    execute statement;
  exception
    when others then
      return;
  end;
  raise exception '%: statement unexpectedly succeeded', label;
end
$function$;

-- Seed through the fixture owner path. Runtime roles never receive direct
-- access to raw provenance edges or hidden test creation.
insert into trace_research.artifact_candidates (
  id, tenant_id, owner_subject_id, audience, team_id, classification,
  allowed_purposes, policy_revision, kind, lifecycle, generator_name,
  generator_revision, generator_config, seed, content_text, content_sha256,
  evidence_summary
) values
  (
    'candidate-good', 'tenant-a', 'alice', 'private', null, 1,
    array['quality-improvement'], 'policy-v1', 'procedure', 'proposal',
    'signals-agentrx-proposer', 'fixture-v1', '{"threshold": 2}', 20260730,
    'Inspect schema evidence before writing governed SQL.',
    repeat('1', 64), '{"support_count": 1}'
  ),
  (
    'candidate-security-fail', 'tenant-a', 'alice', 'private', null, 1,
    array['quality-improvement'], 'policy-v1', 'procedure', 'proposal',
    'signals-agentrx-proposer', 'fixture-v1', '{"threshold": 2}', 20260730,
    'Unsafe candidate used to prove the security veto.',
    repeat('2', 64), '{"support_count": 1}'
  ),
  (
    'candidate-cross-source', 'tenant-a', 'alice', 'private', null, 1,
    array['quality-improvement'], 'policy-v1', 'procedure', 'proposal',
    'signals-agentrx-proposer', 'fixture-v1', '{"threshold": 2}', 20260730,
    'Candidate whose only evidence is outside the caller authority.',
    repeat('3', 64), '{"support_count": 1}'
  );

insert into trace_research.candidate_sources (
  id, candidate_id, source_trajectory_id, source_event_sequence, evidence_role
) values
  ('source-good', 'candidate-good', 'alice-private', 0, 'support'),
  (
    'source-security-fail', 'candidate-security-fail',
    'alice-private', null, 'counterexample'
  ),
  (
    'source-cross', 'candidate-cross-source',
    'eve-private', 0, 'support'
  );

insert into trace_research.replay_manifests (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, split_name, task_family,
  task_manifest_sha256, environment_sha256, tool_schema_sha256,
  evaluator_revision, hidden_from_proposer, payload
) values
  (
    'manifest-good-evidence', 'candidate-good', 'tenant-a', 'alice',
    'private', null, 1, array['quality-improvement'], 'policy-v1', 'evidence',
    'nl2sql', repeat('a', 64), repeat('b', 64), repeat('c', 64),
    'sql-exec-v1', false, '{"task_count": 20}'
  ),
  (
    'manifest-good-selection', 'candidate-good', 'tenant-a', 'alice',
    'private', null, 1, array['quality-improvement'], 'policy-v1', 'selection',
    'nl2sql', repeat('d', 64), repeat('b', 64), repeat('c', 64),
    'sql-exec-v1', false, '{"task_count": 20}'
  ),
  (
    'manifest-good-test', 'candidate-good', 'tenant-a', 'alice',
    'private', null, 1, array['quality-improvement'], 'policy-v1', 'test',
    'nl2sql', repeat('e', 64), repeat('b', 64), repeat('c', 64),
    'sql-exec-v1', true, '{"task_count": 20, "hidden": true}'
  ),
  (
    'manifest-fail-selection', 'candidate-security-fail', 'tenant-a', 'alice',
    'private', null, 1, array['quality-improvement'], 'policy-v1', 'selection',
    'nl2sql', repeat('f', 64), repeat('b', 64), repeat('c', 64),
    'sql-exec-v1', false, '{"task_count": 20}'
  ),
  (
    'manifest-fail-test', 'candidate-security-fail', 'tenant-a', 'alice',
    'private', null, 1, array['quality-improvement'], 'policy-v1', 'test',
    'nl2sql', repeat('0', 64), repeat('b', 64), repeat('c', 64),
    'sql-exec-v1', true, '{"task_count": 20, "hidden": true}'
  );

set role trace_research_miner;
select set_config('app.tenant_id', 'tenant-a', true);
select set_config('app.subject_id', 'alice', true);
select set_config('app.authorization_epoch', '7', true);
select set_config('app.classification_ceiling', '2', true);
select set_config('app.purpose', 'quality-improvement', true);

select pg_temp.assert_count(
  'miner sees only candidates whose complete provenance is authorized',
  (select count(*) from trace_research.artifact_candidates),
  2
);
select pg_temp.assert_count(
  'miner sees evidence and selection, never hidden test manifests',
  (select count(*) from trace_research.replay_manifests),
  3
);
select pg_temp.assert_count(
  'miner sees zero test manifests',
  (
    select count(*) from trace_research.replay_manifests
    where split_name = 'test'
  ),
  0
);
select pg_temp.assert_raises(
  'miner cannot read independent evaluation outcomes',
  'select count(*) from trace_research.evaluation_runs'
);
select pg_temp.assert_raises(
  'miner cannot create hidden test manifests',
  $sql$
    insert into trace_research.replay_manifests (
      id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, policy_revision, split_name,
      task_family, task_manifest_sha256, environment_sha256,
      tool_schema_sha256, evaluator_revision, hidden_from_proposer, payload
    ) values (
      'miner-forged-test', 'candidate-good', 'tenant-a', 'alice',
      'private', null, 1, array['quality-improvement'], 'policy-v1', 'test',
      'nl2sql', repeat('9', 64), repeat('b', 64), repeat('c', 64),
      'sql-exec-v1', true, '{}'
    )
  $sql$
);

update trace_research.artifact_candidates
set lifecycle = 'selected'
where id in ('candidate-good', 'candidate-security-fail');
select pg_temp.assert_raises(
  'miner cannot mutate candidate content after proposal',
  $sql$
    update trace_research.artifact_candidates
    set content_text = 'mutated'
    where id = 'candidate-good'
  $sql$
);

set role trace_research_releaser;
select pg_temp.assert_raises(
  'release fails before independent selection and test results',
  $sql$
    insert into trace_research.artifact_releases (
      id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, policy_revision, status,
      content_sha256, signature, approved_by
    ) values (
      'release-too-early', 'candidate-good', 'tenant-a', 'alice',
      'private', null, 1, array['quality-improvement'], 'policy-v1', 'active',
      repeat('1', 64), 'fixture-signature', 'independent-reviewer'
    )
  $sql$
);

set role trace_research_evaluator;
select pg_temp.assert_count(
  'evaluator sees authorized evidence, selection, and hidden tests',
  (select count(*) from trace_research.replay_manifests),
  5
);
select pg_temp.assert_raises(
  'evaluation candidate must match its frozen manifest',
  $sql$
    insert into trace_research.evaluation_runs (
      id, replay_manifest_id, candidate_id, evaluator_name,
      evaluator_revision, seed, passed, outcome
    ) values (
      'eval-mismatch', 'manifest-good-selection', 'candidate-security-fail',
      'fixture-evaluator', 'sql-exec-v1', 20260730, true, '{}'
    )
  $sql$
);
insert into trace_research.evaluation_runs (
  id, replay_manifest_id, candidate_id, evaluator_name, evaluator_revision,
  seed, passed, security_violation, outcome
) values
  (
    'eval-good-selection', 'manifest-good-selection', 'candidate-good',
    'fixture-evaluator', 'sql-exec-v1', 20260730, true, false,
    '{"execution_accuracy": 0.8}'
  ),
  (
    'eval-good-test', 'manifest-good-test', 'candidate-good',
    'fixture-evaluator', 'sql-exec-v1', 20260730, true, false,
    '{"execution_accuracy": 0.75}'
  ),
  (
    'eval-fail-selection', 'manifest-fail-selection',
    'candidate-security-fail', 'fixture-evaluator', 'sql-exec-v1',
    20260730, true, false, '{"execution_accuracy": 0.8}'
  ),
  (
    'eval-fail-test', 'manifest-fail-test', 'candidate-security-fail',
    'fixture-evaluator', 'sql-exec-v1', 20260730, true, true,
    '{"execution_accuracy": 0.9, "unauthorized_row_count": 1}'
  );

set role trace_research_releaser;
select pg_temp.assert_raises(
  'a security violation vetoes release even when accuracy passes',
  $sql$
    insert into trace_research.artifact_releases (
      id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, policy_revision, status,
      content_sha256, signature, approved_by
    ) values (
      'release-security-fail', 'candidate-security-fail', 'tenant-a', 'alice',
      'private', null, 1, array['quality-improvement'], 'policy-v1', 'active',
      repeat('2', 64), 'fixture-signature', 'independent-reviewer'
    )
  $sql$
);
select pg_temp.assert_raises(
  'release cannot broaden candidate purposes',
  $sql$
    insert into trace_research.artifact_releases (
      id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
      classification, allowed_purposes, policy_revision, status,
      content_sha256, signature, approved_by
    ) values (
      'release-broadened', 'candidate-good', 'tenant-a', 'alice',
      'private', null, 1,
      array['quality-improvement', 'unapproved-purpose'],
      'policy-v1', 'active', repeat('1', 64), 'fixture-signature',
      'independent-reviewer'
    )
  $sql$
);

insert into trace_research.artifact_releases (
  id, candidate_id, tenant_id, owner_subject_id, audience, team_id,
  classification, allowed_purposes, policy_revision, status,
  content_sha256, signature, approved_by
) values (
  'release-good', 'candidate-good', 'tenant-a', 'alice',
  'private', null, 1, array['quality-improvement'], 'policy-v1', 'active',
  repeat('1', 64), 'fixture-signature', 'independent-reviewer'
);
insert into trace_research.release_events (
  release_id, sequence, event_kind, actor_id, reason
) values (
  'release-good', 0, 'published', 'independent-reviewer',
  'selection and hidden test passed'
);
select pg_temp.assert_raises(
  'releaser cannot mutate signed release content',
  $sql$
    update trace_research.artifact_releases
    set signature = 'mutated'
    where id = 'release-good'
  $sql$
);

set role trace_research_app;
select pg_temp.assert_count(
  'runtime sees active release',
  (select count(*) from trace_research.artifact_releases),
  1
);
insert into trace_research.release_exposures (
  id, release_id, tenant_id, subject_id, team_id
) values (
  'exposure-alice', 'release-good', 'tenant-a', 'alice', null
);
select pg_temp.assert_raises(
  'runtime cannot create an exposure for another subject',
  $sql$
    insert into trace_research.release_exposures (
      id, release_id, tenant_id, subject_id, team_id
    ) values (
      'exposure-bob', 'release-good', 'tenant-a', 'bob', null
    )
  $sql$
);
insert into trace_research.trajectory_influences (
  trajectory_id, release_id, exposure_id, influence_kind
) values (
  'alice-private', 'release-good', 'exposure-alice', 'skill'
);
select pg_temp.assert_raises(
  'runtime cannot attach an influence to an unauthorized trajectory',
  $sql$
    insert into trace_research.trajectory_influences (
      trajectory_id, release_id, exposure_id, influence_kind
    ) values (
      'bob-private', 'release-good', 'exposure-alice', 'skill'
    )
  $sql$
);
select pg_temp.assert_raises(
  'runtime cannot forge release audit events',
  $sql$
    insert into trace_research.release_events (
      release_id, sequence, event_kind, actor_id, reason
    ) values (
      'release-good', 1, 'withdrawn', 'alice', 'forged'
    )
  $sql$
);

set role trace_research_releaser;
update trace_research.artifact_releases
set status = 'withdrawn'
where id = 'release-good';
insert into trace_research.release_events (
  release_id, sequence, event_kind, actor_id, reason
) values (
  'release-good', 1, 'withdrawn', 'independent-reviewer',
  'fixture rollback drill'
);

set role trace_research_app;
select pg_temp.assert_count(
  'withdrawn release disappears from runtime selection',
  (select count(*) from trace_research.artifact_releases),
  0
);
select pg_temp.assert_count(
  'withdrawn release exposures disappear from runtime selection',
  (select count(*) from trace_research.release_exposures),
  0
);

select set_config('app.authorization_epoch', '6', true);
select pg_temp.assert_count(
  'stale epoch hides candidates',
  (select count(*) from trace_research.artifact_candidates),
  0
);

reset role;

do $role_assertions$
declare
  unsafe_count bigint;
begin
  select count(*)
  into unsafe_count
  from pg_roles
  where rolname in (
    'trace_research_miner',
    'trace_research_evaluator',
    'trace_research_releaser'
  )
    and (rolsuper or rolbypassrls or rolcreaterole or rolcreatedb or rolinherit);

  if unsafe_count <> 0 then
    raise exception 'a lifecycle role has an unsafe capability';
  end if;
end
$role_assertions$;

select 'governed skill release lifecycle assertions passed' as result;
rollback;
