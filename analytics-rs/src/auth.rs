//! Authentication policy for analytics worker endpoints.

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WorkerAuth {
    expected: Option<Vec<u8>>,
}

impl WorkerAuth {
    pub fn from_token(token: Option<&str>) -> Self {
        Self {
            expected: token
                .filter(|token| !token.is_empty())
                .map(|token| token.as_bytes().to_vec()),
        }
    }

    pub fn is_configured(&self) -> bool {
        self.expected.is_some()
    }

    pub fn authorize_bearer(&self, header: Option<&str>) -> bool {
        let Some(expected) = &self.expected else {
            return true;
        };
        let Some(value) = header.and_then(|value| value.strip_prefix("Bearer ")) else {
            return false;
        };
        constant_time_equal(expected, value.as_bytes())
    }
}

fn constant_time_equal(expected: &[u8], actual: &[u8]) -> bool {
    let mut difference = (expected.len() ^ actual.len()) as u8;
    for index in 0..expected.len().max(actual.len()) {
        difference |=
            expected.get(index).copied().unwrap_or(0) ^ actual.get(index).copied().unwrap_or(0);
    }
    difference == 0
}

#[cfg(test)]
mod tests {
    use super::WorkerAuth;

    #[test]
    fn absent_configuration_is_explicitly_open_for_local_mode() {
        assert!(WorkerAuth::from_token(None).authorize_bearer(None));
        assert!(!WorkerAuth::from_token(Some("")).is_configured());
    }

    #[test]
    fn configured_worker_token_requires_bearer_and_exact_match() {
        let auth = WorkerAuth::from_token(Some("worker-secret"));
        assert!(auth.is_configured());
        assert!(auth.authorize_bearer(Some("Bearer worker-secret")));
        assert!(!auth.authorize_bearer(Some("worker-secret")));
        assert!(!auth.authorize_bearer(Some("Bearer wrong")));
        assert!(!auth.authorize_bearer(None));
    }
}
