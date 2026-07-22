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

/// Normalized, redaction-aware input to replay. Concrete OTLP and log-store
/// adapters must convert their source records to this shape before enqueueing.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReplayTrace {
    pub trace_id: String,
    pub request_id: String,
    pub tenant: String,
    pub model: String,
    pub provider: String,
    pub input: String,
    pub output: String,
}

impl ReplayTrace {
    pub fn is_well_formed(&self) -> bool {
        !self.trace_id.is_empty()
            && !self.request_id.is_empty()
            && !self.tenant.is_empty()
            && !self.model.is_empty()
            && !self.provider.is_empty()
            && self.input.len() <= 1 << 20
            && self.output.len() <= 1 << 20
    }
}

/// Source selection is intentionally explicit: OTLP collectors and gateway
/// log stores have different query/auth contracts and must not be guessed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ReplaySource {
    OtlpHttp { endpoint: String },
    LogStore { endpoint: String },
}

impl ReplaySource {
    pub fn endpoint(&self) -> &str {
        match self {
            Self::OtlpHttp { endpoint } | Self::LogStore { endpoint } => endpoint,
        }
    }

    pub fn is_configured(&self) -> bool {
        let endpoint = self.endpoint();
        (endpoint.starts_with("http://") || endpoint.starts_with("https://"))
            && endpoint.len() <= 2048
    }
}

/// Reader for the gateway's existing `plugins/otel` JSONLReplayStore. The Go
/// side partitions files by sanitized tenant and appends one ReplayRecord per
/// line; this adapter intentionally extracts only the stable envelope and
/// treats the original record as the replay payload. It has no network or
/// inference-path dependency.
pub struct JsonlReplaySource {
    directory: std::path::PathBuf,
    max_bytes: u64,
}

impl JsonlReplaySource {
    pub fn new(directory: impl Into<std::path::PathBuf>) -> Self {
        Self {
            directory: directory.into(),
            max_bytes: 64 * 1024 * 1024,
        }
    }

    pub fn read_tenant(&self, tenant: &str, limit: usize) -> Result<Vec<ReplayTrace>, String> {
        if tenant.is_empty() || limit == 0 || limit > 1_000 {
            return Err("invalid tenant or limit".into());
        }
        let path = self.directory.join(safe_tenant(tenant) + ".jsonl");
        let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
        if metadata.len() > self.max_bytes {
            return Err("replay file exceeds configured bound".into());
        }
        let content = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        let mut traces = Vec::new();
        for line in content.lines().rev() {
            if traces.len() == limit {
                break;
            }
            if line.len() > (1 << 20) {
                continue;
            }
            let tenant_id = json_string_field(line, "tenant_id");
            if tenant_id.as_deref() != Some(tenant) {
                continue;
            }
            let trace_id = json_string_field(line, "trace_id").unwrap_or_default();
            let request_id =
                json_string_field(line, "request_id").unwrap_or_else(|| trace_id.clone());
            if trace_id.is_empty() || request_id.is_empty() {
                continue;
            }
            traces.push(ReplayTrace {
                trace_id,
                request_id,
                tenant: tenant.to_string(),
                model: json_string_field(line, "model").unwrap_or_else(|| "unknown".into()),
                provider: json_string_field(line, "provider").unwrap_or_else(|| "unknown".into()),
                input: line.to_string(),
                output: line.to_string(),
            });
        }
        Ok(traces)
    }
}

fn safe_tenant(tenant: &str) -> String {
    tenant
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.') {
                c
            } else {
                '_'
            }
        })
        .collect()
}

fn json_string_field(line: &str, key: &str) -> Option<String> {
    let marker = format!("\"{}\":\"", key);
    let start = line.find(&marker)? + marker.len();
    let bytes = line.as_bytes();
    let mut out = String::new();
    let mut escaped = false;
    for &byte in &bytes[start..] {
        let ch = byte as char;
        if escaped {
            out.push(match ch {
                '"' => '"',
                '\\' => '\\',
                'n' => '\n',
                'r' => '\r',
                't' => '\t',
                _ => ch,
            });
            escaped = false;
        } else if ch == '\\' {
            escaped = true;
        } else if ch == '"' {
            return Some(out);
        } else {
            out.push(ch);
        }
    }
    None
}

/// Runs a dependency-free smoke check for operators and release automation.
/// This intentionally exercises only the protocol contract; it does not claim
/// that the in-memory store is a production persistence implementation.
pub fn contract_self_check() -> Result<(), &'static str> {
    let store = JobStore::with_capacity(2);
    let job = store
        .submit(SubmitJob {
            protocol_version: PROTOCOL_VERSION,
            id: "self-check".into(),
            tenant: "self-check-tenant".into(),
            kind: "contract".into(),
        })
        .map_err(|_| "protocol version rejected")?;
    if job.state != JobState::Queued {
        return Err("submitted job was not queued");
    }
    let leased = store
        .lease("self-check", "self-check-worker")
        .map_err(|_| "job could not be leased")?;
    if leased.attempt != 1 {
        return Err("first lease did not increment attempt");
    }
    let completed = store
        .complete("self-check", "self-check-worker")
        .map_err(|_| "leased job could not be completed")?;
    if completed.outcome().protocol_version != PROTOCOL_VERSION || !completed.outcome().terminal {
        return Err("terminal outcome is invalid");
    }
    Ok(())
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SubmitJob {
    pub protocol_version: u16,
    pub id: String,
    pub tenant: String,
    pub kind: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReplayJob {
    pub protocol_version: u16,
    pub replay_id: String,
    pub source_job_id: String,
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

impl Job {
    pub fn outcome(&self) -> JobOutcome {
        let (terminal, error_code) = match &self.state {
            JobState::Completed | JobState::Cancelled => (true, None),
            JobState::Failed { error_code } => (true, Some(error_code.clone())),
            JobState::Queued | JobState::Leased { .. } => (false, None),
        };
        JobOutcome {
            protocol_version: PROTOCOL_VERSION,
            id: self.id.clone(),
            attempt: self.attempt,
            terminal,
            error_code,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Experiment {
    pub id: String,
    pub tenant: String,
    pub actor: String,
    pub revision: String,
}

impl Experiment {
    pub fn is_well_formed(&self) -> bool {
        !self.id.is_empty()
            && !self.tenant.is_empty()
            && !self.actor.is_empty()
            && !self.revision.is_empty()
    }
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

impl Run {
    pub fn is_reproducible(&self) -> bool {
        !self.id.is_empty()
            && !self.experiment_id.is_empty()
            && !self.dataset_revision.is_empty()
            && !self.evaluator_revision.is_empty()
            && !self.model_revision.is_empty()
            && !self.prompt_revision.is_empty()
    }
}

/// A single execution attempt of a run.  Keeping attempts separate from the
/// run projection makes retries, lease recovery, and terminal evidence
/// addressable without mutating the requested run configuration.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunAttempt {
    pub id: String,
    pub run_id: String,
    pub attempt: u32,
    pub worker: String,
    pub job_id: String,
    pub outcome: Option<JobOutcome>,
}

impl RunAttempt {
    pub fn is_well_formed(&self) -> bool {
        !self.id.is_empty()
            && !self.run_id.is_empty()
            && self.attempt > 0
            && !self.worker.is_empty()
            && !self.job_id.is_empty()
            && self
                .outcome
                .as_ref()
                .is_none_or(|outcome| outcome.id == self.job_id)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EvaluationResult {
    pub run_id: String,
    pub example_id: String,
    pub score: String,
    pub evaluator_revision: String,
}

impl EvaluationResult {
    pub fn is_well_formed(&self) -> bool {
        !self.run_id.is_empty()
            && !self.example_id.is_empty()
            && !self.score.is_empty()
            && self.score.len() <= 256
            && !self.evaluator_revision.is_empty()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ArtifactManifest {
    pub run_id: String,
    pub digest: String,
    pub media_type: String,
    pub object_uri: String,
}

impl ArtifactManifest {
    pub fn is_well_formed(&self) -> bool {
        !self.run_id.is_empty()
            && !self.digest.is_empty()
            && self.digest.len() <= 256
            && !self.media_type.is_empty()
            && self.media_type.len() <= 256
            && (self.object_uri.starts_with("s3://") || self.object_uri.starts_with("file://"))
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct JobStats {
    pub queued: usize,
    pub leased: usize,
    pub cancelled: usize,
    pub completed: usize,
    pub failed: usize,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum JobState {
    Queued,
    Leased { worker: String, attempt: u32 },
    Cancelled,
    Completed,
    Failed { error_code: String },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Job {
    pub id: String,
    pub tenant: String,
    pub kind: String,
    pub state: JobState,
    /// Monotonically increasing delivery attempt, including recovered leases.
    pub attempt: u32,
    pub checkpoint: Option<String>,
    pub replay_of: Option<String>,
    lease_until: Option<Instant>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LeaseError {
    NotFound,
    NotLeasable,
    AlreadyCancelled,
    CheckpointTooLarge,
    CapacityExceeded,
    InvalidRequest,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum QueueError {
    CapacityExceeded,
    InvalidRequest,
}

#[derive(Clone, Default)]
pub struct JobStore {
    jobs: Arc<Mutex<HashMap<String, Job>>>,
    capacity: Option<usize>,
}

impl JobStore {
    /// Convert one normalized source trace into a replayable terminal job.
    /// Ingestion is deliberately separate from OTLP/log-store transport so
    /// source adapters can be added without changing queue semantics.
    pub fn ingest_replay_trace(&self, trace: &ReplayTrace) -> Result<Job, LeaseError> {
        if !trace.is_well_formed() {
            return Err(LeaseError::InvalidRequest);
        }
        self.submit(SubmitJob {
            protocol_version: PROTOCOL_VERSION,
            id: trace.request_id.clone(),
            tenant: trace.tenant.clone(),
            kind: "replay-source".into(),
        })
    }

    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            jobs: Arc::new(Mutex::new(HashMap::new())),
            capacity: Some(capacity),
        }
    }

    pub fn try_enqueue(
        &self,
        id: impl Into<String>,
        tenant: impl Into<String>,
        kind: impl Into<String>,
    ) -> Result<Job, QueueError> {
        let id = id.into();
        let tenant = tenant.into();
        let kind = kind.into();
        if id.is_empty() || tenant.is_empty() || kind.is_empty() {
            return Err(QueueError::InvalidRequest);
        }
        let job = Job {
            id: id.clone(),
            tenant,
            kind,
            state: JobState::Queued,
            attempt: 0,
            checkpoint: None,
            replay_of: None,
            lease_until: None,
        };
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        if let Some(existing) = jobs.get(&id) {
            return Ok(existing.clone());
        }
        if self.capacity.is_some_and(|capacity| jobs.len() >= capacity) {
            return Err(QueueError::CapacityExceeded);
        }
        jobs.insert(id, job.clone());
        Ok(job)
    }

    pub fn submit(&self, request: SubmitJob) -> Result<Job, LeaseError> {
        if request.protocol_version != PROTOCOL_VERSION
            || request.id.is_empty()
            || request.tenant.is_empty()
            || request.kind.is_empty()
        {
            return Err(LeaseError::InvalidRequest);
        }
        self.try_enqueue(request.id, request.tenant, request.kind)
            .map_err(|error| match error {
                QueueError::CapacityExceeded => LeaseError::CapacityExceeded,
                QueueError::InvalidRequest => LeaseError::InvalidRequest,
            })
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
            attempt: 0,
            checkpoint: None,
            replay_of: None,
            lease_until: None,
        };
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        if let Some(existing) = jobs.get(&job.id) {
            return existing.clone();
        }
        jobs.insert(job.id.clone(), job.clone());
        job
    }

    /// Enqueues a replay only for a terminal source job in the same tenant.
    pub fn replay(&self, request: ReplayJob) -> Result<Job, LeaseError> {
        if request.protocol_version != PROTOCOL_VERSION
            || request.replay_id.is_empty()
            || request.source_job_id.is_empty()
            || request.tenant.is_empty()
            || request.kind.is_empty()
        {
            return Err(LeaseError::InvalidRequest);
        }
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let source = jobs
            .get(&request.source_job_id)
            .ok_or(LeaseError::NotFound)?;
        if source.tenant != request.tenant || !source.outcome().terminal {
            return Err(LeaseError::NotLeasable);
        }
        if let Some(existing) = jobs.get(&request.replay_id) {
            return Ok(existing.clone());
        }
        if self.capacity.is_some_and(|capacity| jobs.len() >= capacity) {
            return Err(LeaseError::CapacityExceeded);
        }
        let job = Job {
            id: request.replay_id.clone(),
            tenant: request.tenant,
            kind: request.kind,
            state: JobState::Queued,
            attempt: 0,
            checkpoint: None,
            replay_of: Some(request.source_job_id),
            lease_until: None,
        };
        jobs.insert(request.replay_id, job.clone());
        Ok(job)
    }

    pub fn get(&self, id: &str) -> Option<Job> {
        self.jobs
            .lock()
            .expect("job store lock poisoned")
            .get(id)
            .cloned()
    }

    /// Return a deterministic, tenant-scoped snapshot bounded to 1,000 jobs.
    /// The bound is part of the contract so an API handler cannot accidentally
    /// turn a large queue into an unbounded response.
    pub fn list_for_tenant(&self, tenant: &str, limit: usize) -> Vec<Job> {
        let mut jobs: Vec<_> = self
            .jobs
            .lock()
            .expect("job store lock poisoned")
            .values()
            .filter(|job| job.tenant == tenant)
            .cloned()
            .collect();
        jobs.sort_by(|left, right| left.id.cmp(&right.id));
        jobs.truncate(limit.min(1_000));
        jobs
    }

    /// Return tenant-scoped queue counters suitable for scaling and dashboards.
    pub fn stats_for_tenant(&self, tenant: &str) -> JobStats {
        let jobs = self.jobs.lock().expect("job store lock poisoned");
        let mut stats = JobStats::default();
        for job in jobs.values().filter(|job| job.tenant == tenant) {
            match job.state {
                JobState::Queued => stats.queued += 1,
                JobState::Leased { .. } => stats.leased += 1,
                JobState::Cancelled => stats.cancelled += 1,
                JobState::Completed => stats.completed += 1,
                JobState::Failed { .. } => stats.failed += 1,
            }
        }
        stats
    }

    /// Return aggregate queue counters for worker-pool scaling signals.
    /// Counters are computed under one lock so a snapshot cannot mix states
    /// from different queue observations.
    pub fn stats(&self) -> JobStats {
        let jobs = self.jobs.lock().expect("job store lock poisoned");
        let mut stats = JobStats::default();
        for job in jobs.values() {
            match job.state {
                JobState::Queued => stats.queued += 1,
                JobState::Leased { .. } => stats.leased += 1,
                JobState::Cancelled => stats.cancelled += 1,
                JobState::Completed => stats.completed += 1,
                JobState::Failed { .. } => stats.failed += 1,
            }
        }
        stats
    }

    pub fn lease(&self, id: &str, worker: impl Into<String>) -> Result<Job, LeaseError> {
        self.lease_for(id, worker, Duration::from_secs(30))
    }

    /// Atomically claim the first queued job for a tenant.
    pub fn lease_next_for_tenant(
        &self,
        tenant: &str,
        worker: impl Into<String>,
        duration: Duration,
    ) -> Option<Job> {
        let worker = worker.into();
        if worker.is_empty() || tenant.is_empty() {
            return None;
        }
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let id = jobs
            .values()
            .filter(|job| job.tenant == tenant && matches!(job.state, JobState::Queued))
            .map(|job| job.id.clone())
            .min()?;
        let job = jobs.get_mut(&id)?;
        job.attempt = job.attempt.saturating_add(1);
        job.state = JobState::Leased {
            worker,
            attempt: job.attempt,
        };
        job.lease_until = Some(Instant::now() + duration);
        Some(job.clone())
    }

    pub fn lease_for(
        &self,
        id: &str,
        worker: impl Into<String>,
        duration: Duration,
    ) -> Result<Job, LeaseError> {
        let worker = worker.into();
        if worker.is_empty() || id.is_empty() {
            return Err(LeaseError::InvalidRequest);
        }
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        let attempt = match job.state {
            JobState::Queued => {
                job.attempt = job.attempt.saturating_add(1);
                job.attempt
            }
            JobState::Leased { .. } => return Err(LeaseError::NotLeasable),
            JobState::Cancelled | JobState::Completed | JobState::Failed { .. } => {
                return Err(LeaseError::NotLeasable)
            }
        };
        job.state = JobState::Leased { worker, attempt };
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

    /// Release all leases owned by a worker during graceful shutdown.
    pub fn drain_worker(&self, worker: &str) -> usize {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let mut drained = 0;
        for job in jobs.values_mut() {
            if matches!(&job.state, JobState::Leased { worker: owner, .. } if owner == worker) {
                job.state = JobState::Queued;
                job.lease_until = None;
                drained += 1;
            }
        }
        drained
    }

    pub fn renew(&self, id: &str, worker: &str, duration: Duration) -> Result<Job, LeaseError> {
        if id.is_empty() || worker.is_empty() {
            return Err(LeaseError::InvalidRequest);
        }
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

    /// Store a bounded progress checkpoint owned by the active lease holder.
    pub fn checkpoint(
        &self,
        id: &str,
        worker: &str,
        value: impl Into<String>,
    ) -> Result<Job, LeaseError> {
        let value = value.into();
        if value.len() > 4096 {
            return Err(LeaseError::CheckpointTooLarge);
        }
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        match &job.state {
            JobState::Leased { worker: owner, .. } if owner == worker => {
                job.checkpoint = Some(value);
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
        if matches!(job.state, JobState::Completed | JobState::Failed { .. }) {
            return Err(LeaseError::NotLeasable);
        }
        job.state = JobState::Cancelled;
        job.lease_until = None;
        Ok(job.clone())
    }

    /// Tenant-scoped cancellation boundary for API callers.
    pub fn cancel_for_tenant(&self, tenant: &str, id: &str) -> Result<Job, LeaseError> {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        if job.tenant != tenant {
            return Err(LeaseError::NotFound);
        }
        if job.state == JobState::Cancelled {
            return Err(LeaseError::AlreadyCancelled);
        }
        if matches!(job.state, JobState::Completed | JobState::Failed { .. }) {
            return Err(LeaseError::NotLeasable);
        }
        job.state = JobState::Cancelled;
        job.lease_until = None;
        Ok(job.clone())
    }

    /// Explicitly requeue a failed job for a tenant-authorized retry.
    pub fn retry_failed_for_tenant(&self, tenant: &str, id: &str) -> Result<Job, LeaseError> {
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        if job.tenant != tenant {
            return Err(LeaseError::NotFound);
        }
        if !matches!(job.state, JobState::Failed { .. }) {
            return Err(LeaseError::NotLeasable);
        }
        job.state = JobState::Queued;
        job.lease_until = None;
        Ok(job.clone())
    }

    pub fn complete(&self, id: &str, worker: &str) -> Result<Job, LeaseError> {
        if id.is_empty() || worker.is_empty() {
            return Err(LeaseError::InvalidRequest);
        }
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

    /// Mark a leased job as terminally failed with a bounded machine-readable code.
    pub fn fail(
        &self,
        id: &str,
        worker: &str,
        error_code: impl Into<String>,
    ) -> Result<Job, LeaseError> {
        let error_code = error_code.into();
        if id.is_empty() || worker.is_empty() {
            return Err(LeaseError::InvalidRequest);
        }
        if error_code.is_empty() || error_code.len() > 256 {
            return Err(LeaseError::CheckpointTooLarge);
        }
        let mut jobs = self.jobs.lock().expect("job store lock poisoned");
        let job = jobs.get_mut(id).ok_or(LeaseError::NotFound)?;
        match &job.state {
            JobState::Leased { worker: owner, .. } if owner == worker => {
                job.state = JobState::Failed { error_code };
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
    fn duplicate_delivery_does_not_reset_terminal_job() {
        let store = JobStore::default();
        store.enqueue("j1b", "tenant-a", "replay");
        store.lease("j1b", "worker-a").unwrap();
        store.complete("j1b", "worker-a").unwrap();
        let duplicate = store.enqueue("j1b", "tenant-a", "replay");
        assert_eq!(duplicate.state, JobState::Completed);
        assert_eq!(duplicate.attempt, 1);
        assert_eq!(store.lease("j1b", "worker-b"), Err(LeaseError::NotLeasable));
    }

    #[test]
    fn job_listing_is_tenant_scoped_deterministic_and_bounded() {
        let store = JobStore::default();
        store.enqueue("j3", "tenant-a", "eval");
        store.enqueue("j1", "tenant-a", "replay");
        store.enqueue("j2", "tenant-b", "eval");
        let jobs = store.list_for_tenant("tenant-a", 1_001);
        assert_eq!(jobs.len(), 2);
        assert_eq!(jobs[0].id, "j1");
        assert_eq!(jobs[1].id, "j3");
        assert!(store.list_for_tenant("tenant-c", 10).is_empty());
    }

    #[test]
    fn aggregate_stats_are_a_consistent_worker_scaling_snapshot() {
        let store = JobStore::default();
        store.enqueue("queued-a", "tenant-a", "eval");
        store.enqueue("queued-b", "tenant-b", "eval");
        store.enqueue("leased", "tenant-a", "eval");
        store.lease("leased", "worker-a").unwrap();
        store.enqueue("cancelled", "tenant-b", "eval");
        store.cancel("cancelled").unwrap();
        store.enqueue("completed", "tenant-a", "eval");
        store.lease("completed", "worker-a").unwrap();
        store.complete("completed", "worker-a").unwrap();
        assert_eq!(
            store.stats(),
            JobStats {
                queued: 2,
                leased: 1,
                cancelled: 1,
                completed: 1,
                failed: 0,
            }
        );
    }

    #[test]
    fn tenant_scoped_cancellation_cannot_cross_tenant_boundary() {
        let store = JobStore::default();
        store.enqueue("j4b", "tenant-a", "eval");
        assert_eq!(
            store.cancel_for_tenant("tenant-b", "j4b"),
            Err(LeaseError::NotFound)
        );
        assert_eq!(store.get("j4b").unwrap().state, JobState::Queued);
        assert_eq!(
            store.cancel_for_tenant("tenant-a", "j4b").unwrap().state,
            JobState::Cancelled
        );
    }

    #[test]
    fn worker_drain_releases_owned_leases_for_recovery() {
        let store = JobStore::default();
        store.enqueue("j5b", "tenant-a", "eval");
        store.enqueue("j6b", "tenant-a", "replay");
        store.lease("j5b", "worker-a").unwrap();
        store.lease("j6b", "worker-b").unwrap();
        assert_eq!(store.drain_worker("worker-a"), 1);
        assert_eq!(store.lease("j5b", "worker-c").unwrap().attempt, 2);
        assert_eq!(store.drain_worker("worker-a"), 0);
        assert!(matches!(
            store.get("j6b").unwrap().state,
            JobState::Leased { .. }
        ));
    }

    #[test]
    fn checkpoints_are_owner_scoped_and_bounded() {
        let store = JobStore::default();
        store.enqueue("j7b", "tenant-a", "eval");
        store.lease("j7b", "worker-a").unwrap();
        assert_eq!(
            store.checkpoint("j7b", "worker-b", "wrong"),
            Err(LeaseError::NotLeasable)
        );
        assert_eq!(
            store
                .checkpoint("j7b", "worker-a", "step:42")
                .unwrap()
                .checkpoint,
            Some("step:42".into())
        );
        assert_eq!(
            store.checkpoint("j7b", "worker-a", "x".repeat(4097)),
            Err(LeaseError::CheckpointTooLarge)
        );
    }

    #[test]
    fn lease_next_claims_one_deterministic_tenant_job_atomically() {
        let store = JobStore::default();
        store.enqueue("j9", "tenant-a", "eval");
        store.enqueue("j8", "tenant-a", "replay");
        store.enqueue("j7", "tenant-b", "eval");
        assert_eq!(
            store
                .lease_next_for_tenant("tenant-a", "worker-a", Duration::from_secs(30))
                .unwrap()
                .id,
            "j8"
        );
        assert_eq!(
            store
                .lease_next_for_tenant("tenant-a", "worker-b", Duration::from_secs(30))
                .unwrap()
                .id,
            "j9"
        );
        assert!(store
            .lease_next_for_tenant("tenant-a", "worker-c", Duration::from_secs(30))
            .is_none());
        assert_eq!(
            store.stats_for_tenant("tenant-a"),
            JobStats {
                leased: 2,
                ..JobStats::default()
            }
        );
    }

    #[test]
    fn bounded_enqueue_rejects_new_jobs_but_keeps_duplicate_idempotent() {
        let store = JobStore::with_capacity(1);
        store.try_enqueue("j11", "tenant-a", "eval").unwrap();
        assert_eq!(
            store.try_enqueue("j12", "tenant-a", "eval"),
            Err(QueueError::CapacityExceeded)
        );
        assert_eq!(
            store.try_enqueue("j11", "tenant-a", "eval").unwrap().id,
            "j11"
        );
    }

    #[test]
    fn bounded_enqueue_rejects_empty_identity_fields() {
        let store = JobStore::with_capacity(1);
        assert_eq!(
            store.try_enqueue("", "tenant-a", "eval"),
            Err(QueueError::InvalidRequest)
        );
        assert_eq!(
            store.try_enqueue("job-a", "", "eval"),
            Err(QueueError::InvalidRequest)
        );
        assert_eq!(
            store.try_enqueue("job-a", "tenant-a", ""),
            Err(QueueError::InvalidRequest)
        );
    }

    #[test]
    fn worker_failure_is_terminal_and_owner_scoped() {
        let store = JobStore::default();
        store.enqueue("j10", "tenant-a", "eval");
        store.lease("j10", "worker-a").unwrap();
        assert_eq!(
            store.fail("j10", "worker-b", "model_timeout"),
            Err(LeaseError::NotLeasable)
        );
        let failed = store.fail("j10", "worker-a", "model_timeout").unwrap();
        assert_eq!(
            failed.state,
            JobState::Failed {
                error_code: "model_timeout".into()
            }
        );
        assert_eq!(store.lease("j10", "worker-c"), Err(LeaseError::NotLeasable));
        let outcome = store.get("j10").unwrap().outcome();
        assert!(outcome.terminal);
        assert_eq!(outcome.error_code.as_deref(), Some("model_timeout"));
        assert_eq!(outcome.protocol_version, PROTOCOL_VERSION);
        assert_eq!(
            store.retry_failed_for_tenant("tenant-b", "j10"),
            Err(LeaseError::NotFound)
        );
        assert_eq!(
            store
                .retry_failed_for_tenant("tenant-a", "j10")
                .unwrap()
                .state,
            JobState::Queued
        );
        assert_eq!(store.lease("j10", "worker-c").unwrap().attempt, 2);
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
    fn protocol_submit_honors_bounded_capacity() {
        let store = JobStore::with_capacity(1);
        store
            .submit(SubmitJob {
                protocol_version: PROTOCOL_VERSION,
                id: "first".into(),
                tenant: "tenant-a".into(),
                kind: "eval".into(),
            })
            .unwrap();
        assert_eq!(
            store.submit(SubmitJob {
                protocol_version: PROTOCOL_VERSION,
                id: "second".into(),
                tenant: "tenant-a".into(),
                kind: "eval".into(),
            }),
            Err(LeaseError::CapacityExceeded)
        );
    }

    #[test]
    fn lease_completion_and_failure_require_named_workers() {
        let store = JobStore::default();
        store.enqueue("worker-bound", "tenant-a", "eval");
        assert_eq!(
            store.lease("worker-bound", ""),
            Err(LeaseError::InvalidRequest)
        );
        store.lease("worker-bound", "worker-a").unwrap();
        assert_eq!(
            store.complete("worker-bound", ""),
            Err(LeaseError::InvalidRequest)
        );
        assert_eq!(
            store.fail("worker-bound", "", "failed"),
            Err(LeaseError::InvalidRequest)
        );
    }

    #[test]
    fn submitted_and_replayed_jobs_reject_empty_identity_fields() {
        let store = JobStore::default();
        assert_eq!(
            store.submit(SubmitJob {
                protocol_version: PROTOCOL_VERSION,
                id: String::new(),
                tenant: "tenant-a".into(),
                kind: "eval".into(),
            }),
            Err(LeaseError::InvalidRequest)
        );
        assert_eq!(
            store.replay(ReplayJob {
                protocol_version: PROTOCOL_VERSION,
                replay_id: "replay-1".into(),
                source_job_id: String::new(),
                tenant: "tenant-a".into(),
                kind: "eval".into(),
            }),
            Err(LeaseError::InvalidRequest)
        );
    }

    #[test]
    fn expired_lease_returns_to_queue_for_recovery() {
        let store = JobStore::default();
        store.enqueue("j4", "tenant-a", "replay");
        let first = store.lease_for("j4", "worker-a", Duration::ZERO).unwrap();
        assert_eq!(first.attempt, 1);
        assert_eq!(store.reap_expired(Instant::now()), 1);
        let recovered = store.lease("j4", "worker-b").unwrap();
        assert_eq!(recovered.attempt, 2);
        store.reap_expired(Instant::now() + Duration::from_secs(31));
        let recovered_again = store.lease("j4", "worker-c").unwrap();
        assert_eq!(recovered_again.attempt, 3);
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
        assert!(run.is_reproducible());
        let attempt = RunAttempt {
            id: "attempt-1".into(),
            run_id: run.id.clone(),
            attempt: 1,
            worker: "eval-worker-a".into(),
            job_id: "job-1".into(),
            outcome: None,
        };
        assert!(attempt.is_well_formed());
        assert!(!RunAttempt {
            attempt: 0,
            ..attempt.clone()
        }
        .is_well_formed());
        let experiment = Experiment {
            id: run.experiment_id.clone(),
            tenant: "tenant-a".into(),
            actor: "user-a".into(),
            revision: "exp:sha256:1".into(),
        };
        assert!(experiment.is_well_formed());
        assert!(!Experiment {
            actor: "".into(),
            ..experiment.clone()
        }
        .is_well_formed());
        let mut incomplete = run.clone();
        incomplete.model_revision.clear();
        assert!(!incomplete.is_reproducible());
        assert!(EvaluationResult {
            run_id: run.id.clone(),
            example_id: "example-1".into(),
            score: "0.95".into(),
            evaluator_revision: run.evaluator_revision.clone(),
        }
        .is_well_formed());
        assert!(!EvaluationResult {
            run_id: run.id.clone(),
            example_id: "".into(),
            score: "0.95".into(),
            evaluator_revision: "eval:sha256:2".into(),
        }
        .is_well_formed());
        let artifact = ArtifactManifest {
            run_id: run.id,
            digest: "sha256:abc".into(),
            media_type: "application/json".into(),
            object_uri: "s3://frankengate/run-1/result.json".into(),
        };
        assert!(artifact.is_well_formed());
        assert!(!ArtifactManifest {
            run_id: "run-1".into(),
            digest: "".into(),
            media_type: "application/json".into(),
            object_uri: "https://unapproved.example/object".into(),
        }
        .is_well_formed());
    }

    #[test]
    fn replay_requires_terminal_same_tenant_source_and_preserves_lineage() {
        let store = JobStore::default();
        store.enqueue("source", "tenant-a", "evaluation");
        assert_eq!(
            store.replay(ReplayJob {
                protocol_version: PROTOCOL_VERSION,
                replay_id: "replay-before-terminal".into(),
                source_job_id: "source".into(),
                tenant: "tenant-a".into(),
                kind: "replay".into(),
            }),
            Err(LeaseError::NotLeasable)
        );
        store.lease("source", "worker-a").unwrap();
        store.complete("source", "worker-a").unwrap();
        assert_eq!(
            store.replay(ReplayJob {
                protocol_version: PROTOCOL_VERSION,
                replay_id: "replay-cross-tenant".into(),
                source_job_id: "source".into(),
                tenant: "tenant-b".into(),
                kind: "replay".into(),
            }),
            Err(LeaseError::NotLeasable)
        );
        let replay = store
            .replay(ReplayJob {
                protocol_version: PROTOCOL_VERSION,
                replay_id: "replay-1".into(),
                source_job_id: "source".into(),
                tenant: "tenant-a".into(),
                kind: "replay".into(),
            })
            .unwrap();
        assert_eq!(replay.replay_of.as_deref(), Some("source"));
        assert_eq!(
            store
                .replay(ReplayJob {
                    protocol_version: PROTOCOL_VERSION,
                    replay_id: "replay-1".into(),
                    source_job_id: "source".into(),
                    tenant: "tenant-a".into(),
                    kind: "replay".into(),
                })
                .unwrap()
                .id,
            "replay-1"
        );

        let bounded = JobStore::with_capacity(1);
        bounded.enqueue("source", "tenant-a", "evaluation");
        bounded.lease("source", "worker-a").unwrap();
        bounded.complete("source", "worker-a").unwrap();
        assert_eq!(
            bounded.replay(ReplayJob {
                protocol_version: PROTOCOL_VERSION,
                replay_id: "replay-over-capacity".into(),
                source_job_id: "source".into(),
                tenant: "tenant-a".into(),
                kind: "replay".into(),
            }),
            Err(LeaseError::CapacityExceeded)
        );
    }

    #[test]
    fn replay_trace_boundary_accepts_normalized_otel_shape() {
        let trace = ReplayTrace {
            trace_id: "trace-1".into(),
            request_id: "request-1".into(),
            tenant: "tenant-a".into(),
            model: "gpt-5.5".into(),
            provider: "bedrock_mantle".into(),
            input: "{\"input\":[]}".into(),
            output: "{\"output\":[]}".into(),
        };
        assert!(trace.is_well_formed());
        assert!(!ReplayTrace {
            request_id: "".into(),
            ..trace.clone()
        }
        .is_well_formed());

        let store = JobStore::default();
        let job = store.ingest_replay_trace(&trace).unwrap();
        assert_eq!(job.id, "request-1");
        assert_eq!(job.kind, "replay-source");
        assert_eq!(job.tenant, "tenant-a");
    }

    #[test]
    fn replay_source_requires_explicit_http_endpoint() {
        assert!(ReplaySource::OtlpHttp {
            endpoint: "https://otel.example/v1/traces".into()
        }
        .is_configured());
        assert!(ReplaySource::LogStore {
            endpoint: "http://logstore.example/replay".into()
        }
        .is_configured());
        assert!(!ReplaySource::OtlpHttp {
            endpoint: "collector.internal".into()
        }
        .is_configured());
    }

    #[test]
    fn jsonl_replay_source_reads_gateway_partition_and_enforces_tenant() {
        let dir = std::env::temp_dir().join(format!("frankengate-replay-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        std::fs::write(
            dir.join("tenant-a.jsonl"),
            "{\"schema_version\":1,\"trace_id\":\"trace-1\",\"request_id\":\"req-1\",\"tenant_id\":\"tenant-a\",\"model\":\"gpt-5.5\"}\n",
        )
        .unwrap();
        let traces = JsonlReplaySource::new(&dir)
            .read_tenant("tenant-a", 10)
            .unwrap();
        assert_eq!(traces.len(), 1);
        assert_eq!(traces[0].trace_id, "trace-1");
        assert_eq!(traces[0].model, "gpt-5.5");
        assert!(JsonlReplaySource::new(&dir)
            .read_tenant("tenant-b", 10)
            .is_err());
        let _ = std::fs::remove_dir_all(dir);
    }
}
