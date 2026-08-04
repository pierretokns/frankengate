// Package inbound generates A2A Agent Cards for FrankenGate-hosted workflows.
// It is deliberately transport-free: HTTP handlers can serve the generated
// cards later without owning card canonicalization.
package inbound

import (
	"encoding/json"

	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

type Record struct {
	Card      CardRecord
	Workflows []WorkflowRecord
}

type CardRecord struct {
	Name                              string
	Description                       string
	Version                           string
	Provider                          *a2adiscovery.AgentProvider
	Interfaces                        []InterfaceRecord
	Capabilities                      a2adiscovery.AgentCapabilities
	DefaultInputModes                 []string
	DefaultOutputModes                []string
	SecuritySchemes                   []SecuritySchemeRecord
	Security                          []SecurityRequirementRecord
	SupportsAuthenticatedExtendedCard bool
	Extensions                        map[string]json.RawMessage
}

type InterfaceRecord struct {
	Order     int
	URL       string
	Transport a2adiscovery.TransportBinding
}

type WorkflowRecord struct {
	Order       int
	ID          string
	Name        string
	Description string
	Tags        []string
	Examples    []string
	InputModes  []string
	OutputModes []string
	Extensions  map[string]json.RawMessage
}

type SecuritySchemeRecord struct {
	Order  int
	ID     string
	Scheme a2adiscovery.SecurityScheme
}

type SecurityRequirementRecord struct {
	Order   int
	Schemes []SecurityRequirementScheme
}

type SecurityRequirementScheme struct {
	Order  int
	ID     string
	Scopes []string
}
