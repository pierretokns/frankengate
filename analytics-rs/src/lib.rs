//! Minimal, dependency-free leased-job contract for the FrankenGate analytics plane.
//!
//! This crate deliberately does not run inside the Go inference gateway.  It is
//! the first vertical slice used to validate ownership, idempotent leasing,
//! cancellation, and bounded outcomes before adding HTTP, SQLx, or worker
//! ecosystem dependencies.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub const PROTOCOL_VERSION: u16 = 1;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SubmitJob {
    pub protocol_version: u16,
    pub id: String,
    pub tenant: String,
    pub kind: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JobOutcome {
    pub protocol_version: u16,
    pub id: String,
    pub attempt: u32,
    pub terminal: bool,
    pub error_code: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Experiment {
    pub id: String,
    pub tenant: String,
    pub actor: String,
    pub revision: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Run {
    pub id: String,
    pub experiment_id: String,
    pub dataset_revision: String,
    pub evaluator_revision: String,
    pub model_revision: String,
    pub prompt_revision: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EvaluationResult {
    pub run_id: String,
    pub example_id: String,
    pub score: String,
    pub evaluator_revision: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ArtifactManifest {
    pub run_id: String,
    pub digest: String,
    pub media_type: String,
    pub object_uri: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum JobState {
    Queued,
    Leased { worker: String, attempt: u32 },
    Cancelled,
    Completed,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Job {
    pub id: String,
    pub tenant: String,
    pub kind: String,
    pub state: JobState,
    lease_until: Option<Instant>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LeaseError {
    NotFound,
    NotLeasable,
    AlreadyCancelled,
}

#[derive(Clone, Default)]
pub struct JobStore {
    jobs: Arc<Mutex<HashMap<String, Job>>>,
}

impl JobStore {
    pub fn submit(&self, request: SubmitJob) -> Result<Job, LeaseError> {
        if request.protocol_version != PROTOCOL_VERSION {
            return Err(LeaseError::NotLeasable);
        }
        Ok(self.enqueue(request.id, request.tenant, request.kind))
    }

    pub fn enqueue(
        &self,
        id: impl Into<String>,
        tenant: impl Into<String>,
        kind: impl Into<String>,
    ) -> Job {
        let job = Job {
            id: id.into(),
            tenant: tenant.into(),
            kind: kind.into(),
            state: JobState::Queued,
            lease_until: None,
        };
        self.jobs
            .lock()
            .expect("job store lock poisoned")
            .insert(job.id.clone(), job.clone());
        job
    }

    pub fn get(&self, id: &str) -> Option<Job> {
        self.jobs
            .lock()
            .expect("job store lock poisoned")
            .get(id)
            .cloned()
    }

    pub fn lease(&self, id: &str, worker: impl Into<String>) -> Result<Job, LeaseError> {
        self.lease_for(id, worker, Duration::from_secs(30))
    }

    pub fn lease_for(
        &self,
        id: &str,
        worker: impl Into<String>,
        duration: Duration,
    ) -> Result<Job, LeaseError> {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        let attempt = match job.state {
            JobState::Queued => 1,
            JobState::Leased { .. } => return Err(LeaseError::NotLeasable),
            JobState::Cancelled | JobState::Completed => return Err(LeaseError::NotLeasable),
        };
        job.state = JobState::Leased {
            worker: worker.into(),
            attempt,
        };
        job.lease_until = Some(Instant::now() + duration);
        Ok(job.clone())
    }

    pub fn reap_expired(&self, now: Instant) -> usize {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let mut reaped = 0;
        for job in jobs.values_mut() {
            if job.lease_until.is_some_and(|deadline| deadline <= now)
                && matches!(job.state, JobState::Leased { .. })
            {
                job.state = JobState::Queued;
                job.lease_until = None;
                reaped += 1;
            }
        }
        reaped
    }

    pub fn renew(&self, id: &str, worker: &str, duration: Duration) -> Result<Job, LeaseError> {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        match &job.state {
            JobState::Leased { worker: owner, .. } if owner == worker => {
                job.lease_until = Some(Instant::now() + duration);
                Ok(job.clone())
            }
            _ => Err(LeaseError::NotLeasable),
        }
    }

    pub fn cancel(&self, id: &str) -> Result<Job, LeaseError> {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        if job.state == JobState::Cancelled {
            return Err(LeaseError::AlreadyCancelled);
        }
        if job.state == JobState::Completed {
            return Err(LeaseError::NotLeasable);
        }
        job.state = JobState::Cancelled;
        job.lease_until = None;
        Ok(job.clone())
    }

    pub fn complete(&self, id: &str, worker: &str) -> Result<Job, LeaseError> {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        match &job.state {
            JobState::Leased { worker: owner, .. } if owner == worker => {
                job.state = JobState::Completed;
                job.lease_until = None;
                Ok(job.clone())
            }
            _ => Err(LeaseError::NotLeasable),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn duplicate_lease_is_rejected_and_owner_can_complete() {
        let store = JobStore::default();
        store.enqueue("j1", "tenant-a", "replay");
        assert!(store.lease("j1", "worker-a").is_ok());
        assert_eq!(store.lease("j1", "worker-b"), Err(LeaseError::NotLeasable));
        assert!(store.complete("j1", "worker-a").is_ok());
    }

    #[test]
    fn cancellation_is_terminal_and_prevents_completion() {
        let store = JobStore::default();
        store.enqueue("j2", "tenant-a", "evaluation");
        assert!(store.cancel("j2").is_ok());
        assert_eq!(store.lease("j2", "worker-a"), Err(LeaseError::NotLeasable));
        assert_eq!(store.cancel("j2"), Err(LeaseError::AlreadyCancelled));
    }

    #[test]
    fn protocol_version_is_explicit() {
        let store = JobStore::default();
        let job = store
            .submit(SubmitJob {
                protocol_version: PROTOCOL_VERSION,
                id: "j3".into(),
                tenant: "tenant-a".into(),
                kind: "report".into(),
            })
            .expect("current protocol is accepted");
        assert_eq!(job.state, JobState::Queued);
    }

    #[test]
    fn expired_lease_returns_to_queue_for_recovery() {
        let store = JobStore::default();
        store.enqueue("j4", "tenant-a", "replay");
        store.lease_for("j4", "worker-a", Duration::ZERO).unwrap();
        assert_eq!(store.reap_expired(Instant::now()), 1);
        assert!(store.lease("j4", "worker-b").is_ok());
    }

    #[test]
    fn only_the_lease_owner_can_renew() {
        let store = JobStore::default();
        store.enqueue("j5", "tenant-a", "eval");
        store.lease_for("j5", "worker-a", Duration::ZERO).unwrap();
        assert_eq!(
            store.renew("j5", "worker-b", Duration::from_secs(30)),
            Err(LeaseError::NotLeasable)
        );
        assert!(store
            .renew("j5", "worker-a", Duration::from_secs(30))
            .is_ok());
    }

    #[test]
    fn lineage_records_keep_revisions_explicit() {
        let run = Run {
            id: "run-1".into(),
            experiment_id: "exp-1".into(),
            dataset_revision: "dataset:sha256:1".into(),
            evaluator_revision: "eval:sha256:2".into(),
            model_revision: "model:sha256:3".into(),
            prompt_revision: "prompt:sha256:4".into(),
        };
        assert_ne!(run.dataset_revision, run.model_revision);
        assert!(!run.prompt_revision.is_empty());
    }
}
