package tables

import "time"

// TableGovernanceReservation is the durable idempotency/lease record for a
// logical request attempt. Quota ownership and limits are evaluated by the
// admission layer; this row is the cross-replica source of truth for lifecycle
// state and settlement.
type TableGovernanceReservation struct {
	ID               string    `gorm:"column:id;primaryKey;size:255"`
	BudgetID         string    `gorm:"column:budget_id;size:255;index"`
	LogicalRequestID string    `gorm:"column:logical_request_id;not null;size:255;index"`
	AttemptID        string    `gorm:"column:attempt_id;not null;size:255"`
	AttemptEpoch     uint64    `gorm:"column:attempt_epoch;not null"`
	Lane             string    `gorm:"column:lane;not null;size:32"`
	ReservedTokens   int64     `gorm:"column:reserved_tokens;not null"`
	ReservedMicros   int64     `gorm:"column:reserved_cost_micros;not null"`
	SettledTokens    int64     `gorm:"column:settled_tokens;not null"`
	SettledMicros    int64     `gorm:"column:settled_cost_micros;not null"`
	RefundedTokens   int64     `gorm:"column:refunded_tokens;not null"`
	RefundedMicros   int64     `gorm:"column:refunded_cost_micros;not null"`
	OverdraftTokens  int64     `gorm:"column:overdraft_tokens;not null"`
	OverdraftMicros  int64     `gorm:"column:overdraft_cost_micros;not null"`
	OverdraftState   string    `gorm:"column:overdraft_state;not null;size:16"`
	OverdraftReason  string    `gorm:"column:overdraft_reason;size:255"`
	State            string    `gorm:"column:state;not null;size:16;index"`
	LeaseUntil       time.Time `gorm:"column:lease_until;not null;index"`
	SettlementKey    string    `gorm:"column:settlement_key;size:255"`
	RefundKey        string    `gorm:"column:refund_key;size:255"`
	CreatedAt        time.Time `gorm:"column:created_at;not null"`
	UpdatedAt        time.Time `gorm:"column:updated_at;not null"`
}

func (TableGovernanceReservation) TableName() string { return "governance_reservations" }
