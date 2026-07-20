use sqlx::{postgres::PgPoolOptions, PgPool};

use crate::{
    ArtifactManifest, EvaluationResult, Experiment, JobStats, ReplayJob, Run, RunAttempt, SubmitJob,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LeaseClaim {
    pub id: String,
    pub tenant: String,
    pub kind: String,
    pub attempt: i32,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct RunSummary {
    pub id: String,
    pub experiment_id: String,
    pub dataset_revision: String,
    pub evaluator_revision: String,
    pub model_revision: String,
    pub prompt_revision: String,
    pub terminal_outcome: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ArtifactSummary {
    pub run_id: String,
    pub digest: String,
    pub media_type: String,
    pub object_uri: String,
    pub created_at: String,
}

/// Optional durable-store boot fence. The process remains usable in local
/// development without Postgres, while production can require a reachable
/// database by setting DATABASE_URL.
pub async fn connect_from_env() -> Result<Option<PgPool>, sqlx::Error> {
    let Some(url) = std::env::var_os("DATABASE_URL") else {
        return Ok(None);
    };
    let pool = PgPoolOptions::new()
        .max_connections(
            std::env::var("DATABASE_MAX_CONNECTIONS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(10),
        )
        .connect(&url.to_string_lossy())
        .await?;
    sqlx::migrate!("./migrations").run(&pool).await?;
    sqlx::query("select 1").execute(&pool).await?;
    Ok(Some(pool))
}

/// Insert a job under a tenant-scoped transaction. RLS is deliberately
/// enforced by the database; callers cannot accidentally omit the tenant
/// setting and receive another tenant's rows.
pub async fn submit_job(pool: &PgPool, job: &SubmitJob) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(&job.tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "insert into frankengate_analytics.jobs (id, tenant_id, kind, state)\
         values ($1, $2, $3, 'queued') on conflict (id) do nothing",
    )
    .bind(&job.id)
    .bind(&job.tenant)
    .bind(&job.kind)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Read the bounded queue projection for one tenant. The query uses the
/// migration-owned view rather than scanning the jobs table in each caller.
pub async fn stats(pool: &PgPool, tenant: &str) -> Result<JobStats, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let rows = sqlx::query_as::<_, (String, i64)>(
        "select state, job_count from frankengate_analytics.job_queue_stats\
         where tenant_id = $1",
    )
    .bind(tenant)
    .fetch_all(&mut *tx)
    .await?;
    tx.commit().await?;

    let mut result = JobStats::default();
    for (state, count) in rows {
        let count = usize::try_from(count).unwrap_or(usize::MAX);
        match state.as_str() {
            "queued" => result.queued = count,
            "leased" => result.leased = count,
            "cancelled" => result.cancelled = count,
            "completed" => result.completed = count,
            "failed" => result.failed = count,
            _ => {}
        }
    }
    Ok(result)
}

/// Atomically claim one queued job for a worker. `SKIP LOCKED` lets replicas
/// claim in parallel without a central coordinator or duplicate delivery.
pub async fn lease_next(
    pool: &PgPool,
    tenant: &str,
    worker: &str,
    lease_seconds: i64,
) -> Result<Option<LeaseClaim>, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let row = sqlx::query_as::<_, (String, String, i32)>(
        "select id, kind, attempt from frankengate_analytics.jobs\
         where tenant_id = $1 and state = 'queued'\
         order by created_at, id for update skip locked limit 1",
    )
    .bind(tenant)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((id, kind, attempt)) = row else {
        tx.commit().await?;
        return Ok(None);
    };
    let next_attempt = attempt + 1;
    sqlx::query(
        "update frankengate_analytics.jobs\
         set state = 'leased', attempt = $1, worker_id = $2,\
             lease_until = now() + make_interval(secs => $3)\
         where id = $4 and tenant_id = $5",
    )
    .bind(next_attempt)
    .bind(worker)
    .bind(lease_seconds as f64)
    .bind(&id)
    .bind(tenant)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(Some(LeaseClaim {
        id,
        tenant: tenant.to_owned(),
        kind,
        attempt: next_attempt,
    }))
}

/// Extend a lease only when the current worker still owns it.
pub async fn renew_lease(
    pool: &PgPool,
    tenant: &str,
    job_id: &str,
    worker: &str,
    lease_seconds: i64,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs\
         set lease_until = now() + make_interval(secs => $1)\
         where id = $2 and tenant_id = $3 and state = 'leased' and worker_id = $4",
    )
    .bind(lease_seconds as f64)
    .bind(job_id)
    .bind(tenant)
    .bind(worker)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Complete a lease only when the current worker owns it; clearing lease
/// projection columns is required by the database invariant.
pub async fn complete_job(
    pool: &PgPool,
    tenant: &str,
    job_id: &str,
    worker: &str,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set state = 'completed',\
         worker_id = null, lease_until = null, error_code = null\
         where id = $1 and tenant_id = $2 and state = 'leased' and worker_id = $3",
    )
    .bind(job_id)
    .bind(tenant)
    .bind(worker)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Record a bounded terminal error for an owned lease.
pub async fn fail_job(
    pool: &PgPool,
    tenant: &str,
    job_id: &str,
    worker: &str,
    error_code: &str,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set state = 'failed',\
         worker_id = null, lease_until = null, error_code = $1\
         where id = $2 and tenant_id = $3 and state = 'leased' and worker_id = $4",
    )
    .bind(error_code)
    .bind(job_id)
    .bind(tenant)
    .bind(worker)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Return expired leases to the queued state for another replica. The update
/// is tenant-scoped and clears the lease projection required by the schema.
pub async fn reap_expired(pool: &PgPool, tenant: &str) -> Result<u64, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set state = 'queued',\
         worker_id = null, lease_until = null\
         where tenant_id = $1 and state = 'leased' and lease_until < now()",
    )
    .bind(tenant)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected())
}

/// Release all leases owned by a draining worker so another replica can pick
/// them up immediately during a graceful Kubernetes termination.
pub async fn drain_worker(pool: &PgPool, tenant: &str, worker: &str) -> Result<u64, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set state = 'queued',\
         worker_id = null, lease_until = null\
         where tenant_id = $1 and state = 'leased' and worker_id = $2",
    )
    .bind(tenant)
    .bind(worker)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected())
}

/// Create a queued replay only from a terminal job in the same tenant. The
/// replay id is the idempotency key, and `replay_of` preserves lineage.
pub async fn replay_job(pool: &PgPool, job: &ReplayJob) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(&job.tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "insert into frankengate_analytics.jobs (id, tenant_id, kind, state, replay_of)\
         select $1, tenant_id, kind, 'queued', id\
         from frankengate_analytics.jobs\
         where id = $2 and tenant_id = $3\
           and state in ('completed', 'cancelled', 'failed')\
         on conflict (id) do nothing",
    )
    .bind(&job.replay_id)
    .bind(&job.source_job_id)
    .bind(&job.tenant)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Persist a bounded worker checkpoint only for the current lease owner.
pub async fn checkpoint_job(
    pool: &PgPool,
    tenant: &str,
    job_id: &str,
    worker: &str,
    checkpoint: &str,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set checkpoint = $1\
         where id = $2 and tenant_id = $3 and state = 'leased'\
           and worker_id = $4 and length($1) <= 65536",
    )
    .bind(checkpoint)
    .bind(job_id)
    .bind(tenant)
    .bind(worker)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

pub async fn create_experiment(
    pool: &PgPool,
    experiment: &Experiment,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(&experiment.tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "insert into frankengate_analytics.experiments (id, tenant_id, actor_id, revision)\
         values ($1, $2, $3, $4) on conflict (id) do nothing",
    )
    .bind(&experiment.id)
    .bind(&experiment.tenant)
    .bind(&experiment.actor)
    .bind(&experiment.revision)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

pub async fn create_run(pool: &PgPool, tenant: &str, run: &Run) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "insert into frankengate_analytics.runs\
         (id, tenant_id, experiment_id, dataset_revision, evaluator_revision, model_revision, prompt_revision)\
         values ($1, $2, $3, $4, $5, $6, $7) on conflict (id) do nothing",
    )
    .bind(&run.id)
    .bind(tenant)
    .bind(&run.experiment_id)
    .bind(&run.dataset_revision)
    .bind(&run.evaluator_revision)
    .bind(&run.model_revision)
    .bind(&run.prompt_revision)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Return a bounded, deterministic run projection for one tenant. The tenant
/// setting is established inside the same transaction as the query so RLS
/// remains authoritative even when this endpoint is called by a dashboard.
pub async fn list_runs(
    pool: &PgPool,
    tenant: &str,
    limit: i64,
) -> Result<Vec<RunSummary>, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let rows = sqlx::query_as::<
        _,
        (
            String,
            String,
            String,
            String,
            String,
            String,
            Option<String>,
            String,
        ),
    >(
        "select id, experiment_id, dataset_revision, evaluator_revision, model_revision,
                prompt_revision, terminal_outcome, created_at::text
           from frankengate_analytics.runs
          where tenant_id = $1
          order by created_at desc, id desc
          limit $2",
    )
    .bind(tenant)
    .bind(limit.clamp(1, 100))
    .fetch_all(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(rows
        .into_iter()
        .map(
            |(
                id,
                experiment_id,
                dataset_revision,
                evaluator_revision,
                model_revision,
                prompt_revision,
                terminal_outcome,
                created_at,
            )| RunSummary {
                id,
                experiment_id,
                dataset_revision,
                evaluator_revision,
                model_revision,
                prompt_revision,
                terminal_outcome,
                created_at,
            },
        )
        .collect())
}

pub async fn record_evaluation(
    pool: &PgPool,
    tenant: &str,
    result: &EvaluationResult,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let inserted = sqlx::query(
        "insert into frankengate_analytics.evaluation_results\
         (run_id, example_id, evaluator_revision, score)\
         values ($1, $2, $3, $4::jsonb) on conflict do nothing",
    )
    .bind(&result.run_id)
    .bind(&result.example_id)
    .bind(&result.evaluator_revision)
    .bind(&result.score)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(inserted.rows_affected() == 1)
}

pub async fn record_artifact(
    pool: &PgPool,
    tenant: &str,
    artifact: &ArtifactManifest,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let inserted = sqlx::query(
        "insert into frankengate_analytics.artifact_manifests\
         (run_id, digest, media_type, object_uri)\
         values ($1, $2, $3, $4) on conflict do nothing",
    )
    .bind(&artifact.run_id)
    .bind(&artifact.digest)
    .bind(&artifact.media_type)
    .bind(&artifact.object_uri)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(inserted.rows_affected() == 1)
}

/// Return bounded artifact lineage metadata for a tenant and run. Tenant
/// ownership is established through the authoritative runs row; artifact
/// bytes are never read by this control-plane projection.
pub async fn list_artifacts(
    pool: &PgPool,
    tenant: &str,
    run_id: &str,
    limit: i64,
) -> Result<Vec<ArtifactSummary>, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let rows = sqlx::query_as::<_, (String, String, String, String, String)>(
        "select a.run_id, a.digest, a.media_type, a.object_uri, a.created_at::text
           from frankengate_analytics.artifact_manifests a
           join frankengate_analytics.runs r on r.id = a.run_id
          where r.tenant_id = $1 and a.run_id = $2
          order by a.created_at desc, a.digest desc
          limit $3",
    )
    .bind(tenant)
    .bind(run_id)
    .bind(limit.clamp(1, 100))
    .fetch_all(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(rows
        .into_iter()
        .map(
            |(run_id, digest, media_type, object_uri, created_at)| ArtifactSummary {
                run_id,
                digest,
                media_type,
                object_uri,
                created_at,
            },
        )
        .collect())
}

/// Persist one worker attempt with optional terminal outcome evidence.
pub async fn record_attempt(
    pool: &PgPool,
    tenant: &str,
    attempt: &RunAttempt,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let outcome = attempt.outcome.as_ref().map(|value| {
        serde_json::json!({
            "protocol_version": value.protocol_version,
            "id": value.id,
            "attempt": value.attempt,
            "terminal": value.terminal,
            "error_code": value.error_code,
        })
    });
    let inserted = sqlx::query(
        "insert into frankengate_analytics.run_attempts\
         (id, tenant_id, run_id, attempt, worker_id, job_id, outcome)\
         values ($1, $2, $3, $4, $5, $6, $7) on conflict do nothing",
    )
    .bind(&attempt.id)
    .bind(tenant)
    .bind(&attempt.run_id)
    .bind(i32::try_from(attempt.attempt).unwrap_or(i32::MAX))
    .bind(&attempt.worker)
    .bind(&attempt.job_id)
    .bind(outcome)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(inserted.rows_affected() == 1)
}

pub async fn cancel_job(pool: &PgPool, tenant: &str, job_id: &str) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set state = 'cancelled',\
         worker_id = null, lease_until = null, error_code = null\
         where id = $1 and tenant_id = $2 and state in ('queued', 'leased')",
    )
    .bind(job_id)
    .bind(tenant)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

pub async fn retry_job(pool: &PgPool, tenant: &str, job_id: &str) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let result = sqlx::query(
        "update frankengate_analytics.jobs set state = 'queued',\
         worker_id = null, lease_until = null, error_code = null\
         where id = $1 and tenant_id = $2 and state = 'failed'",
    )
    .bind(job_id)
    .bind(tenant)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(result.rows_affected() == 1)
}

/// Publish a terminal run outcome without mutating its reproducibility
/// revisions. The outcome is JSON so evaluators can add typed metrics while
/// the run identity remains stable.
pub async fn finish_run(
    pool: &PgPool,
    tenant: &str,
    run_id: &str,
    outcome: &str,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("select set_config('app.tenant_id', $1, true)")
        .bind(tenant)
        .execute(&mut *tx)
        .await?;
    let updated = sqlx::query(
        "update frankengate_analytics.runs set terminal_outcome = $1\
         where id = $2 and tenant_id = $3 and terminal_outcome is null",
    )
    .bind(outcome)
    .bind(run_id)
    .bind(tenant)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(updated.rows_affected() == 1)
}

#[cfg(test)]
mod integration_tests {
    use super::*;
    use crate::SubmitJob;

    /// Runs only when DATABASE_URL is supplied. This keeps the default unit
    /// suite hermetic while giving CI/Kubernetes Postgres jobs a real proof of
    /// migration, tenant isolation, lease ownership, and terminal cleanup.
    #[tokio::test]
    async fn durable_job_lifecycle_is_tenant_scoped() -> Result<(), sqlx::Error> {
        if std::env::var_os("DATABASE_URL").is_none() {
            eprintln!("skipping durable DB test: DATABASE_URL is not set");
            return Ok(());
        }

        let pool = connect_from_env().await?.expect("DATABASE_URL was set");
        let suffix = format!(
            "{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("clock before epoch")
                .as_nanos()
        );
        let tenant = format!("integration-{suffix}");
        let other_tenant = format!("other-{suffix}");
        let job_id = format!("job-{suffix}");

        assert!(
            submit_job(
                &pool,
                &SubmitJob {
                    protocol_version: crate::PROTOCOL_VERSION,
                    id: job_id.clone(),
                    tenant: tenant.clone(),
                    kind: "integration".into(),
                },
            )
            .await?
        );
        assert!(
            !submit_job(
                &pool,
                &SubmitJob {
                    protocol_version: crate::PROTOCOL_VERSION,
                    id: job_id.clone(),
                    tenant: tenant.clone(),
                    kind: "integration".into(),
                },
            )
            .await?
        );

        let claim = lease_next(&pool, &tenant, "worker-a", 30)
            .await?
            .expect("queued job should be claimable");
        assert_eq!(claim.id, job_id);
        assert_eq!(claim.attempt, 1);
        assert!(renew_lease(&pool, &tenant, &job_id, "worker-a", 30).await?);
        assert!(!complete_job(&pool, &tenant, &job_id, "worker-b").await?);
        assert!(complete_job(&pool, &tenant, &job_id, "worker-a").await?);

        let own = stats(&pool, &tenant).await?;
        assert_eq!(own.completed, 1);
        let other = stats(&pool, &other_tenant).await?;
        assert_eq!(other, JobStats::default());

        sqlx::query("delete from frankengate_analytics.jobs where id = $1")
            .bind(&job_id)
            .execute(&pool)
            .await?;
        pool.close().await;
        Ok(())
    }
}
