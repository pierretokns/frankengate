//! Durable Postgres boundary for the isolated analytics control plane.

use sqlx::{postgres::PgPoolOptions, PgPool, Postgres, Transaction};

#[derive(Clone)]
pub struct Database {
    pool: PgPool,
}

#[derive(Debug, Clone, PartialEq, Eq, sqlx::FromRow)]
pub struct ExperimentRow {
    pub id: String,
    pub tenant_id: String,
    pub actor_id: String,
    pub revision: String,
}

#[derive(Debug, Clone, PartialEq, Eq, sqlx::FromRow)]
pub struct RunRow {
    pub id: String,
    pub tenant_id: String,
    pub experiment_id: String,
    pub dataset_revision: String,
    pub evaluator_revision: String,
    pub model_revision: String,
    pub prompt_revision: String,
}

#[derive(Debug, Clone, PartialEq, Eq, sqlx::FromRow)]
pub struct ArtifactRow {
    pub run_id: String,
    pub digest: String,
    pub media_type: String,
    pub object_uri: String,
}

#[derive(Debug, Clone, PartialEq, Eq, sqlx::FromRow)]
pub struct EvaluationRow {
    pub run_id: String,
    pub example_id: String,
    pub evaluator_revision: String,
    pub score: sqlx::types::Json<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Eq, sqlx::FromRow)]
pub struct JobRow {
    pub id: String,
    pub tenant_id: String,
    pub kind: String,
    pub state: String,
    pub attempt: i32,
    pub replay_of: Option<String>,
}

impl Database {
    pub async fn connect(url: &str, max_connections: u32) -> Result<Self, sqlx::Error> {
        let pool = PgPoolOptions::new()
            .max_connections(max_connections.max(1))
            .acquire_timeout(std::time::Duration::from_secs(2))
            .connect(url)
            .await?;
        Ok(Self { pool })
    }

    pub async fn migrate(&self) -> Result<(), sqlx::migrate::MigrateError> {
        sqlx::migrate!().run(&self.pool).await
    }

    pub async fn ready(&self) -> Result<(), sqlx::Error> {
        sqlx::query("select 1")
            .execute(&self.pool)
            .await
            .map(|_| ())
    }

    /// Starts a tenant-fenced transaction. Callers must commit or roll back it.
    pub async fn begin_tenant(
        &self,
        tenant: &str,
    ) -> Result<Transaction<'_, Postgres>, sqlx::Error> {
        let mut tx = self.pool.begin().await?;
        sqlx::query("select set_config('app.tenant_id', $1, true)")
            .bind(tenant)
            .execute(&mut *tx)
            .await?;
        Ok(tx)
    }

    pub async fn create_experiment(
        &self,
        tenant: &str,
        id: &str,
        actor: &str,
        revision: &str,
    ) -> Result<ExperimentRow, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, ExperimentRow>(
            "insert into frankengate_analytics.experiments (id, tenant_id, actor_id, revision)\
             values ($1, $2, $3, $4) returning id, tenant_id, actor_id, revision",
        )
        .bind(id)
        .bind(tenant)
        .bind(actor)
        .bind(revision)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn list_experiments(
        &self,
        tenant: &str,
        limit: i64,
    ) -> Result<Vec<ExperimentRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let rows = sqlx::query_as::<_, ExperimentRow>(
            "select id, tenant_id, actor_id, revision\
             from frankengate_analytics.experiments\
             order by created_at asc, id asc limit $1",
        )
        .bind(limit.clamp(1, 100))
        .fetch_all(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(rows)
    }

    pub async fn create_run(
        &self,
        tenant: &str,
        id: &str,
        experiment_id: &str,
        dataset_revision: &str,
        evaluator_revision: &str,
        model_revision: &str,
        prompt_revision: &str,
    ) -> Result<RunRow, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, RunRow>(
            "insert into frankengate_analytics.runs\
             (id, tenant_id, experiment_id, dataset_revision, evaluator_revision, model_revision, prompt_revision)\
             values ($1, $2, $3, $4, $5, $6, $7)\
             returning id, tenant_id, experiment_id, dataset_revision, evaluator_revision, model_revision, prompt_revision",
        )
        .bind(id)
        .bind(tenant)
        .bind(experiment_id)
        .bind(dataset_revision)
        .bind(evaluator_revision)
        .bind(model_revision)
        .bind(prompt_revision)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn list_runs(&self, tenant: &str, limit: i64) -> Result<Vec<RunRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let rows = sqlx::query_as::<_, RunRow>(
            "select id, tenant_id, experiment_id, dataset_revision, evaluator_revision, model_revision, prompt_revision\
             from frankengate_analytics.runs\
             order by created_at asc, id asc limit $1",
        )
        .bind(limit.clamp(1, 100))
        .fetch_all(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(rows)
    }

    pub async fn record_artifact(
        &self,
        tenant: &str,
        run_id: &str,
        digest: &str,
        media_type: &str,
        object_uri: &str,
    ) -> Result<ArtifactRow, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, ArtifactRow>(
            "insert into frankengate_analytics.artifact_manifests\
             (run_id, digest, media_type, object_uri) values ($1, $2, $3, $4)\
             returning run_id, digest, media_type, object_uri",
        )
        .bind(run_id)
        .bind(digest)
        .bind(media_type)
        .bind(object_uri)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn list_artifacts(
        &self,
        tenant: &str,
        run_id: &str,
        limit: i64,
    ) -> Result<Vec<ArtifactRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let rows = sqlx::query_as::<_, ArtifactRow>(
            "select a.run_id, a.digest, a.media_type, a.object_uri\
             from frankengate_analytics.artifact_manifests a\
             join frankengate_analytics.runs r on r.id = a.run_id\
             where a.run_id = $1 order by a.created_at asc, a.digest asc limit $2",
        )
        .bind(run_id)
        .bind(limit.clamp(1, 100))
        .fetch_all(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(rows)
    }

    pub async fn record_evaluation(
        &self,
        tenant: &str,
        run_id: &str,
        example_id: &str,
        evaluator_revision: &str,
        score: serde_json::Value,
    ) -> Result<EvaluationRow, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, EvaluationRow>(
            "insert into frankengate_analytics.evaluation_results\
             (run_id, example_id, evaluator_revision, score) values ($1, $2, $3, $4)\
             returning run_id, example_id, evaluator_revision, score",
        )
        .bind(run_id)
        .bind(example_id)
        .bind(evaluator_revision)
        .bind(sqlx::types::Json(score))
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn list_evaluations(
        &self,
        tenant: &str,
        run_id: &str,
        limit: i64,
    ) -> Result<Vec<EvaluationRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let rows = sqlx::query_as::<_, EvaluationRow>(
            "select e.run_id, e.example_id, e.evaluator_revision, e.score\
             from frankengate_analytics.evaluation_results e\
             join frankengate_analytics.runs r on r.id = e.run_id\
             where e.run_id = $1 order by e.example_id asc, e.evaluator_revision asc limit $2",
        )
        .bind(run_id)
        .bind(limit.clamp(1, 100))
        .fetch_all(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(rows)
    }

    pub async fn replay_job(
        &self,
        tenant: &str,
        replay_id: &str,
        source_id: &str,
    ) -> Result<JobRow, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, JobRow>(
            "insert into frankengate_analytics.jobs (id, tenant_id, kind, state, replay_of)\
             select $1, tenant_id, kind, 'queued', id\
             from frankengate_analytics.jobs\
             where id = $2 and tenant_id = $3 and state in ('completed', 'failed', 'cancelled')\
             returning id, tenant_id, kind, state, attempt, replay_of",
        )
        .bind(replay_id)
        .bind(source_id)
        .bind(tenant)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn submit_job(
        &self,
        tenant: &str,
        id: &str,
        kind: &str,
    ) -> Result<JobRow, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, JobRow>(
            "insert into frankengate_analytics.jobs (id, tenant_id, kind, state)\
             values ($1, $2, $3, 'queued')\
             returning id, tenant_id, kind, state, attempt, replay_of",
        )
        .bind(id)
        .bind(tenant)
        .bind(kind)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn lease_next_job(
        &self,
        tenant: &str,
        worker_id: &str,
        lease_seconds: i64,
    ) -> Result<Option<JobRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, JobRow>(
            "with candidate as (\
               select id from frankengate_analytics.jobs\
               where tenant_id = $1 and (state = 'queued' or (state = 'leased' and lease_until < now()))\
               order by created_at asc, id asc for update skip locked limit 1\
             )\
             update frankengate_analytics.jobs j\
             set state = 'leased', worker_id = $2, lease_until = now() + ($3 * interval '1 second'),\
                 attempt = j.attempt + 1, updated_at = now()\
             from candidate where j.id = candidate.id\
             returning j.id, j.tenant_id, j.kind, j.state, j.attempt, j.replay_of",
        )
        .bind(tenant)
        .bind(worker_id)
        .bind(lease_seconds.max(1))
        .fetch_optional(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn renew_job(
        &self,
        tenant: &str,
        job_id: &str,
        worker_id: &str,
        lease_seconds: i64,
    ) -> Result<Option<JobRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, JobRow>(
            "update frankengate_analytics.jobs\
             set lease_until = now() + ($4 * interval '1 second'), updated_at = now()\
             where id = $1 and tenant_id = $2 and worker_id = $3 and state = 'leased'\
             returning id, tenant_id, kind, state, attempt, replay_of",
        )
        .bind(job_id)
        .bind(tenant)
        .bind(worker_id)
        .bind(lease_seconds.max(1))
        .fetch_optional(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn complete_job(
        &self,
        tenant: &str,
        job_id: &str,
        worker_id: &str,
    ) -> Result<Option<JobRow>, sqlx::Error> {
        self.finish_job(tenant, job_id, worker_id, "completed", None)
            .await
    }

    pub async fn fail_job(
        &self,
        tenant: &str,
        job_id: &str,
        worker_id: &str,
        error_code: &str,
    ) -> Result<Option<JobRow>, sqlx::Error> {
        self.finish_job(tenant, job_id, worker_id, "failed", Some(error_code))
            .await
    }

    async fn finish_job(
        &self,
        tenant: &str,
        job_id: &str,
        worker_id: &str,
        state: &str,
        error_code: Option<&str>,
    ) -> Result<Option<JobRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, JobRow>(
            "update frankengate_analytics.jobs\
             set state = $4, worker_id = null, lease_until = null, error_code = $5, updated_at = now()\
             where id = $1 and tenant_id = $2 and worker_id = $3 and state = 'leased'\
             returning id, tenant_id, kind, state, attempt, replay_of",
        )
        .bind(job_id)
        .bind(tenant)
        .bind(worker_id)
        .bind(state)
        .bind(error_code)
        .fetch_optional(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    pub async fn cancel_job(
        &self,
        tenant: &str,
        job_id: &str,
    ) -> Result<Option<JobRow>, sqlx::Error> {
        let mut tx = self.begin_tenant(tenant).await?;
        let row = sqlx::query_as::<_, JobRow>(
            "update frankengate_analytics.jobs\
             set state = 'cancelled', worker_id = null, lease_until = null, updated_at = now()\
             where id = $1 and tenant_id = $2 and state in ('queued', 'leased')\
             returning id, tenant_id, kind, state, attempt, replay_of",
        )
        .bind(job_id)
        .bind(tenant)
        .fetch_optional(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(row)
    }
}
