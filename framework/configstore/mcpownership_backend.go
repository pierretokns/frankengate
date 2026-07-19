package configstore

// GORMMCPOwnershipBackend persists the backend-neutral MCP ownership envelope
// in the same Postgres/Aurora database used by governance.  It deliberately
// implements mcpownership.DurableBackend rather than the process-local Store:
// the MCP package can retain its fencing semantics while this adapter supplies
// transactional, cross-replica storage.

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/maximhq/bifrost/core/mcpownership"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

const MCPOwnershipTable = "mcp_connection_ownership"

// MCPOwnershipSchema is intentionally explicit so operators can apply it in
// an Aurora migration without requiring application-startup auto-migration.
// operations_json is JSONB on Postgres and TEXT on SQLite test databases.
const MCPOwnershipSchema = `CREATE TABLE IF NOT EXISTS mcp_connection_ownership (
 client_id TEXT NOT NULL,
 principal TEXT NOT NULL,
 session_key TEXT NOT NULL,
 version BIGINT NOT NULL,
 owner_pod TEXT NOT NULL DEFAULT '',
 fence BIGINT NOT NULL DEFAULT 0,
 lease_until TIMESTAMP WITH TIME ZONE NOT NULL,
 server_session_id TEXT NOT NULL DEFAULT '',
 session_resumable BOOLEAN NOT NULL DEFAULT FALSE,
 operations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
 PRIMARY KEY (client_id, principal, session_key)
)`

type mcpOwnershipRow struct {
	ClientID         string `gorm:"column:client_id;primaryKey"`
	Principal        string `gorm:"column:principal;primaryKey"`
	SessionKey       string `gorm:"column:session_key;primaryKey"`
	Version          uint64
	OwnerPod         string
	Fence            uint64
	LeaseUntil       int64
	ServerSessionID  string
	SessionResumable bool
	OperationsJSON   []byte `gorm:"column:operations_json;type:jsonb"`
}

func (mcpOwnershipRow) TableName() string { return MCPOwnershipTable }

// EnsureMCPOwnershipSchema creates the table. Call it from the existing
// migration transaction; production deployments should still version this DDL.
func EnsureMCPOwnershipSchema(ctx context.Context, db *gorm.DB) error {
	if db == nil {
		return errors.New("mcp ownership: nil database")
	}
	ddl := MCPOwnershipSchema
	if db.Dialector.Name() != "postgres" {
		// SQLite does not understand JSONB or timestamptz syntax.
		ddl = `CREATE TABLE IF NOT EXISTS mcp_connection_ownership (
 client_id TEXT NOT NULL, principal TEXT NOT NULL, session_key TEXT NOT NULL,
 version INTEGER NOT NULL, owner_pod TEXT NOT NULL DEFAULT '', fence INTEGER NOT NULL DEFAULT 0,
 lease_until INTEGER NOT NULL, server_session_id TEXT NOT NULL DEFAULT '',
 session_resumable INTEGER NOT NULL DEFAULT 0, operations_json TEXT NOT NULL DEFAULT '[]',
 PRIMARY KEY (client_id, principal, session_key))`
	}
	return db.WithContext(ctx).Exec(ddl).Error
}

// NewGORMMCPOwnershipBackend returns a shared durable backend over db.
func NewGORMMCPOwnershipBackend(db *gorm.DB) *GORMMCPOwnershipBackend {
	return &GORMMCPOwnershipBackend{db: db}
}

type GORMMCPOwnershipBackend struct{ db *gorm.DB }

func (b *GORMMCPOwnershipBackend) Read(ctx context.Context, key mcpownership.ConnectionKey) (mcpownership.DurableRecord, error) {
	if b == nil || b.db == nil {
		return mcpownership.DurableRecord{}, errors.New("mcp ownership: nil database")
	}
	var row mcpOwnershipRow
	err := b.db.WithContext(ctx).Where("client_id = ? AND principal = ? AND session_key = ?", key.ClientID, key.Principal, key.SessionKey).First(&row).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return mcpownership.DurableRecord{}, mcpownership.ErrNotFound
	}
	if err != nil {
		return mcpownership.DurableRecord{}, err
	}
	return rowRecord(row)
}

func (b *GORMMCPOwnershipBackend) Write(ctx context.Context, expectedVersion uint64, record mcpownership.DurableRecord) error {
	if b == nil || b.db == nil {
		return errors.New("mcp ownership: nil database")
	}
	if record.Key.ClientID == "" || record.Key.Principal == "" || record.Key.SessionKey == "" {
		return mcpownership.ErrInvalidClaim
	}
	ops, err := json.Marshal(record.Operations)
	if err != nil {
		return err
	}
	row := mcpOwnershipRow{ClientID: record.Key.ClientID, Principal: record.Key.Principal, SessionKey: record.Key.SessionKey, Version: record.Version, OwnerPod: record.OwnerPod, Fence: record.Fence, LeaseUntil: record.LeaseUntil.UnixNano(), ServerSessionID: record.ServerSessionID, SessionResumable: record.SessionResumable, OperationsJSON: ops}
	return b.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var current mcpOwnershipRow
		err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).Where("client_id = ? AND principal = ? AND session_key = ?", record.Key.ClientID, record.Key.Principal, record.Key.SessionKey).First(&current).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			if expectedVersion != 0 || record.Version != 1 {
				return mcpownership.ErrVersionConflict
			}
			return tx.Create(&row).Error
		}
		if err != nil {
			return err
		}
		if current.Version == record.Version && current.Fence == record.Fence && current.OwnerPod == record.OwnerPod && string(current.OperationsJSON) == string(ops) {
			return nil
		}
		if current.Version != expectedVersion {
			return mcpownership.ErrVersionConflict
		}
		if record.Fence < current.Fence {
			return mcpownership.ErrFenceRegression
		}
		if record.Version != expectedVersion+1 {
			return mcpownership.ErrVersionConflict
		}
		return tx.Model(&current).Where("client_id = ? AND principal = ? AND session_key = ? AND version = ?", record.Key.ClientID, record.Key.Principal, record.Key.SessionKey, expectedVersion).Updates(map[string]any{"version": record.Version, "owner_pod": record.OwnerPod, "fence": record.Fence, "lease_until": row.LeaseUntil, "server_session_id": record.ServerSessionID, "session_resumable": record.SessionResumable, "operations_json": ops}).Error
	})
}

func rowRecord(row mcpOwnershipRow) (mcpownership.DurableRecord, error) {
	var ops []mcpownership.DurableOperation
	if len(row.OperationsJSON) > 0 {
		if err := json.Unmarshal(row.OperationsJSON, &ops); err != nil {
			return mcpownership.DurableRecord{}, err
		}
	}
	return mcpownership.DurableRecord{Key: mcpownership.ConnectionKey{ClientID: row.ClientID, Principal: row.Principal, SessionKey: row.SessionKey}, Version: row.Version, OwnerPod: row.OwnerPod, Fence: row.Fence, LeaseUntil: time.Unix(0, row.LeaseUntil), ServerSessionID: row.ServerSessionID, SessionResumable: row.SessionResumable, Operations: ops}, nil
}
