package autoeval

import (
	"context"
	"crypto/tls"
	"database/sql"
	"encoding/json"
	"fmt"
	"regexp"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
)

type StoreConfig struct {
	Addr     string
	Database string
	Username string
	Password string
	Secure   bool
}

type Store struct {
	db       *sql.DB
	database string
}

func NewClickHouse(cfg StoreConfig) (*Store, error) {
	if cfg.Addr == "" {
		return nil, fmt.Errorf("CLICKHOUSE_ADDR is required")
	}
	if cfg.Database == "" {
		cfg.Database = "frankengate_analytics"
	}
	if !regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`).MatchString(cfg.Database) {
		return nil, fmt.Errorf("invalid ClickHouse database name %q", cfg.Database)
	}
	protocol := clickhouse.HTTP
	var tlsConfig *tls.Config
	if cfg.Secure {
		tlsConfig = &tls.Config{MinVersion: tls.VersionTLS12}
	}
	db := clickhouse.OpenDB(&clickhouse.Options{Addr: []string{cfg.Addr}, Auth: clickhouse.Auth{Database: "default", Username: cfg.Username, Password: cfg.Password}, Protocol: protocol, DialTimeout: 10 * time.Second, TLS: tlsConfig})
	return &Store{db: db, database: cfg.Database}, nil
}

func (s *Store) Ping(ctx context.Context) error { return s.db.PingContext(ctx) }

func (s *Store) Close() error { return s.db.Close() }

func (s *Store) Migrate(ctx context.Context) error {
	statements := []string{
		fmt.Sprintf(`CREATE DATABASE IF NOT EXISTS %s`, s.database),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.trace_runs (
			tenant_id String, trace_id String, source String, source_revision String, source_digest String, task_family String,
			harness_revision String, model_revision String, skill_revision String,
			kb_revision String, privacy_receipt_id String, loss_receipt_id String,
			deletion_subject String, outcome_status String, outcome_observed UInt8,
			eligible UInt8, created_at DateTime64(3)
		) ENGINE = ReplacingMergeTree(created_at) ORDER BY (tenant_id, trace_id)`, s.database),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.trace_events (
			tenant_id String, trace_id String, event_id String, sequence UInt32,
			parent_event_id String, kind String, observation_status String,
			source_role String, tool_name String, skill_name String,
			knowledge_base String, content_digest String, arguments_digest String,
			result_digest String, observed_at DateTime64(3), created_at DateTime64(3)
		) ENGINE = ReplacingMergeTree(created_at) ORDER BY (tenant_id, trace_id, event_id)`, s.database),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.autoeval_scores (
			tenant_id String, case_id String, candidate_id String, trace_id String,
			rubric_id String, value Int8, confidence Float32, abstain UInt8,
			hard_violations Array(String), dimension_scores_json String,
			evidence_event_ids Array(String), created_at DateTime64(3)
		) ENGINE = ReplacingMergeTree(created_at) ORDER BY (tenant_id, trace_id, case_id, candidate_id)`, s.database),
	}
	for _, statement := range statements {
		if _, err := s.db.ExecContext(ctx, statement); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) InsertTrace(ctx context.Context, t PreparedTrace) error {
	if _, err := s.db.ExecContext(ctx, fmt.Sprintf(`INSERT INTO %s.trace_runs (tenant_id, trace_id, source, source_revision, source_digest, task_family, harness_revision, model_revision, skill_revision, kb_revision, privacy_receipt_id, loss_receipt_id, deletion_subject, outcome_status, outcome_observed, eligible, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, s.database), t.TenantID, t.TraceID, t.Source, t.SourceRevision, t.SourceDigest, t.TaskFamily, t.HarnessRevision, t.ModelRevision, t.SkillRevision, t.KBRevision, t.PrivacyReceipt, t.LossReceipt, t.DeletionSubject, t.OutcomeStatus, t.OutcomeObserved, t.Eligible, t.CreatedAt); err != nil {
		return err
	}
	for _, event := range t.Events {
		if _, err := s.db.ExecContext(ctx, fmt.Sprintf(`INSERT INTO %s.trace_events (tenant_id, trace_id, event_id, sequence, parent_event_id, kind, observation_status, source_role, tool_name, skill_name, knowledge_base, content_digest, arguments_digest, result_digest, observed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, s.database), t.TenantID, event.TraceID, event.EventID, event.Sequence, event.ParentEventID, event.Kind, event.Observation, event.SourceRole, event.ToolName, event.SkillName, event.KnowledgeBase, event.ContentDigest, event.ArgumentsDigest, event.ResultDigest, event.ObservedAt, t.CreatedAt); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) InsertJudgment(ctx context.Context, tenantID string, j Judgment) error {
	_, err := s.db.ExecContext(ctx, fmt.Sprintf(`INSERT INTO %s.autoeval_scores (tenant_id, case_id, candidate_id, trace_id, rubric_id, value, confidence, abstain, hard_violations, dimension_scores_json, evidence_event_ids, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, s.database), tenantID, j.CaseID, j.CandidateID, j.TraceID, j.RubricID, j.Value, j.Confidence, j.Abstain, j.HardViolations, marshalDimensions(j.DimensionScores), j.EvidenceEventIDs, j.CreatedAt)
	return err
}

func (s *Store) EvaluationReport(ctx context.Context, tenantID, traceID string) (EvaluationReport, error) {
	report := EvaluationReport{TenantID: tenantID, TraceID: traceID, ValueHistogram: make(map[int]int)}
	query := fmt.Sprintf(`SELECT value, abstain, length(hard_violations) FROM %s.autoeval_scores FINAL WHERE tenant_id = ?`, s.database)
	args := []any{tenantID}
	if traceID != "" {
		query += " AND trace_id = ?"
		args = append(args, traceID)
	}
	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return report, err
	}
	defer rows.Close()
	var total float64
	for rows.Next() {
		var value int8
		var abstain uint8
		var violationCount uint64
		if err := rows.Scan(&value, &abstain, &violationCount); err != nil {
			return report, err
		}
		report.JudgmentCount++
		if abstain != 0 {
			report.AbstentionCount++
			continue
		}
		report.ScoredCount++
		report.ValueHistogram[int(value)]++
		total += float64(value)
		if violationCount > 0 {
			report.HardViolationCount++
		}
	}
	if err := rows.Err(); err != nil {
		return report, err
	}
	if report.ScoredCount > 0 {
		report.MeanValue = total / float64(report.ScoredCount)
	}
	return report, nil
}

func marshalDimensions(values map[string]float64) string {
	b, err := json.Marshal(values)
	if err != nil {
		return "{}"
	}
	return string(b)
}
