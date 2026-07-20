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
    let database = Arc::new(database);
    println!("FrankenGate analytics control plane listening on 0.0.0.0:{port}");
    for stream in listener.incoming().flatten() {
        let store = Arc::clone(&store);
        let database = Arc::clone(&database);
        std::thread::spawn(|| handle_connection(stream, store, database));
    }
}

fn handle_connection(
    mut stream: std::net::TcpStream,
    store: std::sync::Arc<frankengate_analytics_control::JobStore>,
    database: std::sync::Arc<Option<sqlx::PgPool>>,
) {
    use std::io::{Read, Write};
    // Health probes are tiny and bounded.  Do not let an accepted but idle
    // socket consume a thread forever (especially during a probe storm).
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(2)));
    let mut request = [0_u8; 1024];
    let size = stream.read(&mut request).unwrap_or(0);
    let target = std::str::from_utf8(&request[..size])
        .ok()
        .and_then(|request| request.split_whitespace().nth(1))
        .unwrap_or("/");
    let (path, query) = target.split_once('?').unwrap_or((target, ""));
    let (status, content_type, body) = match path {
        "/healthz" | "/readyz" => ("200 OK", "text/plain", "ok\n".to_string()),
        "/version" => (
            "200 OK",
            "text/plain",
            format!(
                "protocol_version={}\n",
                frankengate_analytics_control::PROTOCOL_VERSION
            ),
        ),
        "/v1/jobs/lease" => {
            let tenant = query_param(query, "tenant");
            let worker = query_param(query, "worker");
            let lease_seconds = query_param(query, "lease_seconds")
                .and_then(|value| value.parse::<i64>().ok())
                .unwrap_or(30)
                .clamp(1, 3600);
            match (database.as_ref(), tenant, worker) {
                (Some(pool), Some(tenant), Some(worker)) => {
                    let result = tokio::runtime::Runtime::new().ok().and_then(|runtime| {
                        runtime
                            .block_on(frankengate_analytics_control::db::lease_next(
                                pool,
                                tenant,
                                worker,
                                lease_seconds,
                            ))
                            .ok()
                    });
                    match result.flatten() {
                        Some(claim) => (
                            "200 OK",
                            "text/plain",
                            format!(
                                "id={}\ntenant={}\nkind={}\nattempt={}\n",
                                claim.id, claim.tenant, claim.kind, claim.attempt
                            ),
                        ),
                        None => ("204 No Content", "text/plain", String::new()),
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "tenant, worker, and DATABASE_URL are required\n".to_string(),
                ),
            }
        }
        "/metrics" => {
            let tenant = query
                .split('&')
                .find_map(|pair| pair.strip_prefix("tenant="))
                .filter(|value| !value.is_empty());
            let stats = if let (Some(pool), Some(tenant)) = (database.as_ref(), tenant) {
                // Metrics are control-plane traffic, not an inference hot path.
                // A short-lived runtime keeps the existing tiny HTTP server
                // architecture while allowing the SQLx async query here.
                tokio::runtime::Runtime::new()
                    .ok()
                    .and_then(|runtime| {
                        runtime
                            .block_on(frankengate_analytics_control::db::stats(pool, tenant))
                            .ok()
                    })
                    .unwrap_or_default()
            } else {
                store.stats()
            };
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
