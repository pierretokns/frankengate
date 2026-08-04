// Package ingestion provides a bounded, deterministic observation ledger for
// model and agent cards. It deliberately separates source observations from
// the active catalog so callers can review changes before admission.
package ingestion

import (
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

const (
	MaxSourceIDBytes    = 256
	MaxObservationBytes = agentcard.MaxAgentModelCardJSONBytes
)

type SourceKind string

const (
	SourceA2A      SourceKind = "a2a"
	SourceMCP      SourceKind = "mcp"
	SourceImport   SourceKind = "import"
	SourceProvider SourceKind = "provider"
)

type Observation struct {
	SourceID   string
	SourceKind SourceKind
	ObservedAt time.Time
	ETag       string
	Card       agentcard.AgentModelCard
}

type Snapshot struct {
	SourceID   string
	SourceKind SourceKind
	ObservedAt time.Time
	ETag       string
	Digest     agentcard.Digest
	Card       agentcard.AgentModelCard
}

type ChangeKind string

const (
	ChangeAdded     ChangeKind = "added"
	ChangeRemoved   ChangeKind = "removed"
	ChangeModified  ChangeKind = "modified"
	ChangeUnchanged ChangeKind = "unchanged"
)

type Change struct {
	Kind       ChangeKind
	SourceID   string
	Previous   *Snapshot
	Current    *Snapshot
	DetectedAt time.Time
}

func (c Change) IsAdmissionRequired() bool {
	return c.Kind == ChangeAdded || c.Kind == ChangeModified
}
