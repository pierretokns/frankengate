package tables

import "time"

const PrincipalAuthorizationEpochSchemaVersion uint16 = 1

// TablePrincipalAuthorizationEpoch is the durable source of truth for a
// tenant+issuer+subject authorization epoch. The principal tuple is the primary
// key and must not be rewritten; deprovisioning advances the epoch and flips the
// row inactive instead of deleting it so stale artifacts fail closed after pod
// restart.
type TablePrincipalAuthorizationEpoch struct {
	TenantID      string     `gorm:"column:tenant_id;primaryKey;type:varchar(255)" json:"tenant_id"`
	Issuer        string     `gorm:"column:issuer;primaryKey;type:varchar(255)" json:"issuer"`
	Subject       string     `gorm:"column:subject;primaryKey;type:varchar(255)" json:"subject"`
	Epoch         uint64     `gorm:"column:epoch;not null" json:"epoch"`
	Active        bool       `gorm:"column:active;not null;default:true;index:idx_principal_authorization_epochs_active" json:"active"`
	LastReason    string     `gorm:"column:last_reason;type:varchar(64);not null;default:''" json:"last_reason"`
	Revision      uint64     `gorm:"column:revision;not null;default:1" json:"revision"`
	CreatedAt     time.Time  `gorm:"column:created_at;not null" json:"created_at"`
	UpdatedAt     time.Time  `gorm:"column:updated_at;not null" json:"updated_at"`
	DeactivatedAt *time.Time `gorm:"column:deactivated_at" json:"deactivated_at,omitempty"`
}

func (TablePrincipalAuthorizationEpoch) TableName() string {
	return "governance_principal_authorization_epochs"
}

// TablePrincipalAuthorizationEpochEvent is an immutable durable outbox event.
// ID is the replay cursor; consumers persist the greatest applied ID and may
// safely apply duplicate events because each carries the post-mutation epoch and
// active flag.
type TablePrincipalAuthorizationEpochEvent struct {
	ID            uint64    `gorm:"column:id;primaryKey;autoIncrement" json:"id"`
	TenantID      string    `gorm:"column:tenant_id;type:varchar(255);not null;index:idx_principal_authorization_epoch_outbox_principal,priority:1" json:"tenant_id"`
	Issuer        string    `gorm:"column:issuer;type:varchar(255);not null;index:idx_principal_authorization_epoch_outbox_principal,priority:2" json:"issuer"`
	Subject       string    `gorm:"column:subject;type:varchar(255);not null;index:idx_principal_authorization_epoch_outbox_principal,priority:3" json:"subject"`
	OldEpoch      uint64    `gorm:"column:old_epoch;not null" json:"old_epoch"`
	NewEpoch      uint64    `gorm:"column:new_epoch;not null" json:"new_epoch"`
	Active        bool      `gorm:"column:active;not null" json:"active"`
	Reason        string    `gorm:"column:reason;type:varchar(64);not null" json:"reason"`
	Revision      uint64    `gorm:"column:revision;not null" json:"revision"`
	SchemaVersion uint16    `gorm:"column:schema_version;not null;default:1" json:"schema_version"`
	CreatedAt     time.Time `gorm:"column:created_at;not null;index" json:"created_at"`
}

func (TablePrincipalAuthorizationEpochEvent) TableName() string {
	return "governance_principal_authorization_epoch_outbox"
}
