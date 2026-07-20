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
    let request_line = std::str::from_utf8(&request[..size]).unwrap_or("");
    let method = request_line.split_whitespace().next().unwrap_or("");
    let target = request_line.split_whitespace().nth(1).unwrap_or("/");
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
        "/v1/jobs" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let id = query_param(query, "id");
            let kind = query_param(query, "kind");
            match (database.as_ref(), tenant, id, kind) {
                (Some(pool), Some(tenant), Some(id), Some(kind)) => {
                    let job = frankengate_analytics_control::SubmitJob {
                        protocol_version: frankengate_analytics_control::PROTOCOL_VERSION,
                        id: id.to_owned(),
                        tenant: tenant.to_owned(),
                        kind: kind.to_owned(),
                    };
                    let submitted = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::submit_job(pool, &job))
                                .ok()
                        })
                        .unwrap_or(false);
                    if submitted {
                        ("201 Created", "text/plain", format!("id={}\n", job.id))
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "job already exists\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, id, and kind is required\n".to_string(),
                ),
            }
        }
        "/v1/jobs/complete" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let worker = query_param(query, "worker");
            let job_id = query_param(query, "job_id");
            match (database.as_ref(), tenant, worker, job_id) {
                (Some(pool), Some(tenant), Some(worker), Some(job_id)) => {
                    let completed = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::complete_job(
                                    pool, tenant, job_id, worker,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if completed {
                        ("200 OK", "text/plain", "completed\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "lease not owned\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, worker, and job_id is required\n".to_string(),
                ),
            }
        }
        "/v1/jobs/renew" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let worker = query_param(query, "worker");
            let job_id = query_param(query, "job_id");
            let lease_seconds = query_param(query, "lease_seconds")
                .and_then(|value| value.parse::<i64>().ok())
                .unwrap_or(30)
                .clamp(1, 3600);
            match (database.as_ref(), tenant, worker, job_id) {
                (Some(pool), Some(tenant), Some(worker), Some(job_id)) => {
                    let renewed = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::renew_lease(
                                    pool,
                                    tenant,
                                    job_id,
                                    worker,
                                    lease_seconds,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if renewed {
                        ("200 OK", "text/plain", "renewed\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "lease not owned\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, worker, and job_id is required\n".to_string(),
                ),
            }
        }
        "/v1/jobs/fail" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let worker = query_param(query, "worker");
            let job_id = query_param(query, "job_id");
            let error_code = query_param(query, "error_code");
            match (database.as_ref(), tenant, worker, job_id, error_code) {
                (Some(pool), Some(tenant), Some(worker), Some(job_id), Some(error_code)) => {
                    let failed = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::fail_job(
                                    pool, tenant, job_id, worker, error_code,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if failed {
                        ("200 OK", "text/plain", "failed\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "lease not owned\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, worker, job_id, and error_code is required\n".to_string(),
                ),
            }
        }
        "/v1/jobs/replay" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let replay_id = query_param(query, "replay_id");
            let source_job_id = query_param(query, "source_job_id");
            let kind = query_param(query, "kind");
            match (database.as_ref(), tenant, replay_id, source_job_id, kind) {
                (Some(pool), Some(tenant), Some(replay_id), Some(source_job_id), Some(kind)) => {
                    let replay = frankengate_analytics_control::ReplayJob {
                        protocol_version: frankengate_analytics_control::PROTOCOL_VERSION,
                        replay_id: replay_id.to_owned(),
                        source_job_id: source_job_id.to_owned(),
                        tenant: tenant.to_owned(),
                        kind: kind.to_owned(),
                    };
                    let created = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::replay_job(
                                    pool, &replay,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if created {
                        (
                            "201 Created",
                            "text/plain",
                            format!("id={}\n", replay.replay_id),
                        )
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "replay rejected\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, replay_id, source_job_id, and kind is required\n"
                        .to_string(),
                ),
            }
        }
        "/v1/jobs/cancel" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let job_id = query_param(query, "job_id");
            match (database.as_ref(), tenant, job_id) {
                (Some(pool), Some(tenant), Some(job_id)) => {
                    let cancelled = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::cancel_job(
                                    pool, tenant, job_id,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if cancelled {
                        ("200 OK", "text/plain", "cancelled\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "job is not cancellable\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant and job_id is required\n".to_string(),
                ),
            }
        }
        "/v1/jobs/retry" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let job_id = query_param(query, "job_id");
            match (database.as_ref(), tenant, job_id) {
                (Some(pool), Some(tenant), Some(job_id)) => {
                    let retried = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::retry_job(
                                    pool, tenant, job_id,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if retried {
                        ("200 OK", "text/plain", "queued\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "job is not retryable\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant and job_id is required\n".to_string(),
                ),
            }
        }
        "/v1/jobs/checkpoint" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let worker = query_param(query, "worker");
            let job_id = query_param(query, "job_id");
            let checkpoint = query_param(query, "checkpoint");
            match (database.as_ref(), tenant, worker, job_id, checkpoint) {
                (Some(pool), Some(tenant), Some(worker), Some(job_id), Some(checkpoint)) => {
                    let saved = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::checkpoint_job(
                                    pool, tenant, job_id, worker, checkpoint,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if saved {
                        ("200 OK", "text/plain", "checkpointed\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "lease not owned or checkpoint too large\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, worker, job_id, and checkpoint is required\n".to_string(),
                ),
            }
        }
        "/v1/workers/drain" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let worker = query_param(query, "worker");
            match (database.as_ref(), tenant, worker) {
                (Some(pool), Some(tenant), Some(worker)) => {
                    let released = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::drain_worker(
                                    pool, tenant, worker,
                                ))
                                .ok()
                        })
                        .unwrap_or(0);
                    ("200 OK", "text/plain", format!("released={}\n", released))
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant and worker is required\n".to_string(),
                ),
            }
        }
        "/v1/workers/reap" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            match (database.as_ref(), tenant) {
                (Some(pool), Some(tenant)) => {
                    let reaped = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::reap_expired(
                                    pool, tenant,
                                ))
                                .ok()
                        })
                        .unwrap_or(0);
                    ("200 OK", "text/plain", format!("reaped={}\n", reaped))
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant is required\n".to_string(),
                ),
            }
        }
        "/v1/experiments" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let id = query_param(query, "id");
            let actor = query_param(query, "actor");
            let revision = query_param(query, "revision");
            match (database.as_ref(), tenant, id, actor, revision) {
                (Some(pool), Some(tenant), Some(id), Some(actor), Some(revision)) => {
                    let experiment = frankengate_analytics_control::Experiment {
                        id: id.to_owned(),
                        tenant: tenant.to_owned(),
                        actor: actor.to_owned(),
                        revision: revision.to_owned(),
                    };
                    let created = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::create_experiment(
                                    pool,
                                    &experiment,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if created {
                        (
                            "201 Created",
                            "text/plain",
                            format!("id={}\n", experiment.id),
                        )
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "experiment already exists\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, id, actor, and revision is required\n".to_string(),
                ),
            }
        }
        "/v1/runs" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let id = query_param(query, "id");
            let experiment_id = query_param(query, "experiment_id");
            let dataset_revision = query_param(query, "dataset_revision");
            let evaluator_revision = query_param(query, "evaluator_revision");
            let model_revision = query_param(query, "model_revision");
            let prompt_revision = query_param(query, "prompt_revision");
            match (
                database.as_ref(),
                tenant,
                id,
                experiment_id,
                dataset_revision,
                evaluator_revision,
                model_revision,
                prompt_revision,
            ) {
                (
                    Some(pool),
                    Some(tenant),
                    Some(id),
                    Some(experiment_id),
                    Some(dataset_revision),
                    Some(evaluator_revision),
                    Some(model_revision),
                    Some(prompt_revision),
                ) => {
                    let run = frankengate_analytics_control::Run {
                        id: id.to_owned(),
                        experiment_id: experiment_id.to_owned(),
                        dataset_revision: dataset_revision.to_owned(),
                        evaluator_revision: evaluator_revision.to_owned(),
                        model_revision: model_revision.to_owned(),
                        prompt_revision: prompt_revision.to_owned(),
                    };
                    let created = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::create_run(
                                    pool, tenant, &run,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if created {
                        ("201 Created", "text/plain", format!("id={}\n", run.id))
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "run already exists\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, id, experiment_id, and all revision fields is required\n"
                        .to_string(),
                ),
            }
        }
        "/v1/evaluations" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let run_id = query_param(query, "run_id");
            let example_id = query_param(query, "example_id");
            let evaluator_revision = query_param(query, "evaluator_revision");
            let score = query_param(query, "score");
            match (
                database.as_ref(),
                tenant,
                run_id,
                example_id,
                evaluator_revision,
                score,
            ) {
                (
                    Some(pool),
                    Some(tenant),
                    Some(run_id),
                    Some(example_id),
                    Some(evaluator_revision),
                    Some(score),
                ) => {
                    let result = frankengate_analytics_control::EvaluationResult {
                        run_id: run_id.to_owned(),
                        example_id: example_id.to_owned(),
                        score: score.to_owned(),
                        evaluator_revision: evaluator_revision.to_owned(),
                    };
                    let inserted = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::record_evaluation(
                                    pool, tenant, &result,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if inserted {
                        ("201 Created", "text/plain", "recorded\n".to_string())
                    } else {
                        ("409 Conflict", "text/plain", "evaluation already exists\n".to_string())
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, run_id, example_id, evaluator_revision, and score is required\n"
                        .to_string(),
                ),
            }
        }
        "/v1/artifacts" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let run_id = query_param(query, "run_id");
            let digest = query_param(query, "digest");
            let media_type = query_param(query, "media_type");
            let object_uri = query_param(query, "object_uri");
            match (
                database.as_ref(),
                tenant,
                run_id,
                digest,
                media_type,
                object_uri,
            ) {
                (
                    Some(pool),
                    Some(tenant),
                    Some(run_id),
                    Some(digest),
                    Some(media_type),
                    Some(object_uri),
                ) => {
                    let artifact = frankengate_analytics_control::ArtifactManifest {
                        run_id: run_id.to_owned(),
                        digest: digest.to_owned(),
                        media_type: media_type.to_owned(),
                        object_uri: object_uri.to_owned(),
                    };
                    let inserted = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::record_artifact(
                                    pool, tenant, &artifact,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if inserted {
                        (
                            "201 Created",
                            "text/plain",
                            format!("digest={}\n", artifact.digest),
                        )
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "artifact already exists\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, run_id, digest, media_type, and object_uri is required\n"
                        .to_string(),
                ),
            }
        }
        "/v1/attempts" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let id = query_param(query, "id");
            let run_id = query_param(query, "run_id");
            let attempt = query_param(query, "attempt").and_then(|value| value.parse().ok());
            let worker = query_param(query, "worker");
            let job_id = query_param(query, "job_id");
            match (
                database.as_ref(),
                tenant,
                id,
                run_id,
                attempt,
                worker,
                job_id,
            ) {
                (
                    Some(pool),
                    Some(tenant),
                    Some(id),
                    Some(run_id),
                    Some(attempt),
                    Some(worker),
                    Some(job_id),
                ) => {
                    let record = frankengate_analytics_control::RunAttempt {
                        id: id.to_owned(),
                        run_id: run_id.to_owned(),
                        attempt,
                        worker: worker.to_owned(),
                        job_id: job_id.to_owned(),
                        outcome: None,
                    };
                    let inserted = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::record_attempt(
                                    pool, tenant, &record,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if inserted {
                        ("201 Created", "text/plain", format!("id={}\n", record.id))
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "attempt already exists\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, id, run_id, attempt, worker, and job_id is required\n"
                        .to_string(),
                ),
            }
        }
        "/v1/runs/finish" if method == "POST" => {
            let tenant = query_param(query, "tenant");
            let run_id = query_param(query, "run_id");
            let outcome = query_param(query, "outcome");
            match (database.as_ref(), tenant, run_id, outcome) {
                (Some(pool), Some(tenant), Some(run_id), Some(outcome)) => {
                    let finished = tokio::runtime::Runtime::new()
                        .ok()
                        .and_then(|runtime| {
                            runtime
                                .block_on(frankengate_analytics_control::db::finish_run(
                                    pool, tenant, run_id, outcome,
                                ))
                                .ok()
                        })
                        .unwrap_or(false);
                    if finished {
                        ("200 OK", "text/plain", "finished\n".to_string())
                    } else {
                        (
                            "409 Conflict",
                            "text/plain",
                            "run already terminal or not found\n".to_string(),
                        )
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "POST with tenant, run_id, and outcome is required\n".to_string(),
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
        "/v1/jobs/stats" if method == "GET" => {
            let tenant = query_param(query, "tenant");
            match (database.as_ref(), tenant) {
                (Some(pool), Some(tenant)) => {
                    match tokio::runtime::Runtime::new().ok().and_then(|runtime| {
                        runtime
                            .block_on(frankengate_analytics_control::db::stats(pool, tenant))
                            .ok()
                    }) {
                        Some(stats) => (
                            "200 OK",
                            "application/json",
                            serde_json::json!({
                                "tenant": tenant,
                                "queued": stats.queued,
                                "leased": stats.leased,
                                "cancelled": stats.cancelled,
                                "completed": stats.completed,
                                "failed": stats.failed,
                            })
                            .to_string(),
                        ),
                        None => (
                            "503 Service Unavailable",
                            "text/plain",
                            "durable queue stats unavailable\n".to_string(),
                        ),
                    }
                }
                _ => (
                    "400 Bad Request",
                    "text/plain",
                    "GET with tenant and DATABASE_URL is required\n".to_string(),
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

fn query_param<'a>(query: &'a str, name: &str) -> Option<&'a str> {
    query
        .split('&')
        .find_map(|pair| {
            pair.strip_prefix(name)
                .and_then(|value| value.strip_prefix('='))
        })
        .filter(|value| !value.is_empty())
}

#[cfg(test)]
mod tests {
    use super::query_param;

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
}
