-- Frankengate wiki-gap mining projection.
--
-- ClickHouse is an analytical projection, not the authority store.  Keep
-- tenant/authorization state, wiki approvals, and candidate lifecycle state
-- in PostgreSQL.  Feed this table from the governed trace exporter and retain
-- raw payloads outside the analytical table when they are not needed for gap
-- detection.

CREATE TABLE IF NOT EXISTS frankengate_trace_events
(
    tenant_id LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_id String,
    event_type LowCardinality(String),
    query_id String,
    session_id String,
    user_id String,
    text String,
    page_ids Array(String),
    tool String,
    external UInt8 DEFAULT 0,
    answerable Nullable(UInt8),
    confidence Nullable(Float32),
    feedback_kind LowCardinality(String),
    outcome_status LowCardinality(String),
    payload JSON
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (tenant_id, session_id, event_time, event_id)
TTL event_time + INTERVAL 730 DAY DELETE;

-- The first pass is intentionally deterministic.  It produces one compact
-- row per query so a frontier adjudicator sees evidence, not a full log scan.
CREATE OR REPLACE VIEW frankengate_wiki_gap_query_rollup AS
SELECT
    tenant_id,
    query_id,
    any(session_id) AS session_id,
    any(user_id) AS user_id,
    argMaxIf(text, event_time, event_type IN ('question', 'user_message')) AS question_text,
    countIf(event_type = 'retrieval') AS retrieval_events,
    countIf(event_type = 'retrieval' AND length(page_ids) > 0) AS useful_retrieval_events,
    countIf(event_type = 'tool_call' AND external = 1) AS external_tool_calls,
    countIf(feedback_kind IN ('correction', 'wrong', 'stale')) AS corrections,
    countIf(outcome_status IN ('failure', 'failed', 'rollback')) AS failed_outcomes,
    min(event_time) AS first_event_time,
    arrayDistinct(arrayFlatten(groupArrayIf(page_ids, event_type = 'retrieval'))) AS retrieved_page_ids,
    groupUniqArray(event_id) AS evidence_event_ids
FROM frankengate_trace_events
GROUP BY tenant_id, query_id;

-- High-confidence operational gaps: the wiki yielded no usable evidence and
-- the agent had to call an external tool.
SELECT
    tenant_id,
    query_id,
    'missing_operational_knowledge' AS gap_type,
    question_text,
    evidence_event_ids,
    retrieved_page_ids
FROM frankengate_wiki_gap_query_rollup
WHERE useful_retrieval_events = 0
  AND external_tool_calls > 0;

-- Stale/incorrect candidates are only promoted when a correction or failed
-- outcome corroborates the age signal.  Join this rollup to the authoritative
-- wiki page-version table in PostgreSQL or an exported ClickHouse dimension.
SELECT
    tenant_id,
    query_id,
    'incomplete_or_incorrect' AS gap_type,
    question_text,
    corrections,
    failed_outcomes,
    evidence_event_ids
FROM frankengate_wiki_gap_query_rollup
WHERE corrections > 0 OR failed_outcomes > 0;

-- Session-level coverage: find recurring demand across distinct users before
-- asking a model to cluster or draft a missing page.
SELECT
    tenant_id,
    lowerUTF8(trim(question_text)) AS normalized_question,
    uniqExact(user_id) AS distinct_users,
    uniqExact(session_id) AS distinct_sessions,
    count() AS demand_count
FROM frankengate_wiki_gap_query_rollup
WHERE question_text != ''
GROUP BY tenant_id, normalized_question
HAVING distinct_users >= 2
ORDER BY demand_count DESC;
