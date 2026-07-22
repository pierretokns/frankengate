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

    let port = std::env::var("PORT").unwrap_or_else(|_| "8081".into());
    let listener = TcpListener::bind(("0.0.0.0", port.parse::<u16>().expect("PORT must be a u16")))
        .expect("analytics control-plane listener failed to bind");
    let store = Arc::new(frankengate_analytics_control::JobStore::default());
    let replay_source = std::env::var("FRANKENGATE_REPLAY_DIR")
        .ok()
        .filter(|dir| !dir.trim().is_empty())
        .map(frankengate_analytics_control::JsonlReplaySource::new)
        .map(Arc::new);
    println!("FrankenGate analytics control plane listening on 0.0.0.0:{port}");
    for stream in listener.incoming().flatten() {
        let store = Arc::clone(&store);
        let replay_source = replay_source.clone();
        std::thread::spawn(|| handle_connection(stream, store, replay_source));
    }
}

fn handle_connection(
    mut stream: std::net::TcpStream,
    store: std::sync::Arc<frankengate_analytics_control::JobStore>,
    replay_source: Option<std::sync::Arc<frankengate_analytics_control::JsonlReplaySource>>,
) {
    use std::io::{Read, Write};
    // Health probes are tiny and bounded.  Do not let an accepted but idle
    // socket consume a thread forever (especially during a probe storm).
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_secs(2)));
    let mut request = [0_u8; 1024];
    let size = stream.read(&mut request).unwrap_or(0);
    let (method, path) = std::str::from_utf8(&request[..size])
        .ok()
        .and_then(|request| {
            let mut parts = request.split_whitespace();
            Some((parts.next()?, parts.next()?))
        })
        .unwrap_or(("GET", "/"));
    let (route, query) = path.split_once('?').unwrap_or((path, ""));
    let (status, content_type, body) = match route {
        "/healthz" | "/readyz" => ("200 OK", "text/plain", "ok\n".to_string()),
        "/version" => (
            "200 OK",
            "text/plain",
            format!(
                "protocol_version={}\n",
                frankengate_analytics_control::PROTOCOL_VERSION
            ),
        ),
        "/persistence" => (
            "200 OK",
            "application/json",
            "{\"mode\":\"in-memory\",\"durable_schema\":\"postgresql\",\"runtime\":\"contract-only\"}\n".into(),
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
        "/stats" => {
            let tenant = query_value(query, "tenant");
            let stats = tenant
                .as_deref()
                .map(|tenant| store.stats_for_tenant(tenant))
                .unwrap_or_else(|| store.stats());
            (
                "200 OK",
                "application/json",
                format!(
                    "{{\"protocol_version\":{},\"queued\":{},\"leased\":{},\"cancelled\":{},\"completed\":{},\"failed\":{}}}\n",
                    frankengate_analytics_control::PROTOCOL_VERSION,
                    stats.queued,
                    stats.leased,
                    stats.cancelled,
                    stats.completed,
                    stats.failed
                ),
            )
        }
        "/jobs" => {
            let tenant = query_value(query, "tenant").unwrap_or_default();
            if tenant.is_empty() {
                (
                    "400 Bad Request",
                    "text/plain",
                    "tenant is required\n".into(),
                )
            } else if method == "POST" {
                let id = query_value(query, "id").unwrap_or_default();
                let kind = query_value(query, "kind").unwrap_or_default();
                match store.submit(frankengate_analytics_control::SubmitJob {
                    protocol_version: frankengate_analytics_control::PROTOCOL_VERSION,
                    id,
                    tenant,
                    kind,
                }) {
                    Ok(job) => ("201 Created", "application/json", job_json(&job)),
                    Err(_) => ("400 Bad Request", "text/plain", "invalid job\n".into()),
                }
            } else if method != "GET" {
                (
                    "405 Method Not Allowed",
                    "text/plain",
                    "method not allowed\n".into(),
                )
            } else {
                let jobs = store.list_for_tenant(&tenant, 100);
                let items = jobs
                    .iter()
                    .map(|job| format!("{}", job_json(job).trim_end()))
                    .collect::<Vec<_>>()
                    .join(",");
                ("200 OK", "application/json", format!("[{}]\n", items))
            }
        }
        "/jobs/lease" => {
            let id = query_value(query, "id").unwrap_or_default();
            let worker = query_value(query, "worker").unwrap_or_default();
            match store.lease(&id, worker) {
                Ok(job) => ("200 OK", "application/json", job_json(&job)),
                Err(_) => ("409 Conflict", "text/plain", "job is not leasable\n".into()),
            }
        }
        "/jobs/complete" => {
            let id = query_value(query, "id").unwrap_or_default();
            let worker = query_value(query, "worker").unwrap_or_default();
            match store.complete(&id, &worker) {
                Ok(job) => ("200 OK", "application/json", job_json(&job)),
                Err(_) => ("409 Conflict", "text/plain", "job is not completable\n".into()),
            }
        }
        "/jobs/renew" => {
            let id = query_value(query, "id").unwrap_or_default();
            let worker = query_value(query, "worker").unwrap_or_default();
            match store.renew(&id, &worker, std::time::Duration::from_secs(30)) {
                Ok(job) => ("200 OK", "application/json", job_json(&job)),
                Err(_) => ("409 Conflict", "text/plain", "job is not renewable\n".into()),
            }
        }
        "/jobs/checkpoint" => {
            let id = query_value(query, "id").unwrap_or_default();
            let worker = query_value(query, "worker").unwrap_or_default();
            let value = query_value(query, "value").unwrap_or_default();
            match store.checkpoint(&id, &worker, value) {
                Ok(job) => ("200 OK", "application/json", job_json(&job)),
                Err(_) => ("409 Conflict", "text/plain", "job checkpoint rejected\n".into()),
            }
        }
        "/jobs/cancel" => {
            let tenant = query_value(query, "tenant").unwrap_or_default();
            let id = query_value(query, "id").unwrap_or_default();
            match store.cancel_for_tenant(&tenant, &id) {
                Ok(job) => ("200 OK", "application/json", job_json(&job)),
                Err(_) => ("409 Conflict", "text/plain", "job is not cancellable\n".into()),
            }
        }
        "/replay" => {
            let tenant = query_value(query, "tenant").unwrap_or_default();
            match (replay_source.as_deref(), tenant.is_empty()) {
                (Some(source), false) => match source.read_tenant(&tenant, 100) {
                    Ok(traces) => {
                        let items = traces.iter().map(|trace| format!(
                            "{{\"trace_id\":\"{}\",\"request_id\":\"{}\",\"tenant\":\"{}\",\"model\":\"{}\",\"provider\":\"{}\"}}",
                            json_escape(&trace.trace_id), json_escape(&trace.request_id),
                            json_escape(&trace.tenant), json_escape(&trace.model), json_escape(&trace.provider)
                        )).collect::<Vec<_>>().join(",");
                        ("200 OK", "application/json", format!("[{}]\n", items))
                    }
                    Err(_) => (
                        "404 Not Found",
                        "text/plain",
                        "replay tenant not found\n".into(),
                    ),
                },
                (None, _) => (
                    "503 Service Unavailable",
                    "text/plain",
                    "replay source is not configured\n".into(),
                ),
                (Some(_), true) => (
                    "400 Bad Request",
                    "text/plain",
                    "tenant is required\n".into(),
                ),
            }
        }
        _ => ("404 Not Found", "text/plain", "not found\n".to_string()),
    };
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
}

fn query_value(query: &str, key: &str) -> Option<String> {
    query.split('&').find_map(|part| {
        let (candidate, value) = part.split_once('=')?;
        (candidate == key).then(|| value.to_string())
    })
}

fn json_escape(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn job_json(job: &frankengate_analytics_control::Job) -> String {
    format!(
        "{{\"id\":\"{}\",\"tenant\":\"{}\",\"kind\":\"{}\",\"attempt\":{}}}\n",
        json_escape(&job.id),
        json_escape(&job.tenant),
        json_escape(&job.kind),
        job.attempt
    )
}

#[cfg(test)]
mod tests {
    use super::{json_escape, query_value};

    #[test]
    fn query_values_are_selected_without_cross_tenant_fallback() {
        assert_eq!(
            query_value("tenant=alpha&limit=10", "tenant"),
            Some("alpha".into())
        );
        assert_eq!(query_value("tenant=alpha", "other"), None);
    }

    #[test]
    fn json_escape_handles_identifiers() {
        assert_eq!(json_escape("a\\\"b"), "a\\\\\\\"b");
    }
}
