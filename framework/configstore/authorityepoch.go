package configstore

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"gorm.io/gorm"
)

const (
	MaxPrincipalAuthorizationEpochEventBatchSize          = 1000
	PrincipalAuthorizationEpochReasonActivated            = "activated"
	PrincipalAuthorizationEpochReasonReactivated          = "reactivated"
	principalAuthorizationEpochMaxSigned           uint64 = uint64(math.MaxInt64)
	principalAuthorizationEpochNotificationChannel        = "bifrost_principal_authorization_epoch_v1"
	principalAuthorizationEpochReconnectMinBackoff        = 100 * time.Millisecond
	principalAuthorizationEpochReconnectMaxBackoff        = 30 * time.Second
	principalAuthorizationEpochStableConnection           = 30 * time.Second
	principalAuthorizationEpochListenerLogInterval        = 30 * time.Second
)

type principalAuthorizationEpochNotifyConn interface {
	Listen(context.Context) error
	WaitForNotification(context.Context) error
	Close(context.Context) error
}

type pgxPrincipalAuthorizationEpochNotifyConn struct {
	conn *pgx.Conn
}

func (c *pgxPrincipalAuthorizationEpochNotifyConn) Listen(ctx context.Context) error {
	_, err := c.conn.Exec(ctx, "LISTEN "+principalAuthorizationEpochNotificationChannel)
	return err
}

func (c *pgxPrincipalAuthorizationEpochNotifyConn) WaitForNotification(ctx context.Context) error {
	_, err := c.conn.WaitForNotification(ctx)
	return err
}

func (c *pgxPrincipalAuthorizationEpochNotifyConn) Close(ctx context.Context) error {
	return c.conn.Close(ctx)
}

var _ PrincipalAuthorizationEpochStore = (*RDBConfigStore)(nil)

func (s *RDBConfigStore) GetPrincipalAuthorizationEpoch(ctx context.Context, principal authorityepoch.Principal) (*tables.TablePrincipalAuthorizationEpoch, error) {
	if err := validatePrincipalAuthorizationEpochPrincipal(principal); err != nil {
		return nil, err
	}
	var row tables.TablePrincipalAuthorizationEpoch
	err := principalAuthorizationEpochQuery(s.DB().WithContext(ctx), principal).First(&row).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, authorityepoch.ErrUnknownPrincipal
	}
	if err != nil {
		return nil, err
	}
	return &row, nil
}

func (s *RDBConfigStore) ActivatePrincipalAuthorizationEpoch(ctx context.Context, principal authorityepoch.Principal, epoch uint64, tx ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpoch, error) {
	if err := validatePrincipalAuthorizationEpochPrincipal(principal); err != nil {
		return nil, err
	}
	if err := validatePrincipalAuthorizationEpochSigned("epoch", epoch); err != nil {
		return nil, err
	}

	var row tables.TablePrincipalAuthorizationEpoch
	err := s.withPrincipalAuthorizationEpochTx(ctx, principal, tx, func(txDB *gorm.DB) error {
		var oldEpoch uint64
		reason := PrincipalAuthorizationEpochReasonActivated
		err := principalAuthorizationEpochQuery(dbForUpdate(txDB.WithContext(ctx)), principal).First(&row).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			row = tables.TablePrincipalAuthorizationEpoch{
				TenantID:   principal.Tenant,
				Issuer:     principal.Issuer,
				Subject:    principal.Subject,
				Epoch:      epoch,
				Active:     true,
				LastReason: reason,
				Revision:   1,
			}
			if err := txDB.WithContext(ctx).Create(&row).Error; err != nil {
				return err
			}
		} else {
			if err != nil {
				return err
			}
			if epoch <= row.Epoch {
				return authorityepoch.ErrStaleEpoch
			}
			if err := validatePrincipalAuthorizationEpochNext(row.Revision); err != nil {
				return err
			}
			oldEpoch = row.Epoch
			if !row.Active {
				reason = PrincipalAuthorizationEpochReasonReactivated
			}
			row.Epoch = epoch
			row.Active = true
			row.LastReason = reason
			row.Revision++
			row.DeactivatedAt = nil
			if err := txDB.WithContext(ctx).Save(&row).Error; err != nil {
				return err
			}
		}
		event := &tables.TablePrincipalAuthorizationEpochEvent{
			TenantID:      principal.Tenant,
			Issuer:        principal.Issuer,
			Subject:       principal.Subject,
			OldEpoch:      oldEpoch,
			NewEpoch:      row.Epoch,
			Active:        true,
			Reason:        reason,
			Revision:      row.Revision,
			SchemaVersion: tables.PrincipalAuthorizationEpochSchemaVersion,
		}
		return s.appendPrincipalAuthorizationEpochEvent(ctx, txDB, event)
	})
	if err != nil {
		return nil, err
	}
	return &row, nil
}

func (s *RDBConfigStore) AdvancePrincipalAuthorizationEpoch(ctx context.Context, principal authorityepoch.Principal, reason authorityepoch.Reason, tx ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpochEvent, error) {
	return s.changePrincipalAuthorizationEpoch(ctx, principal, reason, true, tx...)
}

func (s *RDBConfigStore) DeactivatePrincipalAuthorizationEpoch(ctx context.Context, principal authorityepoch.Principal, reason authorityepoch.Reason, tx ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpochEvent, error) {
	return s.changePrincipalAuthorizationEpoch(ctx, principal, reason, false, tx...)
}

func (s *RDBConfigStore) ValidatePrincipalAuthorizationEpoch(ctx context.Context, ref authorityepoch.Reference) error {
	if err := validatePrincipalAuthorizationEpochPrincipal(ref.Principal); err != nil {
		return err
	}
	if err := validatePrincipalAuthorizationEpochSigned("epoch", ref.Epoch); err != nil {
		return err
	}
	if !isPrincipalAuthorizationEpochArtifactKindSupported(ref.Kind) || strings.TrimSpace(ref.ID) == "" {
		return authorityepoch.ErrInvalidReference
	}
	row, err := s.GetPrincipalAuthorizationEpoch(ctx, ref.Principal)
	if err != nil {
		return err
	}
	if !row.Active {
		return authorityepoch.ErrInactivePrincipal
	}
	if ref.Epoch != row.Epoch {
		return authorityepoch.ErrStaleEpoch
	}
	return nil
}

func (s *RDBConfigStore) ListPrincipalAuthorizationEpochEventsAfter(ctx context.Context, cursor uint64, limit int) ([]tables.TablePrincipalAuthorizationEpochEvent, error) {
	if limit <= 0 || limit > MaxPrincipalAuthorizationEpochEventBatchSize {
		return nil, fmt.Errorf("principal authorization epoch event batch size must be between 1 and %d", MaxPrincipalAuthorizationEpochEventBatchSize)
	}
	events := make([]tables.TablePrincipalAuthorizationEpochEvent, 0, limit)
	err := s.DB().WithContext(ctx).
		Where("id > ?", cursor).
		Order("id ASC").
		Limit(limit).
		Find(&events).Error
	return events, err
}

func (s *RDBConfigStore) GetPrincipalAuthorizationEpochHighWatermark(ctx context.Context) (uint64, error) {
	var highWatermark uint64
	err := s.DB().WithContext(ctx).
		Model(&tables.TablePrincipalAuthorizationEpochEvent{}).
		Select("COALESCE(MAX(id), 0)").
		Scan(&highWatermark).Error
	return highWatermark, err
}

func (s *RDBConfigStore) changePrincipalAuthorizationEpoch(ctx context.Context, principal authorityepoch.Principal, reason authorityepoch.Reason, active bool, tx ...*gorm.DB) (*tables.TablePrincipalAuthorizationEpochEvent, error) {
	if err := validatePrincipalAuthorizationEpochPrincipal(principal); err != nil {
		return nil, err
	}
	reasonString, err := validatePrincipalAuthorizationEpochReason(reason)
	if err != nil {
		return nil, err
	}

	var event tables.TablePrincipalAuthorizationEpochEvent
	err = s.withPrincipalAuthorizationEpochTx(ctx, principal, tx, func(txDB *gorm.DB) error {
		var row tables.TablePrincipalAuthorizationEpoch
		if err := principalAuthorizationEpochQuery(dbForUpdate(txDB.WithContext(ctx)), principal).First(&row).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return authorityepoch.ErrUnknownPrincipal
			}
			return err
		}
		if !row.Active {
			return authorityepoch.ErrInactivePrincipal
		}
		if err := validatePrincipalAuthorizationEpochNext(row.Epoch); err != nil {
			return err
		}
		if err := validatePrincipalAuthorizationEpochNext(row.Revision); err != nil {
			return err
		}

		oldEpoch := row.Epoch
		row.Epoch++
		row.Active = active
		row.LastReason = reasonString
		row.Revision++
		if active {
			row.DeactivatedAt = nil
		} else {
			now := time.Now().UTC()
			row.DeactivatedAt = &now
		}
		if err := txDB.WithContext(ctx).Save(&row).Error; err != nil {
			return err
		}

		event = tables.TablePrincipalAuthorizationEpochEvent{
			TenantID:      principal.Tenant,
			Issuer:        principal.Issuer,
			Subject:       principal.Subject,
			OldEpoch:      oldEpoch,
			NewEpoch:      row.Epoch,
			Active:        row.Active,
			Reason:        reasonString,
			Revision:      row.Revision,
			SchemaVersion: tables.PrincipalAuthorizationEpochSchemaVersion,
		}
		return s.appendPrincipalAuthorizationEpochEvent(ctx, txDB, &event)
	})
	if err != nil {
		return nil, err
	}
	return &event, nil
}

func (s *RDBConfigStore) appendPrincipalAuthorizationEpochEvent(ctx context.Context, tx *gorm.DB, event *tables.TablePrincipalAuthorizationEpochEvent) error {
	if tx == nil {
		return errors.New("principal authorization epoch transaction is required")
	}
	if event == nil {
		return errors.New("principal authorization epoch event is required")
	}
	if err := validatePrincipalAuthorizationEpochPrincipal(authorityepoch.Principal{
		Tenant:  event.TenantID,
		Issuer:  event.Issuer,
		Subject: event.Subject,
	}); err != nil {
		return err
	}
	if event.OldEpoch > principalAuthorizationEpochMaxSigned || event.NewEpoch > principalAuthorizationEpochMaxSigned || event.NewEpoch <= event.OldEpoch {
		return authorityepoch.ErrInvalidReference
	}
	if err := validatePrincipalAuthorizationEpochSigned("revision", event.Revision); err != nil {
		return err
	}
	if _, err := validatePrincipalAuthorizationEpochReason(authorityepoch.Reason(event.Reason)); err != nil {
		return err
	}
	if event.SchemaVersion == 0 {
		event.SchemaVersion = tables.PrincipalAuthorizationEpochSchemaVersion
	}
	if event.SchemaVersion != tables.PrincipalAuthorizationEpochSchemaVersion {
		return fmt.Errorf("unsupported principal authorization epoch schema version %d", event.SchemaVersion)
	}
	if err := tx.WithContext(ctx).Create(event).Error; err != nil {
		return err
	}
	if tx.Dialector.Name() == "postgres" {
		if err := tx.WithContext(ctx).Exec(
			"SELECT pg_notify(?, ?)",
			principalAuthorizationEpochNotificationChannel,
			"",
		).Error; err != nil {
			return fmt.Errorf("publish principal authorization epoch wake hint: %w", err)
		}
	}
	return nil
}

// PrincipalAuthorizationEpochWakeups returns an optional, coalesced PostgreSQL
// wake stream. The durable outbox remains authoritative; consumers must poll by
// cursor after every wake and on a periodic fallback. SQLite returns nil.
func (s *RDBConfigStore) PrincipalAuthorizationEpochWakeups(ctx context.Context) <-chan struct{} {
	if s == nil || s.principalAuthorizationEpochNotifyDial == nil {
		return nil
	}
	wake := make(chan struct{}, 1)
	go s.runPrincipalAuthorizationEpochListener(ctx, wake)
	return wake
}

func (s *RDBConfigStore) runPrincipalAuthorizationEpochListener(ctx context.Context, wake chan<- struct{}) {
	backoff := principalAuthorizationEpochReconnectMinBackoff
	var lastLog time.Time
	for ctx.Err() == nil {
		conn, err := s.principalAuthorizationEpochNotifyDial(ctx)
		if err == nil {
			err = conn.Listen(ctx)
		}
		if err == nil {
			connectedAt := time.Now()
			signalPrincipalAuthorizationEpochWake(wake)
			for ctx.Err() == nil {
				if err = conn.WaitForNotification(ctx); err != nil {
					if time.Since(connectedAt) >= principalAuthorizationEpochStableConnection {
						backoff = principalAuthorizationEpochReconnectMinBackoff
					}
					break
				}
				backoff = principalAuthorizationEpochReconnectMinBackoff
				connectedAt = time.Now()
				signalPrincipalAuthorizationEpochWake(wake)
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
		if s.logger != nil && (lastLog.IsZero() || now.Sub(lastLog) >= principalAuthorizationEpochListenerLogInterval) {
			s.logger.Warn("principal authorization epoch notification listener disconnected; durable polling remains active: %v", err)
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
		if backoff < principalAuthorizationEpochReconnectMaxBackoff {
			backoff *= 2
			if backoff > principalAuthorizationEpochReconnectMaxBackoff {
				backoff = principalAuthorizationEpochReconnectMaxBackoff
			}
		}
	}
}

func signalPrincipalAuthorizationEpochWake(wake chan<- struct{}) {
	select {
	case wake <- struct{}{}:
	default:
	}
}

func (s *RDBConfigStore) withPrincipalAuthorizationEpochTx(ctx context.Context, principal authorityepoch.Principal, txs []*gorm.DB, fn func(*gorm.DB) error) error {
	if len(txs) > 0 {
		if txs[0] == nil {
			return errors.New("principal authorization epoch transaction is nil")
		}
		if err := lockPrincipalAuthorizationEpochTx(ctx, txs[0], principal); err != nil {
			return err
		}
		return fn(txs[0])
	}
	return s.DB().WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := lockPrincipalAuthorizationEpochTx(ctx, tx, principal); err != nil {
			return err
		}
		return fn(tx)
	})
}

func validatePrincipalAuthorizationEpochPrincipal(principal authorityepoch.Principal) error {
	if strings.TrimSpace(principal.Tenant) == "" || strings.TrimSpace(principal.Issuer) == "" || strings.TrimSpace(principal.Subject) == "" {
		return authorityepoch.ErrInvalidPrincipal
	}
	if len(principal.Tenant) > 255 || len(principal.Issuer) > 255 || len(principal.Subject) > 255 {
		return authorityepoch.ErrInvalidPrincipal
	}
	return nil
}

func validatePrincipalAuthorizationEpochReason(reason authorityepoch.Reason) (string, error) {
	switch reason {
	case authorityepoch.ReasonGroupRemoved, authorityepoch.ReasonDeactivated:
		return string(reason), nil
	case authorityepoch.Reason(PrincipalAuthorizationEpochReasonActivated), authorityepoch.Reason(PrincipalAuthorizationEpochReasonReactivated):
		return string(reason), nil
	default:
		return "", fmt.Errorf("unsupported principal authorization epoch reason %q", reason)
	}
}

func validatePrincipalAuthorizationEpochSigned(name string, value uint64) error {
	if value == 0 || value > principalAuthorizationEpochMaxSigned {
		return fmt.Errorf("%s exceeds signed database range: %w", name, authorityepoch.ErrInvalidReference)
	}
	return nil
}

func validatePrincipalAuthorizationEpochNext(value uint64) error {
	if value == 0 || value >= principalAuthorizationEpochMaxSigned {
		return authorityepoch.ErrInvalidReference
	}
	return nil
}

func isPrincipalAuthorizationEpochArtifactKindSupported(kind authorityepoch.ArtifactKind) bool {
	switch kind {
	case authorityepoch.ArtifactUnary,
		authorityepoch.ArtifactSSE,
		authorityepoch.ArtifactWebSocket,
		authorityepoch.ArtifactQueued,
		authorityepoch.ArtifactKey,
		authorityepoch.ArtifactCache,
		authorityepoch.ArtifactMCPGrant,
		authorityepoch.ArtifactMCPLiveConnection:
		return true
	default:
		return false
	}
}

func principalAuthorizationEpochQuery(db *gorm.DB, principal authorityepoch.Principal) *gorm.DB {
	return db.Where("tenant_id = ? AND issuer = ? AND subject = ?", principal.Tenant, principal.Issuer, principal.Subject)
}

func lockPrincipalAuthorizationEpochTx(ctx context.Context, tx *gorm.DB, principal authorityepoch.Principal) error {
	if tx == nil || tx.Dialector == nil || tx.Dialector.Name() != "postgres" {
		return nil
	}
	return tx.WithContext(ctx).Exec(
		"SELECT pg_advisory_xact_lock(?)",
		principalAuthorizationEpochLockKey(principal),
	).Error
}

func principalAuthorizationEpochLockKey(principal authorityepoch.Principal) int64 {
	sum := sha256.Sum256([]byte(principal.Tenant + "\x00" + principal.Issuer + "\x00" + principal.Subject))
	return int64(binary.BigEndian.Uint64(sum[:8]))
}
