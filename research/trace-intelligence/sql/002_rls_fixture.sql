truncate table
  trace_research.derived_artifacts,
  trace_research.events,
  trace_research.trajectories,
  trace_research.team_memberships,
  trace_research.authority_epochs
cascade;

insert into trace_research.authority_epochs
  (tenant_id, subject_id, authorization_epoch, classification_ceiling)
values
  ('tenant-a', 'alice', 7, 2),
  ('tenant-a', 'bob', 11, 1),
  ('tenant-b', 'eve', 3, 3);

insert into trace_research.team_memberships
  (tenant_id, team_id, subject_id)
values
  ('tenant-a', 'platform', 'alice'),
  ('tenant-a', 'platform', 'bob');

insert into trace_research.trajectories (
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
  adapter_revision,
  task_id,
  model_name,
  outcome,
  loss_receipt,
  raw_payload,
  content_sha256
) values
  (
    'alice-private',
    'tenant-a',
    'alice',
    'private',
    null,
    1,
    array['history', 'quality-improvement'],
    'policy-v1',
    'fixture',
    'fixture-v1',
    'adapter-v1',
    'task-a',
    'fixture-model',
    '{"success": true}',
    '{"silently_dropped_event_count": 0}',
    '{"fixture": true}',
    repeat('a', 64)
  ),
  (
    'bob-private',
    'tenant-a',
    'bob',
    'private',
    null,
    1,
    array['history', 'quality-improvement'],
    'policy-v1',
    'fixture',
    'fixture-v1',
    'adapter-v1',
    'task-b',
    'fixture-model',
    '{"success": false}',
    '{"silently_dropped_event_count": 0}',
    '{"fixture": true}',
    repeat('b', 64)
  ),
  (
    'platform-shared',
    'tenant-a',
    'alice',
    'team',
    'platform',
    1,
    array['history', 'quality-improvement'],
    'policy-v1',
    'fixture',
    'fixture-v1',
    'adapter-v1',
    'task-team',
    'fixture-model',
    '{"success": true}',
    '{"silently_dropped_event_count": 0}',
    '{"fixture": true}',
    repeat('c', 64)
  ),
  (
    'alice-restricted',
    'tenant-a',
    'alice',
    'private',
    null,
    2,
    array['history'],
    'policy-v1',
    'fixture',
    'fixture-v1',
    'adapter-v1',
    'task-restricted',
    'fixture-model',
    '{"success": true}',
    '{"silently_dropped_event_count": 0}',
    '{"fixture": true}',
    repeat('d', 64)
  ),
  (
    'eve-private',
    'tenant-b',
    'eve',
    'private',
    null,
    1,
    array['history', 'quality-improvement'],
    'policy-v1',
    'fixture',
    'fixture-v1',
    'adapter-v1',
    'task-eve',
    'fixture-model',
    '{"success": true}',
    '{"silently_dropped_event_count": 0}',
    '{"fixture": true}',
    repeat('e', 64)
  );

insert into trace_research.events (
  trajectory_id,
  sequence,
  event_id,
  parent_event_id,
  kind,
  observation_status,
  source_role,
  tool_call_id,
  tool_name,
  content_text,
  payload
)
select
  id,
  0,
  id || ':0',
  null,
  'tool_call_proposal',
  'observed',
  'assistant',
  id || '-call',
  'cloud_diagnose',
  'diagnose repeated deployment timeout for ' || id,
  jsonb_build_object('fixture', true)
from trace_research.trajectories;

insert into trace_research.derived_artifacts (
  id,
  source_trajectory_id,
  tenant_id,
  owner_subject_id,
  audience,
  team_id,
  classification,
  allowed_purposes,
  policy_revision,
  kind,
  content_text,
  payload,
  embedding,
  source_content_sha256,
  derivation_revision
)
select
  id || '-signal',
  id,
  tenant_id,
  owner_subject_id,
  audience,
  team_id,
  classification,
  allowed_purposes,
  policy_revision,
  'signal',
  'repeated deployment timeout ' || id,
  jsonb_build_object('friction_score', 2),
  ('[' ||
    CASE id
      WHEN 'alice-private' THEN '1,0,0,0,0,0,0,0'
      WHEN 'bob-private' THEN '0.9,0.1,0,0,0,0,0,0'
      WHEN 'platform-shared' THEN '0.8,0.2,0,0,0,0,0,0'
      WHEN 'alice-restricted' THEN '0.7,0.3,0,0,0,0,0,0'
      ELSE '0,1,0,0,0,0,0,0'
    END ||
  ']')::vector,
  content_sha256,
  'fixture-derivation-v1'
from trace_research.trajectories;
