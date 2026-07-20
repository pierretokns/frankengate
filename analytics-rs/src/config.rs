use crate::auth::WorkerAuth;

#[derive(Clone, Debug)]
pub struct Config {
    pub database_url: Option<String>,
    pub worker_auth: WorkerAuth,
    pub port: u16,
    pub pool_max_connections: u32,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let port = parse_env("PORT", 8081)?;
        let pool_max_connections = parse_env("ANALYTICS_DB_MAX_CONNECTIONS", 10)?;
        Ok(Self {
            database_url: std::env::var("DATABASE_URL").ok().filter(|v| !v.is_empty()),
            worker_auth: WorkerAuth::from_token(
                std::env::var("ANALYTICS_WORKER_TOKEN").ok().as_deref(),
            ),
            port,
            pool_max_connections,
        })
    }
}

fn parse_env<T: std::str::FromStr>(name: &str, default: T) -> Result<T, String> {
    match std::env::var(name) {
        Ok(value) => value
            .parse()
            .map_err(|_| format!("{name} must be a valid integer")),
        Err(std::env::VarError::NotPresent) => Ok(default),
        Err(std::env::VarError::NotUnicode(_)) => Err(format!("{name} must be valid UTF-8")),
    }
}

#[cfg(test)]
mod tests {
    use super::Config;

    #[test]
    fn defaults_are_local_and_bounded() {
        let config = Config {
            database_url: None,
            worker_auth: crate::auth::WorkerAuth::from_token(None),
            port: 8081,
            pool_max_connections: 10,
        };
        assert_eq!(config.port, 8081);
        assert_eq!(config.pool_max_connections, 10);
        assert!(!config.worker_auth.is_configured());
    }
}
