use crate::auth::WorkerAuth;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Health,
    Ready,
    Version,
    Jobs,
    JobStats,
    Lease,
    Renew,
    Complete,
    Fail,
    Cancel,
    Checkpoint,
    Replay,
    Drain,
    Unknown,
}

pub fn route_for(path: &str) -> Route {
    match path {
        "/healthz" => Route::Health,
        "/readyz" => Route::Ready,
        "/version" => Route::Version,
        "/v1/jobs" => Route::Jobs,
        "/v1/jobs/stats" => Route::JobStats,
        "/v1/jobs/lease" => Route::Lease,
        "/v1/jobs/renew" => Route::Renew,
        "/v1/jobs/complete" => Route::Complete,
        "/v1/jobs/fail" => Route::Fail,
        "/v1/jobs/cancel" => Route::Cancel,
        "/v1/jobs/checkpoint" => Route::Checkpoint,
        "/v1/jobs/replay" => Route::Replay,
        "/v1/jobs/drain" => Route::Drain,
        _ => Route::Unknown,
    }
}

pub fn authorize_route(route: Route, auth: &WorkerAuth, bearer: Option<&str>) -> bool {
    matches!(route, Route::Health | Route::Ready | Route::Version) || auth.authorize_bearer(bearer)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Request<'a> {
    pub method: &'a str,
    pub path: &'a str,
    pub authorization: Option<&'a str>,
    pub tenant: Option<&'a str>,
    pub job_id: Option<&'a str>,
    pub job_kind: Option<&'a str>,
    pub worker_id: Option<&'a str>,
    pub lease_seconds: Option<&'a str>,
    pub error_code: Option<&'a str>,
    pub checkpoint: Option<&'a str>,
    pub replay_id: Option<&'a str>,
    pub source_job_id: Option<&'a str>,
}

pub fn parse_request(raw: &[u8]) -> Option<Request<'_>> {
    const MAX_REQUEST_BYTES: usize = 16 * 1024;
    if raw.len() > MAX_REQUEST_BYTES {
        return None;
    }
    let text = std::str::from_utf8(raw).ok()?;
    let mut lines = text.split("\r\n");
    let request_line = lines.next()?;
    let mut parts = request_line.split_whitespace();
    let method = parts.next()?;
    let path = parts.next()?;
    if parts.next()? != "HTTP/1.1" {
        return None;
    }
    let mut authorization = None;
    let mut tenant = None;
    let mut job_id = None;
    let mut job_kind = None;
    let mut worker_id = None;
    let mut lease_seconds = None;
    let mut error_code = None;
    let mut checkpoint = None;
    let mut replay_id = None;
    let mut source_job_id = None;
    for line in lines {
        if line.is_empty() {
            break;
        }
        let (name, value) = line.split_once(':')?;
        if name.eq_ignore_ascii_case("authorization") {
            authorization = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-tenant-id") {
            tenant = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-job-id") {
            job_id = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-job-kind") {
            job_kind = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-worker-id") {
            worker_id = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-lease-seconds") {
            lease_seconds = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-error-code") {
            error_code = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-checkpoint") {
            checkpoint = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-replay-id") {
            replay_id = Some(value.trim());
        }
        if name.eq_ignore_ascii_case("x-source-job-id") {
            source_job_id = Some(value.trim());
        }
    }
    Some(Request {
        method,
        path,
        authorization,
        tenant,
        job_id,
        job_kind,
        worker_id,
        lease_seconds,
        error_code,
        checkpoint,
        replay_id,
        source_job_id,
    })
}

#[cfg(test)]
mod tests {
    use super::{authorize_route, parse_request, route_for, Route};
    use crate::auth::WorkerAuth;

    #[test]
    fn classifies_public_and_governed_routes() {
        assert_eq!(route_for("/healthz"), Route::Health);
        assert_eq!(route_for("/v1/jobs"), Route::Jobs);
        assert_eq!(route_for("/v1/jobs/stats"), Route::JobStats);
        assert_eq!(route_for("/other"), Route::Unknown);
    }

    #[test]
    fn protects_v1_routes_when_worker_auth_is_configured() {
        let auth = WorkerAuth::from_token(Some("secret"));
        assert!(authorize_route(Route::Health, &auth, None));
        assert!(!authorize_route(Route::Jobs, &auth, None));
        assert!(authorize_route(Route::Jobs, &auth, Some("Bearer secret")));
    }

    #[test]
    fn parses_bounded_request_and_authorization_header() {
        let request =
            parse_request(b"GET /v1/jobs HTTP/1.1\r\nAuthorization: Bearer secret\r\n\r\n")
                .expect("valid request");
        assert_eq!(request.method, "GET");
        assert_eq!(request.path, "/v1/jobs");
        assert_eq!(request.authorization, Some("Bearer secret"));
        assert_eq!(request.tenant, None);
        assert_eq!(request.job_id, None);
        assert!(parse_request(b"GET / HTTP/1.0\r\n\r\n").is_none());
    }
}
