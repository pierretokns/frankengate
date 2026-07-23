fn main() {
    if std::env::args().any(|arg| arg == "--check") {
        frankengate_analytics_control::contract_self_check()
            .expect("analytics control-plane contract self-check failed");
        println!(
            "FrankenGate analytics contract v{}: OK",
            frankengate_analytics_control::PROTOCOL_VERSION
        );
    } else if std::env::args().any(|arg| arg == "--serve") {
        serve();
    } else {
        println!("FrankenGate analytics control-plane contract slice");
        println!("Run with --check to validate the leased-job protocol.");
    }
}

fn serve() {
    use std::net::TcpListener;
    use std::sync::Arc;

    // Do not advertise readiness until the control-plane contract itself is
    // executable.  This is intentionally a boot fence: a future durable
    // store must replace this check with its migration/connectivity check.
    frankengate_analytics_control::contract_self_check()
        .expect("analytics control-plane boot fence failed");

    // When configured, Postgres is part of the readiness fence. This avoids
    // advertising a healthy pod that cannot persist or consume jobs.
    let runtime = tokio::runtime::Runtime::new().expect("tokio runtime failed");
    let database = runtime
        .block_on(frankengate_analytics_control::db::connect_from_env())
        .expect("analytics control-plane database boot fence failed");

    let port = std::env::var("PORT").unwrap_or_else(|_| "8081".into());
    let listener = TcpListener::bind(("0.0.0.0", port.parse::<u16>().expect("PORT must be a u16")))
        .expect("analytics control-plane listener failed to bind");
    let store = Arc::new(frankengate_analytics_control::JobStore::default());
    println!("FrankenGate analytics control plane listening on 0.0.0.0:{port}");
    for stream in listener.incoming().flatten() {
        let store = Arc::clone(&store);
        let database = database.clone();
        std::thread::spawn(|| handle_connection(stream, store, database));
    }
}

fn handle_connection(
    mut stream: std::net::TcpStream,
    store: std::sync::Arc<frankengate_analytics_control::JobStore>,
    database: Option<sqlx::PgPool>,
) {
    use std::io::{Read, Write};
    // Health probes are tiny and bounded.  Do not let an accepted but idle
    // socket consume a thread forever (especially during a probe storm).
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(2)));
    let mut request = [0_u8; 1024];
    let size = stream.read(&mut request).unwrap_or(0);
    let request_line = std::str::from_utf8(&request[..size]).unwrap_or("");
    let method = request_line.split_whitespace().next().unwrap_or("");
    let target = request_line.split_whitespace().nth(1).unwrap_or("/");
    let (path, query) = target.split_once('?').unwrap_or((target, ""));
    if path.starts_with("/v1/") && !worker_authorized(request_line) {
        let response = "HTTP/1.1 401 Unauthorized\r\nContent-Type: text/plain\r\nContent-Length: 13\r\nConnection: close\r\n\r\nunauthorized\n";
        let _ = stream.write_all(response.as_bytes());
        return;
    }
    let (status, content_type, body) = match path {
        "/healthz" => ("200 OK", "text/plain", "ok\n".to_string()),
        "/readyz" => {
            // Liveness only proves that the process is accepting sockets. Readiness
            // must also prove that the durable control-plane store is reachable;
            // otherwise Kubernetes can route jobs to a pod that cannot persist
            // leases, completions, or checkpoints after a database outage.
            match database.as_ref() {
                Some(pool) => {
                    let reachable = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime.block_on(sqlx::query("SELECT 1").execute(pool)).ok()
                        })
                        .is_some();
                    if reachable {
                        ("200 OK", "text/plain", "ok\n".to_string())
                    } else {
                        (
                            "503 Service Unavailable",
                            "text/plain",
                            "database unavailable\n".to_string(),
                        )
                    }
                }
                None => (
                    "503 Service Unavailable",
                    "text/plain",
                    "database unavailable\n".to_string(),
                ),
            }
        }
        "/version" => (
            "200 OK",
            "text/plain",
            format!(
                "protocol_version={}\n",
                frankengate_analytics_control::PROTOCOL_VERSION
            ),
        ),
        "/metrics" => {
            let stats = store.stats();
            (
                "200 OK",
                "text/plain; version=0.0.4",
                format!(
                    "# HELP frankengate_analytics_jobs Number of analytics jobs by state.\n# TYPE frankengate_analytics_jobs gauge\nfrankengate_analytics_jobs{{state=\"queued\"}} {}\nfrankengate_analytics_jobs{{state=\"leased\"}} {}\nfrankengate_analytics_jobs{{state=\"cancelled\"}} {}\nfrankengate_analytics_jobs{{state=\"completed\"}} {}\nfrankengate_analytics_jobs{{state=\"failed\"}} {}\n",
                    stats.queued,
                    stats.leased,
                    stats.cancelled,
                    stats.completed,
                    stats.failed
                ),
            )
        }
        _ => ("404 Not Found", "text/plain", "not found\n".to_string()),
    };
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
}

fn query_param<'a>(query: &'a str, name: &str) -> Option<&'a str> {
    query
        .split('&')
        .find_map(|pair| {
            pair.strip_prefix(name)
                .and_then(|value| value.strip_prefix('='))
        })
        .filter(|value| !value.is_empty())
}

/// If ANALYTICS_WORKER_TOKEN is configured, require a matching bearer token
/// on every control-plane API request. Leaving it unset is intentionally
/// development-friendly; production Helm deployments should provide it via a
/// Secret and still enforce network/service-account policy at the cluster edge.
fn worker_authorized(request: &str) -> bool {
    let Some(expected) = std::env::var_os("ANALYTICS_WORKER_TOKEN") else {
        return true;
    };
    let expected = expected.to_string_lossy();
    let supplied = request.lines().find_map(|line| {
        line.strip_prefix("Authorization:")
            .or_else(|| line.strip_prefix("authorization:"))
            .map(str::trim)
            .and_then(|value| value.strip_prefix("Bearer "))
    });
    let Some(supplied) = supplied else {
        return false;
    };
    // Compare every byte to avoid an early-exit timing signal. Length is
    // included in the accumulator so short tokens are not accepted.
    let mut diff = expected.len() ^ supplied.len();
    for index in 0..expected.len().max(supplied.len()) {
        diff |= expected.as_bytes().get(index).copied().unwrap_or(0) as usize
            ^ supplied.as_bytes().get(index).copied().unwrap_or(0) as usize;
    }
    diff == 0
}

#[cfg(test)]
mod tests {
    use super::{query_param, worker_authorized};

    #[test]
    fn query_params_are_exact_and_empty_values_fail_closed() {
        let query = "tenant=team-a&worker=pod-1&job_id=j-7&tenant_extra=wrong";
        assert_eq!(query_param(query, "tenant"), Some("team-a"));
        assert_eq!(query_param(query, "worker"), Some("pod-1"));
        assert_eq!(query_param(query, "job_id"), Some("j-7"));
        assert_eq!(query_param(query, "tenant_extra"), Some("wrong"));
        assert_eq!(query_param("tenant=&worker=pod-1", "tenant"), None);
        assert_eq!(query_param(query, "missing"), None);
    }

    #[test]
    fn worker_authorization_requires_bearer_when_configured() {
        std::env::set_var("ANALYTICS_WORKER_TOKEN", "test-token");
        assert!(!worker_authorized("GET /v1/jobs HTTP/1.1\r\n"));
        assert!(!worker_authorized(
            "GET /v1/jobs HTTP/1.1\r\nAuthorization: Bearer wrong\r\n"
        ));
        assert!(worker_authorized(
            "GET /v1/jobs HTTP/1.1\r\nAuthorization: Bearer test-token\r\n"
        ));
        std::env::remove_var("ANALYTICS_WORKER_TOKEN");
    }
}
