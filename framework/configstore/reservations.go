package configstore

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"gorm.io/gorm"
)

// ReservationStore is the durable lifecycle boundary used by distributed
// admission. Notifications may wake consumers, but callers must use these
// transactional methods as the source of truth.
type ReservationStore interface {
	Reserve(context.Context, reservations.ReservationRequest) (reservations.Reservation, error)
	Renew(context.Context, reservations.RenewRequest) (reservations.Reservation, error)
	Settle(context.Context, reservations.SettleRequest) (reservations.Reservation, error)
	Refund(context.Context, reservations.RefundRequest) (reservations.Reservation, error)
	Get(context.Context, reservations.ReservationID) (reservations.Reservation, error)
}

// BudgetReservationStore is the admission-facing extension. Implementations
// must perform the budget lock, active-reservation check, and insert in one
// transaction; callers must not substitute the unbound Reserve method when a
// budget owner is known.
type BudgetReservationStore interface {
	ReservationStore
	ReserveAgainstBudget(context.Context, BudgetReservationRequest) (reservations.Reservation, error)
}

var _ BudgetReservationStore = (*RDBConfigStore)(nil)

// BudgetReservationRequest binds a reservation to one authoritative budget.
// Hierarchical governance calls this once per budget owner in a single outer
// transaction when it is wired into admission.
type BudgetReservationRequest struct {
	BudgetID string
	Request  reservations.ReservationRequest
}

func (s *RDBConfigStore) reservationDB(ctx context.Context) (*gorm.DB, error) {
	db := s.db.Load()
	if db == nil {
		return nil, errors.New("config store database is unavailable")
	}
	return db.WithContext(ctx), nil
}

func reservationRow(r reservations.Reservation) tables.TableGovernanceReservation {
	return tables.TableGovernanceReservation{ID: string(r.ID), LogicalRequestID: string(r.LogicalRequestID), AttemptID: string(r.AttemptID), AttemptEpoch: uint64(r.AttemptEpoch), Lane: string(r.Lane), ReservedTokens: r.ReservedAmount.Tokens, ReservedMicros: r.ReservedAmount.CostMicros, SettledTokens: r.SettledAmount.Tokens, SettledMicros: r.SettledAmount.CostMicros, RefundedTokens: r.RefundedAmount.Tokens, RefundedMicros: r.RefundedAmount.CostMicros, OverdraftTokens: r.OverdraftAmount.Tokens, OverdraftMicros: r.OverdraftAmount.CostMicros, OverdraftState: string(r.OverdraftState), OverdraftReason: r.OverdraftReason, State: string(r.State), LeaseUntil: r.LeaseUntil, SettlementKey: r.SettlementKey, RefundKey: r.RefundKey, CreatedAt: r.CreatedAt, UpdatedAt: r.UpdatedAt}
}

func (s *RDBConfigStore) ReserveAgainstBudget(ctx context.Context, req BudgetReservationRequest) (reservations.Reservation, error) {
	if req.BudgetID == "" {
		return s.Reserve(ctx, req.Request)
	}
	now := req.Request.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	db, err := s.reservationDB(ctx)
	if err != nil {
		return reservations.Reservation{}, err
	}
	id := reservations.ReservationID(fmt.Sprintf("%s:%s:%d:%s", req.Request.LogicalRequestID, req.Request.AttemptID, req.Request.AttemptEpoch, req.Request.Lane))
	r := reservations.Reservation{ID: id, LogicalRequestID: req.Request.LogicalRequestID, AttemptID: req.Request.AttemptID, AttemptEpoch: req.Request.AttemptEpoch, Lane: req.Request.Lane, ReservedAmount: req.Request.Amount, LeaseUntil: req.Request.LeaseUntil, State: reservations.ReservationStateActive, CreatedAt: now, UpdatedAt: now}
	err = db.Transaction(func(tx *gorm.DB) error {
		var budget tables.TableBudget
		if err := dbForUpdate(tx).First(&budget, "id = ?", req.BudgetID).Error; errors.Is(err, gorm.ErrRecordNotFound) {
			return reservations.ErrNotFound
		} else if err != nil {
			return err
		}
		row := reservationRow(r)
		row.BudgetID = req.BudgetID
		var existing tables.TableGovernanceReservation
		if e := tx.First(&existing, "id = ?", row.ID).Error; e == nil {
			if existing.LogicalRequestID != row.LogicalRequestID || existing.AttemptID != row.AttemptID || existing.AttemptEpoch != row.AttemptEpoch || existing.Lane != row.Lane || existing.ReservedTokens != row.ReservedTokens || existing.ReservedMicros != row.ReservedMicros || existing.BudgetID != row.BudgetID {
				return reservations.ErrReservationConflict
			}
			r = reservationFromRow(existing)
			return nil
		} else if !errors.Is(e, gorm.ErrRecordNotFound) {
			return e
		}
		var active struct{ Total float64 }
		if err := tx.Model(&tables.TableGovernanceReservation{}).Where("budget_id = ? AND state = ?", req.BudgetID, string(reservations.ReservationStateActive)).Select("COALESCE(SUM(reserved_cost_micros),0) AS total").Scan(&active).Error; err != nil {
			return err
		}
		if budget.CurrentUsage+(active.Total+float64(req.Request.Amount.CostMicros))/1_000_000 > budget.MaxLimit {
			return reservations.ErrOverdraftDenied
		}
		return tx.Create(&row).Error
	})
	return r, err
}

func reservationFromRow(row tables.TableGovernanceReservation) reservations.Reservation {
	return reservations.Reservation{ID: reservations.ReservationID(row.ID), LogicalRequestID: reservations.LogicalRequestID(row.LogicalRequestID), AttemptID: reservations.AttemptID(row.AttemptID), AttemptEpoch: reservations.AttemptEpoch(row.AttemptEpoch), Lane: reservations.AccountingLane(row.Lane), ReservedAmount: reservations.Amount{Tokens: row.ReservedTokens, CostMicros: row.ReservedMicros}, SettledAmount: reservations.Amount{Tokens: row.SettledTokens, CostMicros: row.SettledMicros}, RefundedAmount: reservations.Amount{Tokens: row.RefundedTokens, CostMicros: row.RefundedMicros}, OverdraftAmount: reservations.Amount{Tokens: row.OverdraftTokens, CostMicros: row.OverdraftMicros}, OverdraftState: reservations.OverdraftState(row.OverdraftState), OverdraftReason: row.OverdraftReason, State: reservations.ReservationState(row.State), LeaseUntil: row.LeaseUntil, SettlementKey: row.SettlementKey, RefundKey: row.RefundKey, CreatedAt: row.CreatedAt, UpdatedAt: row.UpdatedAt}
}

func (s *RDBConfigStore) Reserve(ctx context.Context, req reservations.ReservationRequest) (reservations.Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	id := reservations.ReservationID(fmt.Sprintf("%s:%s:%d:%s", req.LogicalRequestID, req.AttemptID, req.AttemptEpoch, req.Lane))
	r := reservations.Reservation{ID: id, LogicalRequestID: req.LogicalRequestID, AttemptID: req.AttemptID, AttemptEpoch: req.AttemptEpoch, Lane: req.Lane, ReservedAmount: req.Amount, LeaseUntil: req.LeaseUntil, State: reservations.ReservationStateActive, CreatedAt: now, UpdatedAt: now}
	db, err := s.reservationDB(ctx)
	if err != nil {
		return reservations.Reservation{}, err
	}
	row := reservationRow(r)
	err = db.Transaction(func(tx *gorm.DB) error {
		var existing tables.TableGovernanceReservation
		if e := tx.First(&existing, "id = ?", row.ID).Error; e == nil {
			if existing.LogicalRequestID != row.LogicalRequestID || existing.AttemptID != row.AttemptID || existing.AttemptEpoch != row.AttemptEpoch || existing.Lane != row.Lane || existing.ReservedTokens != row.ReservedTokens || existing.ReservedMicros != row.ReservedMicros {
				return reservations.ErrReservationConflict
			}
			r = reservationFromRow(existing)
			return nil
		} else if !errors.Is(e, gorm.ErrRecordNotFound) {
			return e
		}
		return tx.Create(&row).Error
	})
	return r, err
}

func (s *RDBConfigStore) Get(ctx context.Context, id reservations.ReservationID) (reservations.Reservation, error) {
	db, err := s.reservationDB(ctx)
	if err != nil {
		return reservations.Reservation{}, err
	}
	var row tables.TableGovernanceReservation
	if err := db.First(&row, "id = ?", string(id)).Error; errors.Is(err, gorm.ErrRecordNotFound) {
		return reservations.Reservation{}, reservations.ErrNotFound
	} else if err != nil {
		return reservations.Reservation{}, err
	}
	return reservationFromRow(row), nil
}

func (s *RDBConfigStore) Renew(ctx context.Context, req reservations.RenewRequest) (reservations.Reservation, error) {
	now := time.Now().UTC()
	db, err := s.reservationDB(ctx)
	if err != nil {
		return reservations.Reservation{}, err
	}
	var out reservations.Reservation
	err = db.Transaction(func(tx *gorm.DB) error {
		var row tables.TableGovernanceReservation
		if err := dbForUpdate(tx).First(&row, "id = ?", string(req.ReservationID)).Error; errors.Is(err, gorm.ErrRecordNotFound) {
			return reservations.ErrNotFound
		} else if err != nil {
			return err
		}
		if uint64(req.AttemptEpoch) < row.AttemptEpoch {
			return reservations.ErrStaleEpoch
		}
		if row.State != string(reservations.ReservationStateActive) {
			return reservations.ErrAlreadyFinalized
		}
		row.AttemptEpoch, row.LeaseUntil, row.UpdatedAt = uint64(req.AttemptEpoch), req.LeaseUntil, now
		if err := tx.Save(&row).Error; err != nil {
			return err
		}
		out = reservationFromRow(row)
		return nil
	})
	return out, err
}

func (s *RDBConfigStore) Settle(ctx context.Context, req reservations.SettleRequest) (reservations.Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	db, err := s.reservationDB(ctx)
	if err != nil {
		return reservations.Reservation{}, err
	}
	var out reservations.Reservation
	err = db.Transaction(func(tx *gorm.DB) error {
		var row tables.TableGovernanceReservation
		if err := dbForUpdate(tx).First(&row, "id = ?", string(req.ReservationID)).Error; errors.Is(err, gorm.ErrRecordNotFound) {
			return reservations.ErrNotFound
		} else if err != nil {
			return err
		}
		if req.AttemptEpoch != reservations.AttemptEpoch(row.AttemptEpoch) {
			return reservations.ErrStaleEpoch
		}
		if row.State == string(reservations.ReservationStateSettled) && row.SettlementKey == req.IdempotencyKey && row.SettledTokens == req.ActualAmount.Tokens && row.SettledMicros == req.ActualAmount.CostMicros {
			out = reservationFromRow(row)
			return nil
		}
		if row.State != string(reservations.ReservationStateActive) {
			return reservations.ErrAlreadyFinalized
		}
		excessTokens := req.ActualAmount.Tokens - row.ReservedTokens
		excessMicros := req.ActualAmount.CostMicros - row.ReservedMicros
		if excessTokens > 0 || excessMicros > 0 {
			if !req.Overdraft.Allow {
				row.OverdraftState = string(reservations.OverdraftStateDenied)
				row.UpdatedAt = now
				_ = tx.Save(&row)
				return reservations.ErrOverdraftDenied
			}
			row.OverdraftState, row.OverdraftReason = string(reservations.OverdraftStateControlled), req.Overdraft.Reason
			if excessTokens > 0 {
				row.OverdraftTokens = excessTokens
			}
			if excessMicros > 0 {
				row.OverdraftMicros = excessMicros
			}
		}
		row.State, row.SettledTokens, row.SettledMicros, row.SettlementKey, row.UpdatedAt = string(reservations.ReservationStateSettled), req.ActualAmount.Tokens, req.ActualAmount.CostMicros, req.IdempotencyKey, now
		if unused := row.ReservedTokens - req.ActualAmount.Tokens; unused > 0 {
			row.RefundedTokens = unused
		}
		if unused := row.ReservedMicros - req.ActualAmount.CostMicros; unused > 0 {
			row.RefundedMicros = unused
		}
		if row.BudgetID != "" {
			var budget tables.TableBudget
			if err := dbForUpdate(tx).First(&budget, "id = ?", row.BudgetID).Error; errors.Is(err, gorm.ErrRecordNotFound) {
				return reservations.ErrNotFound
			} else if err != nil {
				return err
			}
			budget.CurrentUsage += float64(req.ActualAmount.CostMicros) / 1_000_000
			if err := tx.Save(&budget).Error; err != nil {
				return err
			}
		}
		if err := tx.Save(&row).Error; err != nil {
			return err
		}
		out = reservationFromRow(row)
		return nil
	})
	return out, err
}

func (s *RDBConfigStore) Refund(ctx context.Context, req reservations.RefundRequest) (reservations.Reservation, error) {
	now := req.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	db, err := s.reservationDB(ctx)
	if err != nil {
		return reservations.Reservation{}, err
	}
	var out reservations.Reservation
	err = db.Transaction(func(tx *gorm.DB) error {
		var row tables.TableGovernanceReservation
		if err := dbForUpdate(tx).First(&row, "id = ?", string(req.ReservationID)).Error; errors.Is(err, gorm.ErrRecordNotFound) {
			return reservations.ErrNotFound
		} else if err != nil {
			return err
		}
		if req.AttemptEpoch != reservations.AttemptEpoch(row.AttemptEpoch) {
			return reservations.ErrStaleEpoch
		}
		if row.State == string(reservations.ReservationStateRefunded) && row.RefundKey == req.IdempotencyKey {
			out = reservationFromRow(row)
			return nil
		}
		if row.State != string(reservations.ReservationStateActive) {
			return reservations.ErrAlreadyFinalized
		}
		row.State, row.RefundedTokens, row.RefundedMicros, row.RefundKey, row.UpdatedAt = string(reservations.ReservationStateRefunded), row.ReservedTokens, row.ReservedMicros, req.IdempotencyKey, now
		if err := tx.Save(&row).Error; err != nil {
			return err
		}
		out = reservationFromRow(row)
		return nil
	})
	return out, err
}
