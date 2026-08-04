package handlers

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"slices"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog"
	"github.com/valyala/fasthttp"
)

const (
	agentModelCardAPIResponseSchemaVersion        = "bifrost.agent_model_cards.api.v1"
	agentModelCardValidationResponseSchemaVersion = "bifrost.agent_model_card_validation.v1"

	agentModelCardErrorType = "agent_model_card_error"

	agentModelCardReasonCatalogUnavailable   = "agent_model_card_catalog_unavailable"
	agentModelCardReasonModelsUnavailable    = "agent_model_card_models_unavailable"
	agentModelCardReasonMissingParameter     = "agent_model_card_missing_parameter"
	agentModelCardReasonNotFound             = "agent_model_card_not_found"
	agentModelCardReasonResponseEncodeFailed = "agent_model_card_response_encode_failed"
	agentModelCardReasonJSONInvalid          = "agent_model_card_json_invalid"
	agentModelCardReasonPayloadTooLarge      = "agent_model_card_payload_too_large"
	agentModelCardReasonSchemaVersionInvalid = "agent_model_card_schema_version_invalid"
	agentModelCardReasonProviderRequired     = "agent_model_card_provider_required"
	agentModelCardReasonModelRequired        = "agent_model_card_model_required"
	agentModelCardReasonBaseModelRequired    = "agent_model_card_base_model_required"
	agentModelCardReasonProviderMismatch     = "agent_model_card_provider_mapping_mismatch"
	agentModelCardReasonWireModelRequired    = "agent_model_card_wire_model_required"
	agentModelCardReasonCapabilityInvalid    = "agent_model_card_capability_state_invalid"
	agentModelCardReasonSourceInvalid        = "agent_model_card_source_invalid"
	agentModelCardReasonInvalid              = "agent_model_card_invalid"
)

type agentModelCardsListResponse struct {
	SchemaVersion      string                                        `json:"schema_version"`
	CardSchemaVersion  string                                        `json:"card_schema_version"`
	Revision           modelcatalog.AgentModelCardRevision           `json:"revision"`
	SourcePrecedence   []modelcatalog.AgentModelCardSourceKind       `json:"source_precedence"`
	Sources            []modelcatalog.AgentModelCardSource           `json:"sources"`
	UnknownBehavior    modelcatalog.AgentModelCardUnknownBehavior    `json:"unknown_behavior"`
	DeprecatedBehavior modelcatalog.AgentModelCardDeprecatedBehavior `json:"deprecated_behavior"`
	Cards              []modelcatalog.AgentModelCard                 `json:"cards"`
	Total              int                                           `json:"total"`
	Limit              int                                           `json:"limit"`
	Offset             int                                           `json:"offset"`
	HasMore            bool                                          `json:"has_more"`
}

type agentModelCardDetailResponse struct {
	SchemaVersion     string                              `json:"schema_version"`
	CardSchemaVersion string                              `json:"card_schema_version"`
	Revision          modelcatalog.AgentModelCardRevision `json:"revision"`
	Card              modelcatalog.AgentModelCard         `json:"card"`
}

type agentModelCardValidateResponse struct {
	SchemaVersion     string                           `json:"schema_version"`
	CardSchemaVersion string                           `json:"card_schema_version"`
	Valid             bool                             `json:"valid"`
	ReasonCodes       []string                         `json:"reason_codes,omitempty"`
	Reasons           []agentModelCardValidationReason `json:"reasons,omitempty"`
}

type agentModelCardValidationReason struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// listAgentModelCardsV1 handles GET /api/v1/agent-model-cards.
func (h *ProviderHandler) listAgentModelCardsV1(ctx *fasthttp.RequestCtx) {
	query, ok := h.parseModelListQuery(ctx, 20)
	if !ok {
		return
	}

	unpagedQuery := query
	unpagedQuery.Limit = 0
	unpagedQuery.Offset = 0

	snapshot, cards, err := h.visibleAgentModelCards(unpagedQuery)
	if err != nil {
		h.sendAgentModelCardReadError(ctx, err)
		return
	}

	total := len(cards)
	pagedCards, hasMore := paginateAgentModelCards(cards, query.Limit, query.Offset)

	sendAgentModelCardJSONWithETag(ctx, agentModelCardsListResponse{
		SchemaVersion:      agentModelCardAPIResponseSchemaVersion,
		CardSchemaVersion:  snapshot.SchemaVersion,
		Revision:           snapshot.Revision,
		SourcePrecedence:   snapshot.SourcePrecedence,
		Sources:            snapshot.Sources,
		UnknownBehavior:    snapshot.UnknownBehavior,
		DeprecatedBehavior: snapshot.DeprecatedBehavior,
		Cards:              pagedCards,
		Total:              total,
		Limit:              query.Limit,
		Offset:             query.Offset,
		HasMore:            hasMore,
	})
}

// getAgentModelCardV1 handles GET /api/v1/agent-model-cards/detail.
func (h *ProviderHandler) getAgentModelCardV1(ctx *fasthttp.RequestCtx) {
	provider := schemas.ModelProvider(strings.TrimSpace(string(ctx.QueryArgs().Peek("provider"))))
	model := strings.TrimSpace(string(ctx.QueryArgs().Peek("model")))
	if provider == "" || model == "" {
		sendAgentModelCardError(ctx, fasthttp.StatusBadRequest, agentModelCardReasonMissingParameter, "provider and model query parameters are required")
		return
	}

	query, ok := h.parseModelListQuery(ctx, 0)
	if !ok {
		return
	}
	query.Provider = provider
	query.Query = ""
	query.Limit = 0
	query.Offset = 0

	snapshot, cards, err := h.visibleAgentModelCards(query)
	if err != nil {
		h.sendAgentModelCardReadError(ctx, err)
		return
	}

	for _, card := range cards {
		if card.Provider == provider && card.Model == model {
			sendAgentModelCardJSONWithETag(ctx, agentModelCardDetailResponse{
				SchemaVersion:     agentModelCardAPIResponseSchemaVersion,
				CardSchemaVersion: snapshot.SchemaVersion,
				Revision:          snapshot.Revision,
				Card:              card,
			})
			return
		}
	}

	sendAgentModelCardError(ctx, fasthttp.StatusNotFound, agentModelCardReasonNotFound, "agent model card not found")
}

// validateAgentModelCardV1 handles POST /api/v1/agent-model-cards/validate.
// It validates the submitted API card payload and does not persist it.
func (h *ProviderHandler) validateAgentModelCardV1(ctx *fasthttp.RequestCtx) {
	var card modelcatalog.AgentModelCard
	if err := json.Unmarshal(ctx.PostBody(), &card); err != nil {
		reason := agentModelCardReasonJSONInvalid
		if strings.Contains(err.Error(), "exceeds") {
			reason = agentModelCardReasonPayloadTooLarge
		}
		SendJSON(ctx, agentModelCardValidateResponse{
			SchemaVersion:     agentModelCardValidationResponseSchemaVersion,
			CardSchemaVersion: modelcatalog.AgentModelCardSchemaVersion,
			Valid:             false,
			ReasonCodes:       []string{reason},
			Reasons: []agentModelCardValidationReason{{
				Code:    reason,
				Message: err.Error(),
			}},
		})
		return
	}

	reasons := validateAgentModelCardPayload(card)
	if len(reasons) == 0 {
		SendJSON(ctx, agentModelCardValidateResponse{
			SchemaVersion:     agentModelCardValidationResponseSchemaVersion,
			CardSchemaVersion: modelcatalog.AgentModelCardSchemaVersion,
			Valid:             true,
		})
		return
	}

	SendJSON(ctx, agentModelCardValidateResponse{
		SchemaVersion:     agentModelCardValidationResponseSchemaVersion,
		CardSchemaVersion: modelcatalog.AgentModelCardSchemaVersion,
		Valid:             false,
		ReasonCodes:       dedupeAgentModelCardReasonCodes(reasons),
		Reasons:           reasons,
	})
}

func (h *ProviderHandler) visibleAgentModelCards(query modelListQuery) (modelcatalog.AgentModelCardSnapshot, []modelcatalog.AgentModelCard, error) {
	if h.inMemoryStore == nil || h.inMemoryStore.ModelCatalog == nil {
		return modelcatalog.AgentModelCardSnapshot{}, nil, errAgentModelCardCatalogUnavailable
	}
	if h.modelsManager == nil {
		return modelcatalog.AgentModelCardSnapshot{}, nil, errAgentModelCardModelsUnavailable
	}

	visibleModels, _, err := h.listManagementModels(query)
	if err != nil {
		return modelcatalog.AgentModelCardSnapshot{}, nil, err
	}

	visible := make(map[string]struct{}, len(visibleModels))
	for _, model := range visibleModels {
		visible[agentModelCardKey(model.Provider, model.Name)] = struct{}{}
	}

	snapshot := h.inMemoryStore.ModelCatalog.CompileAgentModelCards()
	cards := make([]modelcatalog.AgentModelCard, 0, len(snapshot.Cards))
	for _, card := range snapshot.Cards {
		if _, ok := visible[agentModelCardKey(card.Provider, card.Model)]; ok {
			cards = append(cards, card)
		}
	}
	return snapshot, cards, nil
}

func paginateAgentModelCards(cards []modelcatalog.AgentModelCard, limit int, offset int) ([]modelcatalog.AgentModelCard, bool) {
	if offset > 0 {
		if offset >= len(cards) {
			return []modelcatalog.AgentModelCard{}, false
		}
		cards = cards[offset:]
	}
	if limit <= 0 || limit >= len(cards) {
		return cards, false
	}
	return cards[:limit], true
}

func agentModelCardKey(provider schemas.ModelProvider, model string) string {
	return string(provider) + "\x00" + model
}

var (
	errAgentModelCardCatalogUnavailable = errors.New(agentModelCardReasonCatalogUnavailable)
	errAgentModelCardModelsUnavailable  = errors.New(agentModelCardReasonModelsUnavailable)
)

func (h *ProviderHandler) sendAgentModelCardReadError(ctx *fasthttp.RequestCtx, err error) {
	switch {
	case errors.Is(err, errAgentModelCardCatalogUnavailable):
		sendAgentModelCardError(ctx, fasthttp.StatusServiceUnavailable, agentModelCardReasonCatalogUnavailable, "model catalog not available")
	case errors.Is(err, errAgentModelCardModelsUnavailable):
		sendAgentModelCardError(ctx, fasthttp.StatusServiceUnavailable, agentModelCardReasonModelsUnavailable, "model list manager not available")
	default:
		sendAgentModelCardError(ctx, fasthttp.StatusInternalServerError, agentModelCardReasonInvalid, fmt.Sprintf("failed to list agent model cards: %v", err))
	}
}

func sendAgentModelCardError(ctx *fasthttp.RequestCtx, statusCode int, code string, message string) {
	errorType := agentModelCardErrorType
	bifrostErr := &schemas.BifrostError{
		IsBifrostError: false,
		StatusCode:     &statusCode,
		Error: &schemas.ErrorField{
			Type:    &errorType,
			Code:    &code,
			Message: message,
		},
	}
	SendBifrostError(ctx, bifrostErr)
}

func sendAgentModelCardJSONWithETag(ctx *fasthttp.RequestCtx, payload any) {
	body, err := json.Marshal(payload)
	if err != nil {
		sendAgentModelCardError(ctx, fasthttp.StatusInternalServerError, agentModelCardReasonResponseEncodeFailed, fmt.Sprintf("failed to encode response: %v", err))
		return
	}

	hash := sha256.Sum256(body)
	etag := `"` + hex.EncodeToString(hash[:]) + `"`
	ctx.Response.Header.Set("ETag", etag)
	ctx.Response.Header.Set("Cache-Control", "private, max-age=0, must-revalidate")

	if agentModelCardETagMatches(string(ctx.Request.Header.Peek("If-None-Match")), etag) {
		ctx.SetStatusCode(fasthttp.StatusNotModified)
		ctx.SetBody(nil)
		return
	}

	ctx.SetContentType("application/json")
	ctx.SetStatusCode(fasthttp.StatusOK)
	ctx.SetBody(body)
}

func agentModelCardETagMatches(header string, etag string) bool {
	if header == "" {
		return false
	}
	for _, candidate := range strings.Split(header, ",") {
		candidate = strings.TrimSpace(candidate)
		if candidate == "*" || candidate == etag || strings.TrimPrefix(candidate, "W/") == etag {
			return true
		}
	}
	return false
}

func validateAgentModelCardPayload(card modelcatalog.AgentModelCard) []agentModelCardValidationReason {
	reasons := make([]agentModelCardValidationReason, 0)
	if card.Provider == "" {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonProviderRequired, Message: "provider is required"})
	}
	if strings.TrimSpace(card.Model) == "" {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonModelRequired, Message: "model is required"})
	}
	if strings.TrimSpace(card.BaseModel) == "" {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonBaseModelRequired, Message: "base_model is required"})
	}
	if card.ProviderMapping.Provider != "" && card.ProviderMapping.Provider != card.Provider {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonProviderMismatch, Message: "provider_mapping.provider must match provider"})
	}
	if strings.TrimSpace(card.ProviderMapping.RequestedModel) != "" && card.ProviderMapping.RequestedModel != card.Model {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonProviderMismatch, Message: "provider_mapping.requested_model must match model"})
	}
	if strings.TrimSpace(card.ProviderMapping.WireModel) == "" {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonWireModelRequired, Message: "provider_mapping.wire_model is required"})
	}
	if card.CapabilityState != modelcatalog.AgentModelCapabilityKnown && card.CapabilityState != modelcatalog.AgentModelCapabilityUnknown {
		reasons = append(reasons, agentModelCardValidationReason{Code: agentModelCardReasonCapabilityInvalid, Message: "capability_state must be known or unknown"})
	}
	for i, source := range card.Sources {
		if !validAgentModelCardSource(source) {
			reasons = append(reasons, agentModelCardValidationReason{
				Code:    agentModelCardReasonSourceInvalid,
				Message: fmt.Sprintf("sources[%d] is invalid", i),
			})
		}
	}
	return reasons
}

func validAgentModelCardSource(source modelcatalog.AgentModelCardSourceKind) bool {
	switch source {
	case modelcatalog.AgentModelCardSourceKeyConfig,
		modelcatalog.AgentModelCardSourceLiveListModels,
		modelcatalog.AgentModelCardSourceDatasheet,
		modelcatalog.AgentModelCardSourceModelParameters:
		return true
	default:
		return false
	}
}

func dedupeAgentModelCardReasonCodes(reasons []agentModelCardValidationReason) []string {
	codes := make([]string, 0, len(reasons))
	for _, reason := range reasons {
		if !slices.Contains(codes, reason.Code) {
			codes = append(codes, reason.Code)
		}
	}
	return codes
}
