package configstore

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"gorm.io/gorm"
)

const (
	MaxVirtualKeyInvalidationBatchSize        = 1000
	virtualKeyInvalidationNotificationChannel = "bifrost_vk_invalidation_v1"
	virtualKeyInvalidationReconnectMinBackoff = 100 * time.Millisecond
	virtualKeyInvalidationReconnectMaxBackoff = 30 * time.Second
	virtualKeyInvalidationStableConnection    = 30 * time.Second
	virtualKeyInvalidationListenerLogInterval = 30 * time.Second
)

type virtualKeyInvalidationNotifyConn interface {
	Listen(context.Context) error
	WaitForNotification(context.Context) error
	Close(context.Context) error
}

type pgxVirtualKeyInvalidationNotifyConn struct {
	conn *pgx.Conn
}

// SetVirtualKeyInvalidationMetricSink installs a non-blocking observer for
// notification-listener metrics. The callback is deliberately tiny and may be
// replaced during server/plugin reload without interrupting the listener.
func (s *RDBConfigStore) SetVirtualKeyInvalidationMetricSink(sink func(string, float64)) {
	if s == nil {
		return
	}
	s.virtualKeyInvalidationMetricsMu.Lock()
	s.virtualKeyInvalidationMetrics = sink
	s.virtualKeyInvalidationMetricsMu.Unlock()
}

func (s *RDBConfigStore) observeVirtualKeyInvalidationMetric(name string, value float64) {
	if s == nil {
		return
	}
	s.virtualKeyInvalidationMetricsMu.RLock()
	sink := s.virtualKeyInvalidationMetrics
	s.virtualKeyInvalidationMetricsMu.RUnlock()
	if sink != nil {
		sink(name, value)
	}
}

func (c *pgxVirtualKeyInvalidationNotifyConn) Listen(ctx context.Context) error {
	_, err := c.conn.Exec(ctx, "LISTEN "+virtualKeyInvalidationNotificationChannel)
	return err
}

func (c *pgxVirtualKeyInvalidationNotifyConn) WaitForNotification(ctx context.Context) error {
	_, err := c.conn.WaitForNotification(ctx)
	return err
}

func (c *pgxVirtualKeyInvalidationNotifyConn) Close(ctx context.Context) error {
	return c.conn.Close(ctx)
}

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
	if err := tx.WithContext(ctx).Create(event).Error; err != nil {
		return err
	}
	if tx.Dialector.Name() == "postgres" {
		if err := tx.WithContext(ctx).Exec(
			"SELECT pg_notify(?, ?)",
			virtualKeyInvalidationNotificationChannel,
			"",
		).Error; err != nil {
			return fmt.Errorf("publish virtual-key invalidation wake hint: %w", err)
		}
	}
	return nil
}

// VirtualKeyInvalidationWakeups returns an optional, coalesced PostgreSQL wake
// stream. The durable outbox remains authoritative: a wake only tells a
// consumer to poll sooner. SQLite and stores without a dedicated connector
// return nil and continue using periodic polling exclusively.
//
// The listener uses a separately dialed physical PostgreSQL connection rather
// than borrowing from database/sql. It therefore cannot consume the final slot
// in a small GORM pool, and a runtime-pool refresh cannot strand it. Connection
// loss (including Aurora failover) is recovered with bounded backoff; the wake
// emitted immediately after every successful LISTEN closes the notification
// loss window by prompting a durable poll.
func (s *RDBConfigStore) VirtualKeyInvalidationWakeups(ctx context.Context) <-chan struct{} {
	if s == nil || s.virtualKeyInvalidationNotifyDial == nil {
		return nil
	}
	wake := make(chan struct{}, 1)
	go s.runVirtualKeyInvalidationListener(ctx, wake)
	return wake
}

func (s *RDBConfigStore) runVirtualKeyInvalidationListener(ctx context.Context, wake chan<- struct{}) {
	backoff := virtualKeyInvalidationReconnectMinBackoff
	var lastLog time.Time
	for ctx.Err() == nil {
		conn, err := s.virtualKeyInvalidationNotifyDial(ctx)
		if err == nil {
			err = conn.Listen(ctx)
		}
		if err == nil {
			connectedAt := time.Now()
			s.observeVirtualKeyInvalidationMetric("listener_reconnects", 1)
			signalVirtualKeyInvalidationWake(wake)
			s.observeVirtualKeyInvalidationMetric("wakeups", 1)
			for ctx.Err() == nil {
				if err = conn.WaitForNotification(ctx); err != nil {
					if time.Since(connectedAt) >= virtualKeyInvalidationStableConnection {
						backoff = virtualKeyInvalidationReconnectMinBackoff
					}
					break
				}
				// Receiving traffic proves the session is usable, so a later
				// disconnect may retry quickly. Accept-then-drop sessions never
				// reach this reset and continue exponential backoff.
				backoff = virtualKeyInvalidationReconnectMinBackoff
				connectedAt = time.Now()
				signalVirtualKeyInvalidationWake(wake)
				s.observeVirtualKeyInvalidationMetric("wakeups", 1)
			}
		}
		if conn != nil {
			closeCtx, cancel := context.WithTimeout(context.Background(), time.Second)
			_ = conn.Close(closeCtx)
			cancel()
		}
		if ctx.Err() != nil {
			return
		}
		now := time.Now()
		if s.logger != nil && (lastLog.IsZero() || now.Sub(lastLog) >= virtualKeyInvalidationListenerLogInterval) {
			s.logger.Warn("virtual-key invalidation notification listener disconnected; durable polling remains active: %v", err)
			lastLog = now
		}
		delay := jitterVirtualKeyInvalidationBackoff(backoff, now.UnixNano())
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			if !timer.Stop() {
				<-timer.C
			}
			return
		case <-timer.C:
		}
		if backoff < virtualKeyInvalidationReconnectMaxBackoff {
			backoff *= 2
			if backoff > virtualKeyInvalidationReconnectMaxBackoff {
				backoff = virtualKeyInvalidationReconnectMaxBackoff
			}
		}
	}
}

func signalVirtualKeyInvalidationWake(wake chan<- struct{}) {
	select {
	case wake <- struct{}{}:
	default:
	}
}

func jitterVirtualKeyInvalidationBackoff(base time.Duration, salt int64) time.Duration {
	if base <= 0 {
		return 0
	}
	spread := base / 5
	if spread == 0 {
		return base
	}
	width := int64(2*spread + 1)
	if salt < 0 {
		salt = -salt
	}
	return base - spread + time.Duration(salt%width)
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
