use crate::auth::WorkerAuth;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Health,
    Ready,
    Version,
    Jobs,
    JobStats,
    Unknown,
}

pub fn route_for(path: &str) -> Route {
    match path {
        "/healthz" => Route::Health,
        "/readyz" => Route::Ready,
        "/version" => Route::Version,
        "/v1/jobs" => Route::Jobs,
        "/v1/jobs/stats" => Route::JobStats,
        _ => Route::Unknown,
    }
}

pub fn authorize_route(route: Route, auth: &WorkerAuth, bearer: Option<&str>) -> bool {
    matches!(route, Route::Health | Route::Ready | Route::Version) || auth.authorize_bearer(bearer)
}

#[cfg(test)]
mod tests {
    use super::{authorize_route, route_for, Route};
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
}
