package configstore

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// ConfigChangefeedEvent is the durable, commit-ordered unit consumed by pods.
// Cursor is a generation-local commit cursor; callers must never substitute a
// bare database sequence for it.
type ConfigChangefeedEvent struct {
	Generation uint64    `gorm:"column:generation;primaryKey" json:"generation"`
	Cursor     uint64    `gorm:"column:cursor;primaryKey" json:"cursor"`
	Scope      string    `gorm:"column:scope;primaryKey;type:varchar(255)" json:"scope"`
	Kind       string    `gorm:"column:kind;type:varchar(64);not null" json:"kind"`
	Entity     string    `gorm:"column:entity;type:varchar(255);not null" json:"entity"`
	Payload    []byte    `gorm:"column:payload;type:blob;not null" json:"payload"`
	PayloadSHA string    `gorm:"column:payload_sha256;type:char(64);not null" json:"payload_sha256"`
	CreatedAt  time.Time `gorm:"column:created_at;not null" json:"created_at"`
}

func (ConfigChangefeedEvent) TableName() string { return "config_changefeed_events" }

// ConfigChangefeedGeneration is the scoped authority row. The row is locked
// during appends so a generation is complete before any event becomes visible.
type ConfigChangefeedGeneration struct {
	Scope         string    `gorm:"column:scope;primaryKey;type:varchar(255)" json:"scope"`
	Generation    uint64    `gorm:"column:generation;not null" json:"generation"`
	NextCursor    uint64    `gorm:"column:next_cursor;not null" json:"next_cursor"`
	RetainedFloor uint64    `gorm:"column:retained_floor;not null" json:"retained_floor"`
	UpdatedAt     time.Time `gorm:"column:updated_at;not null" json:"updated_at"`
}

// ConfigChangefeedCursorTooOldError means the consumer fell behind the
// retained event window and must load a fenced snapshot before resuming.
type ConfigChangefeedCursorTooOldError struct {
	Scope         string
	Generation    uint64
	Cursor        uint64
	RetainedFloor uint64
}

func (e *ConfigChangefeedCursorTooOldError) Error() string {
	return fmt.Sprintf("config changefeed cursor is below retained floor: scope=%s generation=%d cursor=%d floor=%d", e.Scope, e.Generation, e.Cursor, e.RetainedFloor)
}

func (ConfigChangefeedGeneration) TableName() string { return "config_changefeed_generations" }

// EnsureConfigChangefeedSchema creates the additive compatibility schema. It is
// intentionally explicit so rollout code can run it under the same migration
// lock as the rest of configstore in a later integration bead.
func EnsureConfigChangefeedSchema(ctx context.Context, db *gorm.DB) error {
	if db == nil {
		return errors.New("config changefeed database is required")
	}
	if err := db.WithContext(ctx).AutoMigrate(&ConfigChangefeedGeneration{}, &ConfigChangefeedEvent{}); err != nil {
		return fmt.Errorf("migrate config changefeed schema: %w", err)
	}
	return nil
}

// AppendConfigChangefeed atomically appends a complete generation. The caller
// must invoke it inside the same transaction as its authoritative mutation.
func AppendConfigChangefeed(ctx context.Context, tx *gorm.DB, scope, kind, entity string, payload []byte) (ConfigChangefeedEvent, error) {
	if tx == nil {
		return ConfigChangefeedEvent{}, errors.New("config changefeed transaction is required")
	}
	scope, kind, entity = strings.TrimSpace(scope), strings.TrimSpace(kind), strings.TrimSpace(entity)
	if scope == "" || kind == "" || entity == "" {
		return ConfigChangefeedEvent{}, errors.New("config changefeed scope, kind, and entity are required")
	}
	if payload == nil {
		return ConfigChangefeedEvent{}, errors.New("config changefeed payload is required")
	}
	var generation ConfigChangefeedGeneration
	q := tx.WithContext(ctx).Clauses(clause.Locking{Strength: "UPDATE"}).Where("scope = ?", scope).First(&generation)
	if errors.Is(q.Error, gorm.ErrRecordNotFound) {
		generation = ConfigChangefeedGeneration{Scope: scope, Generation: 1, NextCursor: 1, RetainedFloor: 1, UpdatedAt: time.Now().UTC()}
		if err := tx.WithContext(ctx).Create(&generation).Error; err != nil {
			return ConfigChangefeedEvent{}, fmt.Errorf("create config changefeed generation: %w", err)
		}
	} else if q.Error != nil {
		return ConfigChangefeedEvent{}, q.Error
	}
	hash := sha256.Sum256(payload)
	event := ConfigChangefeedEvent{Generation: generation.Generation, Cursor: generation.NextCursor, Scope: scope, Kind: kind, Entity: entity, Payload: append([]byte(nil), payload...), PayloadSHA: hex.EncodeToString(hash[:]), CreatedAt: time.Now().UTC()}
	if err := tx.WithContext(ctx).Create(&event).Error; err != nil {
		return ConfigChangefeedEvent{}, fmt.Errorf("append config changefeed event: %w", err)
	}
	generation.NextCursor++
	generation.UpdatedAt = event.CreatedAt
	if err := tx.WithContext(ctx).Save(&generation).Error; err != nil {
		return ConfigChangefeedEvent{}, fmt.Errorf("advance config changefeed cursor: %w", err)
	}
	return event, nil
}

// RetainConfigChangefeedFrom advances the durable floor and deletes events
// before it in the same transaction. The floor is monotonic and generation
// scoped; a caller must coordinate this with its snapshot/admission fence.
func RetainConfigChangefeedFrom(ctx context.Context, tx *gorm.DB, scope string, generation, floor uint64) error {
	if tx == nil || strings.TrimSpace(scope) == "" || generation == 0 || floor == 0 {
		return errors.New("valid config changefeed transaction, scope, generation, and floor are required")
	}
	var row ConfigChangefeedGeneration
	q := tx.WithContext(ctx).Clauses(clause.Locking{Strength: "UPDATE"}).Where("scope = ?", scope).First(&row)
	if q.Error != nil {
		return q.Error
	}
	if row.Generation != generation {
		return fmt.Errorf("config changefeed generation mismatch: scope=%s expected=%d actual=%d", scope, generation, row.Generation)
	}
	if floor <= row.RetainedFloor {
		return nil
	}
	if floor > row.NextCursor {
		return fmt.Errorf("config changefeed floor %d exceeds next cursor %d", floor, row.NextCursor)
	}
	if err := tx.WithContext(ctx).Where("scope = ? AND generation = ? AND cursor < ?", scope, generation, floor).Delete(&ConfigChangefeedEvent{}).Error; err != nil {
		return fmt.Errorf("prune config changefeed events: %w", err)
	}
	row.RetainedFloor = floor
	row.UpdatedAt = time.Now().UTC()
	return tx.WithContext(ctx).Save(&row).Error
}

// ListConfigChangefeedAfter returns only the requested generation and scope.
// Consumers persist the tuple (scope,generation,cursor), not a global ID.
func ListConfigChangefeedAfter(ctx context.Context, db *gorm.DB, scope string, generation, cursor uint64, limit int) ([]ConfigChangefeedEvent, error) {
	if db == nil || strings.TrimSpace(scope) == "" || generation == 0 || limit <= 0 {
		return nil, errors.New("valid config changefeed database, scope, generation, and limit are required")
	}
	var row ConfigChangefeedGeneration
	if err := db.WithContext(ctx).Where("scope = ?", scope).First(&row).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return []ConfigChangefeedEvent{}, nil
		}
		return nil, err
	}
	if row.Generation != generation {
		return nil, fmt.Errorf("config changefeed generation mismatch: scope=%s expected=%d actual=%d", scope, generation, row.Generation)
	}
	if cursor+1 < row.RetainedFloor {
		return nil, &ConfigChangefeedCursorTooOldError{Scope: scope, Generation: generation, Cursor: cursor, RetainedFloor: row.RetainedFloor}
	}
	var events []ConfigChangefeedEvent
	err := db.WithContext(ctx).Where("scope = ? AND generation = ? AND cursor > ?", scope, generation, cursor).Order("cursor ASC").Limit(limit).Find(&events).Error
	return events, err
}
