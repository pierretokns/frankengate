//! Durable Postgres boundary for the isolated analytics control plane.

use sqlx::{postgres::PgPoolOptions, PgPool, Postgres, Transaction};

#[derive(Clone)]
pub struct Database {
    pool: PgPool,
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
}
