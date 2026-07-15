package configstore

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/maximhq/bifrost/framework/configstore/tables"
	"gorm.io/gorm"
)

const MaxVirtualKeyInvalidationBatchSize = 1000

// AppendVirtualKeyInvalidation appends an event using the caller's transaction.
// Callers should mutate the virtual-key authority row and append its invalidation
// in the same transaction so consumers can never observe an event for an
// uncommitted change.
func (s *RDBConfigStore) AppendVirtualKeyInvalidation(ctx context.Context, tx *gorm.DB, event *tables.TableVirtualKeyInvalidationEvent) error {
	if tx == nil {
		return errors.New("virtual-key invalidation transaction is required")
	}
	if event == nil {
		return errors.New("virtual-key invalidation event is required")
	}
	if event.EntityType != tables.VirtualKeyInvalidationEntityType {
		return fmt.Errorf("invalid virtual-key invalidation entity type %q", event.EntityType)
	}
	if strings.TrimSpace(event.EntityID) == "" {
		return errors.New("virtual-key invalidation entity id is required")
	}
	if event.Action != tables.VirtualKeyInvalidationActionReload && event.Action != tables.VirtualKeyInvalidationActionDelete {
		return fmt.Errorf("invalid virtual-key invalidation action %q", event.Action)
	}
	if event.SchemaVersion == 0 {
		event.SchemaVersion = tables.VirtualKeyInvalidationSchemaVersion
	}
	if event.SchemaVersion != tables.VirtualKeyInvalidationSchemaVersion {
		return fmt.Errorf("unsupported virtual-key invalidation schema version %d", event.SchemaVersion)
	}
	return tx.WithContext(ctx).Create(event).Error
}

// ListVirtualKeyInvalidationsAfter returns a bounded, ascending batch whose IDs
// are strictly greater than cursor. Consumers advance their durable cursor only
// after applying a batch; replay after a crash is therefore duplicate-safe.
func (s *RDBConfigStore) ListVirtualKeyInvalidationsAfter(ctx context.Context, cursor uint64, limit int) ([]tables.TableVirtualKeyInvalidationEvent, error) {
	if limit <= 0 || limit > MaxVirtualKeyInvalidationBatchSize {
		return nil, fmt.Errorf("virtual-key invalidation batch size must be between 1 and %d", MaxVirtualKeyInvalidationBatchSize)
	}
	events := make([]tables.TableVirtualKeyInvalidationEvent, 0, limit)
	err := s.DB().WithContext(ctx).
		Where("id > ?", cursor).
		Order("id ASC").
		Limit(limit).
		Find(&events).Error
	return events, err
}

// GetVirtualKeyInvalidationHighWatermark returns the greatest durable event ID,
// or zero when the outbox is empty.
func (s *RDBConfigStore) GetVirtualKeyInvalidationHighWatermark(ctx context.Context) (uint64, error) {
	var highWatermark uint64
	err := s.DB().WithContext(ctx).
		Model(&tables.TableVirtualKeyInvalidationEvent{}).
		Select("COALESCE(MAX(id), 0)").
		Scan(&highWatermark).Error
	return highWatermark, err
}
