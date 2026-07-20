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
}
