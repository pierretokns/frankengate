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

    let config = frankengate_analytics_control::config::Config::from_env()
        .unwrap_or_else(|error| panic!("analytics control-plane configuration failed: {error}"));
    let runtime = Arc::new(
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("analytics control-plane runtime failed to start"),
    );
    let database = config.database_url.as_deref().map(|url| {
        let database = runtime
            .block_on(frankengate_analytics_control::database::Database::connect(
                url,
                config.pool_max_connections,
            ))
            .unwrap_or_else(|error| panic!("analytics database connection failed: {error}"));
        runtime
            .block_on(database.migrate())
            .unwrap_or_else(|error| panic!("analytics database migration failed: {error}"));
        database
    });
    let database = Arc::new(database);
    let listener = TcpListener::bind(("0.0.0.0", config.port))
        .expect("analytics control-plane listener failed to bind");
    println!(
        "FrankenGate analytics control plane listening on 0.0.0.0:{}",
        config.port
    );
    for stream in listener.incoming().flatten() {
        let auth = config.worker_auth.clone();
        let database = database.clone();
        let runtime = runtime.clone();
        std::thread::spawn(move || handle_connection(stream, &auth, database, runtime));
    }
}

fn handle_connection(
    mut stream: std::net::TcpStream,
    auth: &frankengate_analytics_control::auth::WorkerAuth,
    database: std::sync::Arc<Option<frankengate_analytics_control::database::Database>>,
    runtime: std::sync::Arc<tokio::runtime::Runtime>,
) {
    use std::io::{Read, Write};
    // Health probes are tiny and bounded.  Do not let an accepted but idle
    // socket consume a thread forever (especially during a probe storm).
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(2)));
    let mut request = [0_u8; 1024];
    let size = stream.read(&mut request).unwrap_or(0);
    let parsed = frankengate_analytics_control::http::parse_request(&request[..size]);
    let path = parsed.as_ref().map(|request| request.path).unwrap_or("/");
    let route = frankengate_analytics_control::http::route_for(path);
    let authorized = parsed.as_ref().is_some_and(|request| {
        frankengate_analytics_control::http::authorize_route(route, auth, request.authorization)
    });
    if !authorized {
        let body = "unauthorized\n";
        let response = format!(
            "HTTP/1.1 401 Unauthorized\r\nContent-Type: text/plain\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        );
        let _ = stream.write_all(response.as_bytes());
        return;
    }
    let (status, content_type, body) = match path {
        "/healthz" => ("200 OK", "text/plain", "ok\n".to_string()),
        "/readyz" => readiness_response(),
        "/version" => (
            "200 OK",
            "text/plain",
            format!(
                "protocol_version={}\n",
                frankengate_analytics_control::PROTOCOL_VERSION
            ),
        ),
        "/v1/jobs"
        | "/v1/jobs/stats"
        | "/v1/jobs/lease"
        | "/v1/jobs/renew"
        | "/v1/jobs/complete"
        | "/v1/jobs/fail"
        | "/v1/jobs/cancel"
        | "/v1/jobs/checkpoint"
        | "/v1/jobs/replay"
        | "/v1/jobs/drain" => governed_response(parsed.as_ref(), &database, &runtime),
        _ => ("404 Not Found", "text/plain", "not found\n".to_string()),
    };
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
}

fn governed_response(
    request: Option<&frankengate_analytics_control::http::Request<'_>>,
    database: &std::sync::Arc<Option<frankengate_analytics_control::database::Database>>,
    runtime: &std::sync::Arc<tokio::runtime::Runtime>,
) -> (&'static str, &'static str, String) {
    let Some(request) = request else {
        return (
            "400 Bad Request",
            "text/plain",
            "malformed request\n".into(),
        );
    };
    let Some(tenant) = request.tenant.filter(|tenant| !tenant.is_empty()) else {
        return (
            "400 Bad Request",
            "text/plain",
            "x-tenant-id is required\n".into(),
        );
    };
    let Some(database) = database.as_ref() else {
        return (
            "503 Service Unavailable",
            "text/plain",
            "database is not configured\n".into(),
        );
    };
    if request.path == "/v1/jobs/stats" {
        return match runtime.block_on(database.job_stats(tenant)) {
            Ok(stats) => (
                "200 OK",
                "application/json",
                serde_json::json!({
                    "queued": stats.queued, "leased": stats.leased, "completed": stats.completed,
                    "failed": stats.failed, "cancelled": stats.cancelled,
                })
                .to_string(),
            ),
            Err(_) => (
                "500 Internal Server Error",
                "text/plain",
                "job stats failed\n".into(),
            ),
        };
    }
    if request.path == "/v1/jobs/lease" {
        if request.method != "POST" {
            return (
                "405 Method Not Allowed",
                "text/plain",
                "only POST is supported\n".into(),
            );
        }
        let Some(worker_id) = request.worker_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-worker-id is required\n".into(),
            );
        };
        let lease_seconds = request
            .lease_seconds
            .and_then(|value| value.parse::<i64>().ok())
            .unwrap_or(30)
            .clamp(1, 3600);
        return match runtime.block_on(database.lease_next_job(tenant, worker_id, lease_seconds)) {
            Ok(Some(job)) => (
                "200 OK",
                "application/json",
                serde_json::json!({
                    "id": job.id, "tenant_id": job.tenant_id, "kind": job.kind,
                    "state": job.state, "attempt": job.attempt, "replay_of": job.replay_of,
                })
                .to_string(),
            ),
            Ok(None) => ("204 No Content", "application/json", String::new()),
            Err(_) => ("409 Conflict", "text/plain", "job lease rejected\n".into()),
        };
    }
    if request.path == "/v1/jobs/renew" {
        if request.method != "POST" {
            return (
                "405 Method Not Allowed",
                "text/plain",
                "only POST is supported\n".into(),
            );
        }
        let Some(job_id) = request.job_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-job-id is required\n".into(),
            );
        };
        let Some(worker_id) = request.worker_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-worker-id is required\n".into(),
            );
        };
        let lease_seconds = request
            .lease_seconds
            .and_then(|value| value.parse::<i64>().ok())
            .unwrap_or(30)
            .clamp(1, 3600);
        return match runtime.block_on(database.renew_job(tenant, job_id, worker_id, lease_seconds))
        {
            Ok(Some(job)) => (
                "200 OK",
                "application/json",
                serde_json::json!({
                    "id": job.id, "tenant_id": job.tenant_id, "kind": job.kind,
                    "state": job.state, "attempt": job.attempt, "replay_of": job.replay_of,
                })
                .to_string(),
            ),
            Ok(None) => (
                "409 Conflict",
                "text/plain",
                "lease renewal rejected\n".into(),
            ),
            Err(_) => (
                "500 Internal Server Error",
                "text/plain",
                "lease renewal failed\n".into(),
            ),
        };
    }
    if matches!(
        request.path,
        "/v1/jobs/complete" | "/v1/jobs/fail" | "/v1/jobs/cancel"
    ) {
        if request.method != "POST" {
            return (
                "405 Method Not Allowed",
                "text/plain",
                "only POST is supported\n".into(),
            );
        }
        let Some(job_id) = request.job_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-job-id is required\n".into(),
            );
        };
        let result = match request.path {
            "/v1/jobs/complete" => {
                let Some(worker_id) = request.worker_id.filter(|value| !value.is_empty()) else {
                    return (
                        "400 Bad Request",
                        "text/plain",
                        "x-worker-id is required\n".into(),
                    );
                };
                runtime.block_on(database.complete_job(tenant, job_id, worker_id))
            }
            "/v1/jobs/fail" => {
                let Some(worker_id) = request.worker_id.filter(|value| !value.is_empty()) else {
                    return (
                        "400 Bad Request",
                        "text/plain",
                        "x-worker-id is required\n".into(),
                    );
                };
                let error_code = request.error_code.unwrap_or("worker_failure");
                runtime.block_on(database.fail_job(tenant, job_id, worker_id, error_code))
            }
            _ => runtime.block_on(database.cancel_job(tenant, job_id)),
        };
        return match result {
            Ok(Some(job)) => (
                "200 OK",
                "application/json",
                serde_json::json!({
                    "id": job.id, "tenant_id": job.tenant_id, "kind": job.kind,
                    "state": job.state, "attempt": job.attempt, "replay_of": job.replay_of,
                })
                .to_string(),
            ),
            Ok(None) => (
                "409 Conflict",
                "text/plain",
                "job transition rejected\n".into(),
            ),
            Err(_) => (
                "500 Internal Server Error",
                "text/plain",
                "job transition failed\n".into(),
            ),
        };
    }
    if request.path == "/v1/jobs/checkpoint" {
        if request.method != "POST" {
            return (
                "405 Method Not Allowed",
                "text/plain",
                "only POST is supported\n".into(),
            );
        }
        let Some(job_id) = request.job_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-job-id is required\n".into(),
            );
        };
        let Some(worker_id) = request.worker_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-worker-id is required\n".into(),
            );
        };
        let Some(checkpoint) = request.checkpoint.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-checkpoint is required\n".into(),
            );
        };
        let checkpoint = &checkpoint[..checkpoint.len().min(4096)];
        return match runtime
            .block_on(database.save_checkpoint(tenant, job_id, worker_id, checkpoint))
        {
            Ok(true) => ("204 No Content", "text/plain", String::new()),
            Ok(false) => ("409 Conflict", "text/plain", "checkpoint rejected\n".into()),
            Err(_) => (
                "500 Internal Server Error",
                "text/plain",
                "checkpoint failed\n".into(),
            ),
        };
    }
    if request.path == "/v1/jobs/replay" {
        if request.method != "POST" {
            return (
                "405 Method Not Allowed",
                "text/plain",
                "only POST is supported\n".into(),
            );
        }
        let Some(replay_id) = request.replay_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-replay-id is required\n".into(),
            );
        };
        let Some(source_id) = request.source_job_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-source-job-id is required\n".into(),
            );
        };
        return match runtime.block_on(database.replay_job(tenant, replay_id, source_id)) {
            Ok(job) => (
                "201 Created",
                "application/json",
                serde_json::json!({
                    "id": job.id, "tenant_id": job.tenant_id, "kind": job.kind,
                    "state": job.state, "attempt": job.attempt, "replay_of": job.replay_of,
                })
                .to_string(),
            ),
            Err(_) => ("409 Conflict", "text/plain", "replay rejected\n".into()),
        };
    }
    if request.path == "/v1/jobs/drain" {
        if request.method != "POST" {
            return (
                "405 Method Not Allowed",
                "text/plain",
                "only POST is supported\n".into(),
            );
        }
        let Some(worker_id) = request.worker_id.filter(|value| !value.is_empty()) else {
            return (
                "400 Bad Request",
                "text/plain",
                "x-worker-id is required\n".into(),
            );
        };
        return match runtime.block_on(database.drain_worker(tenant, worker_id)) {
            Ok(released) => (
                "200 OK",
                "application/json",
                serde_json::json!({ "worker_id": worker_id, "released": released }).to_string(),
            ),
            Err(_) => (
                "500 Internal Server Error",
                "text/plain",
                "worker drain failed\n".into(),
            ),
        };
    }
    match request.method {
        "POST" => {
            let Some(id) = request.job_id.filter(|value| !value.is_empty()) else {
                return ("400 Bad Request", "text/plain", "x-job-id is required\n".into());
            };
            let Some(kind) = request.job_kind.filter(|value| !value.is_empty()) else {
                return (
                    "400 Bad Request",
                    "text/plain",
                    "x-job-kind is required\n".into(),
                );
            };
            match runtime.block_on(database.submit_job(tenant, id, kind)) {
                Ok(job) => (
                    "201 Created",
                    "application/json",
                    serde_json::json!({
                        "id": job.id, "tenant_id": job.tenant_id, "kind": job.kind,
                        "state": job.state, "attempt": job.attempt, "replay_of": job.replay_of,
                    })
                    .to_string(),
                ),
                Err(_) => ("409 Conflict", "text/plain", "job submission rejected\n".into()),
            }
        }
        "GET" => match runtime.block_on(database.list_jobs(tenant, 100)) {
            Ok(jobs) => ("200 OK", "application/json", serde_json::to_string(&jobs.iter().map(|job| serde_json::json!({
                "id": job.id, "tenant_id": job.tenant_id, "kind": job.kind, "state": job.state,
                "attempt": job.attempt, "replay_of": job.replay_of,
            })).collect::<Vec<_>>()).unwrap_or_else(|_| "[]".into())),
            Err(_) => ("500 Internal Server Error", "text/plain", "job listing failed\n".into()),
        },
        _ => ("405 Method Not Allowed", "text/plain", "only GET is supported\n".into()),
    }
}

/// Readiness is a boot fence, not liveness.  When a database is configured,
/// refuse readiness until its TCP endpoint is reachable.  The contract crate
/// remains usable without a database for local protocol tests and `--check`.
fn readiness_response() -> (&'static str, &'static str, String) {
    use std::net::ToSocketAddrs;
    let Some(database_url) = std::env::var_os("DATABASE_URL") else {
        return ("200 OK", "text/plain", "ok\n".to_string());
    };
    let database_url = database_url.to_string_lossy();
    let Some(endpoint) = postgres_endpoint(&database_url) else {
        return (
            "503 Service Unavailable",
            "text/plain",
            "database endpoint is invalid\n".to_string(),
        );
    };
    let address = endpoint
        .to_socket_addrs()
        .ok()
        .and_then(|mut addresses| addresses.next());
    let Some(address) = address else {
        return (
            "503 Service Unavailable",
            "text/plain",
            "database unavailable\n".to_string(),
        );
    };
    match std::net::TcpStream::connect_timeout(&address, std::time::Duration::from_millis(250)) {
        Ok(_) => ("200 OK", "text/plain", "ok\n".to_string()),
        Err(_) => (
            "503 Service Unavailable",
            "text/plain",
            "database unavailable\n".to_string(),
        ),
    }
}

fn postgres_endpoint(url: &str) -> Option<String> {
    let authority = url.split("://").nth(1)?.split('/').next()?;
    let authority = authority.rsplit('@').next()?;
    let (host, port) = authority.rsplit_once(':').unwrap_or((authority, "5432"));
    let host = host.trim_matches(['[', ']']);
    let port = port.parse::<u16>().ok()?;
    if host.contains(':') {
        Some(format!("[{host}]:{port}"))
    } else {
        Some(format!("{host}:{port}"))
    }
}

#[cfg(test)]
mod tests {
    use super::postgres_endpoint;

    #[test]
    fn parses_postgres_ipv4_url() {
        assert_eq!(
            postgres_endpoint("postgres://user:pass@127.0.0.1:5433/db"),
            Some("127.0.0.1:5433".into())
        );
    }

    #[test]
    fn preserves_kubernetes_dns_hosts_for_resolution() {
        assert_eq!(
            postgres_endpoint("postgres://db.internal:5432/db"),
            Some("db.internal:5432".into())
        );
    }

    #[test]
    fn preserves_brackets_for_ipv6_endpoints() {
        assert_eq!(
            postgres_endpoint("postgres://[::1]:5432/db"),
            Some("[::1]:5432".into())
        );
    }
}
