package tables

import (
	"strings"
	"time"
)

const (
	VirtualKeyInvalidationEntityType           = "virtual_key"
	VirtualKeyInvalidationActionReload         = "reload"
	VirtualKeyInvalidationActionDelete         = "delete"
	VirtualKeyInvalidationSchemaVersion uint16 = 1
	MCPClientInvalidationEntityIDPrefix        = "__frankengate_mcp_client__:"
)

func MCPClientInvalidationEntityID(clientID string) string {
	return MCPClientInvalidationEntityIDPrefix + clientID
}

func ParseMCPClientInvalidationEntityID(entityID string) (string, bool) {
	clientID, ok := strings.CutPrefix(entityID, MCPClientInvalidationEntityIDPrefix)
	return clientID, ok && clientID != ""
}

func IsReservedVirtualKeyEntityID(entityID string) bool {
	return strings.HasPrefix(entityID, MCPClientInvalidationEntityIDPrefix)
}

// TableVirtualKeyInvalidationEvent is an immutable, cursor-addressable signal
// that a consumer must reload or delete one virtual key from its local snapshot.
// MCP control records use a reserved EntityID prefix while retaining the v1
// virtual_key entity type: pre-MCP consumers safely treat the reserved ID as a
// nonexistent VK and advance, which makes rolling upgrades backward compatible.
// ID is the durable global ordering token; consumers persist the greatest ID
// they have successfully applied and may safely apply an event more than once.
type TableVirtualKeyInvalidationEvent struct {
	ID            uint64    `gorm:"column:id;primaryKey;autoIncrement" json:"id"`
	EntityType    string    `gorm:"column:entity_type;type:varchar(64);not null" json:"entity_type"`
	Action        string    `gorm:"column:action;type:varchar(32);not null" json:"action"`
	EntityID      string    `gorm:"column:entity_id;type:varchar(255);not null;index:idx_vk_invalidation_entity" json:"entity_id"`
	TenantID      *string   `gorm:"column:tenant_id;type:varchar(255);index:idx_vk_invalidation_tenant" json:"tenant_id,omitempty"`
	Scope         *string   `gorm:"column:scope;type:varchar(255)" json:"scope,omitempty"`
	SchemaVersion uint16    `gorm:"column:schema_version;not null;default:1" json:"schema_version"`
	CreatedAt     time.Time `gorm:"column:created_at;not null;index" json:"created_at"`
}

func (TableVirtualKeyInvalidationEvent) TableName() string {
	return "governance_virtual_key_invalidation_outbox"
}
