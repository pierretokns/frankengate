package modelcatalog

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"slices"
	"sort"
	"strconv"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

const AgentModelCardSchemaVersion = "bifrost.agent_model_card.v1alpha1"

type AgentModelCardSourceKind string

const (
	AgentModelCardSourceKeyConfig       AgentModelCardSourceKind = "key_config"
	AgentModelCardSourceLiveListModels  AgentModelCardSourceKind = "live_list_models"
	AgentModelCardSourceDatasheet       AgentModelCardSourceKind = "datasheet_pricing"
	AgentModelCardSourceModelParameters AgentModelCardSourceKind = "model_parameters"
)

type AgentModelCardFreshnessState string

const (
	AgentModelCardFreshnessFresh               AgentModelCardFreshnessState = "fresh"
	AgentModelCardFreshnessStale               AgentModelCardFreshnessState = "stale"
	AgentModelCardFreshnessUnknown             AgentModelCardFreshnessState = "unknown"
	AgentModelCardFreshnessLocalCacheNoTime    AgentModelCardFreshnessState = "local_cache_no_timestamp"
	AgentModelCardFreshnessSharedWithDatasheet AgentModelCardFreshnessState = "shared_with_datasheet"
	AgentModelCardFreshnessSourceNotConfigured AgentModelCardFreshnessState = "source_not_configured"
)

type AgentModelCapabilityState string

const (
	AgentModelCapabilityKnown   AgentModelCapabilityState = "known"
	AgentModelCapabilityUnknown AgentModelCapabilityState = "unknown"
)

type AgentModelCardSnapshot struct {
	SchemaVersion      string                           `json:"schema_version"`
	GenerationID       string                           `json:"generation_id"`
	GeneratedAt        time.Time                        `json:"generated_at"`
	Revision           AgentModelCardRevision           `json:"revision"`
	SourcePrecedence   []AgentModelCardSourceKind       `json:"source_precedence"`
	Sources            []AgentModelCardSource           `json:"sources"`
	UnknownBehavior    AgentModelCardUnknownBehavior    `json:"unknown_behavior"`
	DeprecatedBehavior AgentModelCardDeprecatedBehavior `json:"deprecated_behavior"`
	Cards              []AgentModelCard                 `json:"cards"`
}

type AgentModelCardRevision struct {
	ID        string `json:"id"`
	CardCount int    `json:"card_count"`
}

type AgentModelCardSource struct {
	Kind      AgentModelCardSourceKind     `json:"kind"`
	Revision  string                       `json:"revision"`
	Freshness AgentModelCardFreshnessState `json:"freshness"`
	Details   map[string]string            `json:"details,omitempty"`
}

type AgentModelCardUnknownBehavior struct {
	CapabilityState string `json:"capability_state"`
	Admission       string `json:"admission"`
	Pricing         string `json:"pricing"`
}

type AgentModelCardDeprecatedBehavior struct {
	Visibility string `json:"visibility"`
	Admission  string `json:"admission"`
}

type AgentModelCard struct {
	Provider              schemas.ModelProvider      `json:"provider"`
	Model                 string                     `json:"model"`
	BaseModel             string                     `json:"base_model"`
	CapabilityState       AgentModelCapabilityState  `json:"capability_state"`
	IsDeprecated          bool                       `json:"is_deprecated"`
	Sources               []AgentModelCardSourceKind `json:"sources"`
	ProviderMapping       AgentModelProviderMapping  `json:"provider_mapping"`
	Aliases               []AgentModelCardAlias      `json:"aliases,omitempty"`
	SupportedRequestTypes []schemas.RequestType      `json:"supported_request_types,omitempty"`
	SupportedParameters   []string                   `json:"supported_parameters,omitempty"`
	Architecture          *schemas.Architecture      `json:"architecture,omitempty"`
	Limits                AgentModelCardLimits       `json:"limits,omitempty"`
	Pricing               *AgentModelCardPricing     `json:"pricing,omitempty"`
	RoutableKeyIDs        []string                   `json:"routable_key_ids,omitempty"`
	LiveKeyIDs            []string                   `json:"live_key_ids,omitempty"`
	UnfilteredLiveKeyIDs  []string                   `json:"unfiltered_live_key_ids,omitempty"`
}

type AgentModelProviderMapping struct {
	Provider       schemas.ModelProvider `json:"provider"`
	RequestedModel string                `json:"requested_model"`
	WireModel      string                `json:"wire_model"`
	CanonicalModel string                `json:"canonical_model,omitempty"`
}

type AgentModelCardAlias struct {
	Alias       string               `json:"alias"`
	KeyID       string               `json:"key_id,omitempty"`
	ModelID     string               `json:"model_id"`
	ModelName   *string              `json:"model_name,omitempty"`
	ModelFamily *schemas.ModelFamily `json:"model_family,omitempty"`
	Description string               `json:"description,omitempty"`
}

type AgentModelCardLimits struct {
	ContextLength   *int `json:"context_length,omitempty"`
	MaxInputTokens  *int `json:"max_input_tokens,omitempty"`
	MaxOutputTokens *int `json:"max_output_tokens,omitempty"`
}

type AgentModelCardPricing struct {
	Mode                          string   `json:"mode,omitempty"`
	InputCostPerToken             *float64 `json:"input_cost_per_token,omitempty"`
	OutputCostPerToken            *float64 `json:"output_cost_per_token,omitempty"`
	CacheReadInputTokenCost       *float64 `json:"cache_read_input_token_cost,omitempty"`
	CacheCreationInputTokenCost   *float64 `json:"cache_creation_input_token_cost,omitempty"`
	InputCostPerImage             *float64 `json:"input_cost_per_image,omitempty"`
	OutputCostPerImage            *float64 `json:"output_cost_per_image,omitempty"`
	SearchContextCostPerQuery     *float64 `json:"search_context_cost_per_query,omitempty"`
	CodeInterpreterCostPerSession *float64 `json:"code_interpreter_cost_per_session,omitempty"`
}

var agentModelCardSourcePrecedence = []AgentModelCardSourceKind{
	AgentModelCardSourceKeyConfig,
	AgentModelCardSourceLiveListModels,
	AgentModelCardSourceDatasheet,
	AgentModelCardSourceModelParameters,
}

var agentModelCardRequestTypes = []schemas.RequestType{
	schemas.TextCompletionRequest,
	schemas.TextCompletionStreamRequest,
	schemas.ChatCompletionRequest,
	schemas.ChatCompletionStreamRequest,
	schemas.ResponsesRequest,
	schemas.ResponsesStreamRequest,
	schemas.EmbeddingRequest,
	schemas.RerankRequest,
	schemas.SpeechRequest,
	schemas.SpeechStreamRequest,
	schemas.TranscriptionRequest,
	schemas.TranscriptionStreamRequest,
	schemas.ImageGenerationRequest,
	schemas.ImageGenerationStreamRequest,
	schemas.ImageEditRequest,
	schemas.ImageEditStreamRequest,
	schemas.ImageVariationRequest,
	schemas.VideoGenerationRequest,
	schemas.VideoRetrieveRequest,
	schemas.VideoDownloadRequest,
	schemas.VideoDeleteRequest,
	schemas.VideoListRequest,
	schemas.VideoRemixRequest,
	schemas.BatchCreateRequest,
	schemas.BatchListRequest,
	schemas.BatchRetrieveRequest,
	schemas.BatchCancelRequest,
	schemas.BatchResultsRequest,
	schemas.BatchDeleteRequest,
	schemas.OCRRequest,
	schemas.RealtimeRequest,
}

// CompileAgentModelCards compiles the current catalog state into a read-only
// snapshot value. The returned slices, maps, and pointer fields do not alias
// the modelcatalog stores; callers should treat the snapshot as immutable.
func (mc *ModelCatalog) CompileAgentModelCards() AgentModelCardSnapshot {
	return mc.CompileAgentModelCardsAt(time.Now())
}

// CompileAgentModelCardsAt is the deterministic form of CompileAgentModelCards.
// It performs no I/O and does not mutate pricing, routing, live-list, or key
// configuration state.
func (mc *ModelCatalog) CompileAgentModelCardsAt(generatedAt time.Time) AgentModelCardSnapshot {
	if generatedAt.IsZero() {
		generatedAt = time.Now()
	}
	generatedAt = generatedAt.UTC()

	liveSnapshot := mapLiveModels(mc)
	cards := compileAgentModelCards(mc, liveSnapshot)
	sourcePrecedence := slices.Clone(agentModelCardSourcePrecedence)
	sources := compileAgentModelCardSources(mc, generatedAt, liveSnapshot)

	revisionID := stableAgentCardHash(struct {
		SchemaVersion    string
		SourcePrecedence []AgentModelCardSourceKind
		SourceRevisions  []agentModelCardSourceRevision
		Cards            []AgentModelCard
	}{
		SchemaVersion:    AgentModelCardSchemaVersion,
		SourcePrecedence: sourcePrecedence,
		SourceRevisions:  agentModelCardSourceRevisions(sources),
		Cards:            cards,
	})

	snapshot := AgentModelCardSnapshot{
		SchemaVersion:    AgentModelCardSchemaVersion,
		GeneratedAt:      generatedAt,
		Revision:         AgentModelCardRevision{ID: revisionID, CardCount: len(cards)},
		SourcePrecedence: sourcePrecedence,
		Sources:          sources,
		UnknownBehavior: AgentModelCardUnknownBehavior{
			CapabilityState: "models without an authoritative datasheet/provider capability row compile as unknown, never unsupported",
			Admission:       "unknown capabilities preserve existing ModelCatalog behavior and remain provider-owned at request time",
			Pricing:         "unknown pricing compiles as nil and does not alter CalculateCost lookup semantics",
		},
		DeprecatedBehavior: AgentModelCardDeprecatedBehavior{
			Visibility: "deprecated datasheet rows remain visible in the compiled snapshot and in existing model lists",
			Admission:  "deprecated is metadata only; the compiler does not deny routing or remove models",
		},
		Cards: cards,
	}
	snapshot.GenerationID = stableAgentCardHash(struct {
		RevisionID  string
		GeneratedAt string
	}{
		RevisionID:  snapshot.Revision.ID,
		GeneratedAt: generatedAt.Format(time.RFC3339Nano),
	})
	return snapshot
}

func compileAgentModelCards(mc *ModelCatalog, liveSnapshot map[schemas.ModelProvider]agentModelCardLiveModels) []AgentModelCard {
	if mc == nil {
		return nil
	}
	providers := mc.knownProviders()
	slices.Sort(providers)

	cards := make([]AgentModelCard, 0)
	for _, provider := range providers {
		models := dedupeSortedStrings(mc.GetModelsForProvider(provider))
		for _, model := range models {
			card := compileAgentModelCard(mc, provider, model, liveSnapshot[provider])
			cards = append(cards, card)
		}
	}
	sort.Slice(cards, func(i, j int) bool {
		if cards[i].Provider != cards[j].Provider {
			return cards[i].Provider < cards[j].Provider
		}
		return cards[i].Model < cards[j].Model
	})
	return cards
}

func compileAgentModelCard(mc *ModelCatalog, provider schemas.ModelProvider, model string, live agentModelCardLiveModels) AgentModelCard {
	aliases := agentModelCardAliases(mc, provider, model)
	metadataModel := agentModelCardMetadataModel(model, aliases)
	entry := mc.GetModelCapabilityEntryForModel(metadataModel, provider)
	params := dedupeSortedStrings(mc.GetSupportedParameters(metadataModel))
	supportedRequestTypes := supportedAgentModelCardRequestTypes(mc, provider, metadataModel)
	routableKeyIDs := dedupeSortedStrings(mc.KeysAllowingModel(provider, model))
	liveKeyIDs := dedupeSortedStrings(live.filtered[model])
	unfilteredLiveKeyIDs := dedupeSortedStrings(live.unfiltered[model])

	baseModel := mc.GetBaseModelName(metadataModel)
	if baseModel == "" {
		baseModel = metadataModel
	}

	mapping := AgentModelProviderMapping{
		Provider:       provider,
		RequestedModel: model,
		WireModel:      model,
		CanonicalModel: baseModel,
	}
	if len(aliases) > 0 {
		mapping.WireModel = aliases[0].ModelID
		if aliases[0].ModelName != nil && *aliases[0].ModelName != "" {
			mapping.CanonicalModel = *aliases[0].ModelName
		}
	}

	capabilityState := AgentModelCapabilityUnknown
	if entry != nil || len(supportedRequestTypes) > 0 {
		capabilityState = AgentModelCapabilityKnown
	}

	card := AgentModelCard{
		Provider:              provider,
		Model:                 model,
		BaseModel:             baseModel,
		CapabilityState:       capabilityState,
		Sources:               agentModelCardSourcesForModel(entry, params, liveKeyIDs, unfilteredLiveKeyIDs, routableKeyIDs, aliases),
		ProviderMapping:       mapping,
		Aliases:               aliases,
		SupportedRequestTypes: supportedRequestTypes,
		SupportedParameters:   params,
		RoutableKeyIDs:        routableKeyIDs,
		LiveKeyIDs:            liveKeyIDs,
		UnfilteredLiveKeyIDs:  unfilteredLiveKeyIDs,
	}
	if entry != nil {
		card.IsDeprecated = entry.IsDeprecated
		card.Architecture = cloneArchitecture(entry.Architecture)
		card.Limits = AgentModelCardLimits{
			ContextLength:   cloneIntPtr(entry.ContextLength),
			MaxInputTokens:  cloneIntPtr(entry.MaxInputTokens),
			MaxOutputTokens: cloneIntPtr(entry.MaxOutputTokens),
		}
		card.Pricing = cloneAgentModelCardPricing(entry)
	}
	return card
}

func supportedAgentModelCardRequestTypes(mc *ModelCatalog, provider schemas.ModelProvider, model string) []schemas.RequestType {
	out := make([]schemas.RequestType, 0, len(agentModelCardRequestTypes))
	for _, requestType := range agentModelCardRequestTypes {
		if mc.IsRequestTypeSupportedForProvider(model, provider, requestType) {
			out = append(out, requestType)
		}
	}
	return out
}

func agentModelCardAliases(mc *ModelCatalog, provider schemas.ModelProvider, model string) []AgentModelCardAlias {
	owner, ok := mc.ResolveAlias(provider, model)
	if !ok {
		return nil
	}
	alias := AgentModelCardAlias{
		Alias:       model,
		KeyID:       owner.KeyID,
		ModelID:     owner.Config.ModelID,
		ModelName:   cloneStringPtr(owner.Config.ModelName),
		ModelFamily: cloneModelFamilyPtr(owner.Config.ModelFamily),
		Description: owner.Config.Description,
	}
	return []AgentModelCardAlias{alias}
}

func agentModelCardMetadataModel(model string, aliases []AgentModelCardAlias) string {
	if len(aliases) == 0 {
		return model
	}
	if aliases[0].ModelName != nil && *aliases[0].ModelName != "" {
		return *aliases[0].ModelName
	}
	if aliases[0].ModelID != "" {
		return aliases[0].ModelID
	}
	return model
}

func agentModelCardSourcesForModel(entry *PricingEntry, params []string, liveKeyIDs []string, unfilteredLiveKeyIDs []string, routableKeyIDs []string, aliases []AgentModelCardAlias) []AgentModelCardSourceKind {
	seen := make(map[AgentModelCardSourceKind]struct{}, len(agentModelCardSourcePrecedence))
	if len(routableKeyIDs) > 0 || len(aliases) > 0 {
		seen[AgentModelCardSourceKeyConfig] = struct{}{}
	}
	if len(liveKeyIDs) > 0 || len(unfilteredLiveKeyIDs) > 0 {
		seen[AgentModelCardSourceLiveListModels] = struct{}{}
	}
	if entry != nil {
		seen[AgentModelCardSourceDatasheet] = struct{}{}
	}
	if len(params) > 0 {
		seen[AgentModelCardSourceModelParameters] = struct{}{}
	}
	out := make([]AgentModelCardSourceKind, 0, len(seen))
	for _, source := range agentModelCardSourcePrecedence {
		if _, ok := seen[source]; ok {
			out = append(out, source)
		}
	}
	return out
}

type agentModelCardLiveModels struct {
	filtered   map[string][]string
	unfiltered map[string][]string
}

func mapLiveModels(mc *ModelCatalog) map[schemas.ModelProvider]agentModelCardLiveModels {
	out := make(map[schemas.ModelProvider]agentModelCardLiveModels)
	if mc == nil || mc.live == nil {
		return out
	}
	for key, entry := range mc.live.Snapshot() {
		providerLive := out[key.Provider]
		if providerLive.filtered == nil {
			providerLive.filtered = make(map[string][]string)
			providerLive.unfiltered = make(map[string][]string)
		}
		target := providerLive.filtered
		if key.Unfiltered {
			target = providerLive.unfiltered
		}
		for _, model := range entry.Models {
			target[model] = append(target[model], key.KeyID)
		}
		out[key.Provider] = providerLive
	}
	return out
}

func compileAgentModelCardSources(mc *ModelCatalog, generatedAt time.Time, liveSnapshot map[schemas.ModelProvider]agentModelCardLiveModels) []AgentModelCardSource {
	return []AgentModelCardSource{
		compileKeyConfigSource(mc),
		compileLiveListModelsSource(liveSnapshot),
		compileDatasheetSource(mc, generatedAt),
		compileModelParametersSource(mc),
	}
}

func compileKeyConfigSource(mc *ModelCatalog) AgentModelCardSource {
	details := map[string]string{"timestamp": "not_tracked"}
	revisionInput := make([]agentModelCardKeyConfigRevisionEntry, 0)
	if mc != nil && mc.keyconf != nil {
		providers := mc.keyconf.Providers()
		slices.Sort(providers)
		details["provider_count"] = strconv.Itoa(len(providers))
		for _, provider := range providers {
			for _, entry := range mc.keyconf.EntriesFor(provider) {
				revisionInput = append(revisionInput, makeAgentModelCardKeyConfigRevisionEntry(provider, entry))
			}
		}
	}
	return AgentModelCardSource{
		Kind:      AgentModelCardSourceKeyConfig,
		Revision:  stableAgentCardHash(revisionInput),
		Freshness: AgentModelCardFreshnessLocalCacheNoTime,
		Details:   details,
	}
}

func compileLiveListModelsSource(liveSnapshot map[schemas.ModelProvider]agentModelCardLiveModels) AgentModelCardSource {
	revisionInput := make([]agentModelCardLiveRevisionEntry, 0)
	entryCount := 0
	for provider, live := range liveSnapshot {
		for model, keyIDs := range live.filtered {
			revisionInput = append(revisionInput, agentModelCardLiveRevisionEntry{
				Provider:   provider,
				Model:      model,
				KeyIDs:     dedupeSortedStrings(keyIDs),
				Unfiltered: false,
			})
			entryCount++
		}
		for model, keyIDs := range live.unfiltered {
			revisionInput = append(revisionInput, agentModelCardLiveRevisionEntry{
				Provider:   provider,
				Model:      model,
				KeyIDs:     dedupeSortedStrings(keyIDs),
				Unfiltered: true,
			})
			entryCount++
		}
	}
	sort.Slice(revisionInput, func(i, j int) bool {
		if revisionInput[i].Provider != revisionInput[j].Provider {
			return revisionInput[i].Provider < revisionInput[j].Provider
		}
		if revisionInput[i].Model != revisionInput[j].Model {
			return revisionInput[i].Model < revisionInput[j].Model
		}
		return !revisionInput[i].Unfiltered && revisionInput[j].Unfiltered
	})
	return AgentModelCardSource{
		Kind:      AgentModelCardSourceLiveListModels,
		Revision:  stableAgentCardHash(revisionInput),
		Freshness: AgentModelCardFreshnessLocalCacheNoTime,
		Details: map[string]string{
			"entry_count": strconv.Itoa(entryCount),
			"timestamp":   "not_tracked",
		},
	}
}

func compileDatasheetSource(mc *ModelCatalog, generatedAt time.Time) AgentModelCardSource {
	source := AgentModelCardSource{
		Kind:      AgentModelCardSourceDatasheet,
		Revision:  "not_configured",
		Freshness: AgentModelCardFreshnessSourceNotConfigured,
	}
	if mc == nil || mc.datasheet == nil {
		return source
	}
	lastSyncedAt := mc.datasheet.LastSyncedAt()
	syncInterval := mc.datasheet.SyncInterval()
	providers := mc.datasheet.DatasheetProviders()
	slices.Sort(providers)

	freshness := AgentModelCardFreshnessUnknown
	revision := "local_memory"
	details := map[string]string{
		"pricing_url":         mc.datasheet.URL(),
		"sync_interval":       syncInterval.String(),
		"datasheet_providers": strconv.Itoa(len(providers)),
		"freshness_timestamp": "pricing_last_synced_at",
	}
	if !lastSyncedAt.IsZero() {
		lastSyncedAt = lastSyncedAt.UTC()
		revision = lastSyncedAt.Format(time.RFC3339Nano)
		details["last_synced_at"] = revision
		if generatedAt.Sub(lastSyncedAt) <= syncInterval {
			freshness = AgentModelCardFreshnessFresh
		} else {
			freshness = AgentModelCardFreshnessStale
		}
	}
	source.Revision = revision
	source.Freshness = freshness
	source.Details = details
	return source
}

func compileModelParametersSource(mc *ModelCatalog) AgentModelCardSource {
	source := AgentModelCardSource{
		Kind:      AgentModelCardSourceModelParameters,
		Revision:  "not_configured",
		Freshness: AgentModelCardFreshnessSourceNotConfigured,
	}
	if mc == nil || mc.datasheet == nil {
		return source
	}
	source.Revision = "co_loaded_with_modelcatalog"
	source.Freshness = AgentModelCardFreshnessSharedWithDatasheet
	source.Details = map[string]string{
		"model_parameters_url": mc.datasheet.ModelParametersURL(),
		"timestamp":            "not_independently_tracked",
	}
	return source
}

type agentModelCardLiveRevisionEntry struct {
	Provider   schemas.ModelProvider `json:"provider"`
	Model      string                `json:"model"`
	KeyIDs     []string              `json:"key_ids,omitempty"`
	Unfiltered bool                  `json:"unfiltered"`
}

type agentModelCardSourceRevision struct {
	Kind     AgentModelCardSourceKind `json:"kind"`
	Revision string                   `json:"revision"`
}

type agentModelCardKeyConfigRevisionEntry struct {
	Provider    schemas.ModelProvider              `json:"provider"`
	KeyID       string                             `json:"key_id"`
	Enabled     bool                               `json:"enabled"`
	Allowed     []string                           `json:"allowed,omitempty"`
	Blacklisted []string                           `json:"blacklisted,omitempty"`
	Aliases     []agentModelCardAliasRevisionEntry `json:"aliases,omitempty"`
}

type agentModelCardAliasRevisionEntry struct {
	Alias       string               `json:"alias"`
	ModelID     string               `json:"model_id"`
	ModelName   *string              `json:"model_name,omitempty"`
	ModelFamily *schemas.ModelFamily `json:"model_family,omitempty"`
	Description string               `json:"description,omitempty"`
}

func agentModelCardSourceRevisions(sources []AgentModelCardSource) []agentModelCardSourceRevision {
	out := make([]agentModelCardSourceRevision, 0, len(sources))
	for _, source := range sources {
		out = append(out, agentModelCardSourceRevision{
			Kind:     source.Kind,
			Revision: source.Revision,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Kind < out[j].Kind })
	return out
}

func makeAgentModelCardKeyConfigRevisionEntry(provider schemas.ModelProvider, entry KeyConfigEntry) agentModelCardKeyConfigRevisionEntry {
	out := agentModelCardKeyConfigRevisionEntry{
		Provider:    provider,
		KeyID:       entry.KeyID,
		Enabled:     entry.Enabled,
		Allowed:     dedupeSortedStrings(entry.Allowed),
		Blacklisted: dedupeSortedStrings(entry.Blacklisted),
		Aliases:     make([]agentModelCardAliasRevisionEntry, 0, len(entry.Aliases)),
	}
	for alias, config := range entry.Aliases {
		out.Aliases = append(out.Aliases, agentModelCardAliasRevisionEntry{
			Alias:       alias,
			ModelID:     config.ModelID,
			ModelName:   cloneStringPtr(config.ModelName),
			ModelFamily: cloneModelFamilyPtr(config.ModelFamily),
			Description: config.Description,
		})
	}
	sort.Slice(out.Aliases, func(i, j int) bool { return out.Aliases[i].Alias < out.Aliases[j].Alias })
	return out
}

func cloneAgentModelCardPricing(entry *PricingEntry) *AgentModelCardPricing {
	if entry == nil {
		return nil
	}
	return &AgentModelCardPricing{
		Mode:                          entry.Mode,
		InputCostPerToken:             cloneFloat64Ptr(entry.InputCostPerToken),
		OutputCostPerToken:            cloneFloat64Ptr(entry.OutputCostPerToken),
		CacheReadInputTokenCost:       cloneFloat64Ptr(entry.CacheReadInputTokenCost),
		CacheCreationInputTokenCost:   cloneFloat64Ptr(entry.CacheCreationInputTokenCost),
		InputCostPerImage:             cloneFloat64Ptr(entry.InputCostPerImage),
		OutputCostPerImage:            cloneFloat64Ptr(entry.OutputCostPerImage),
		SearchContextCostPerQuery:     cloneFloat64Ptr(entry.SearchContextCostPerQuery),
		CodeInterpreterCostPerSession: cloneFloat64Ptr(entry.CodeInterpreterCostPerSession),
	}
}

func cloneArchitecture(in *schemas.Architecture) *schemas.Architecture {
	if in == nil {
		return nil
	}
	return &schemas.Architecture{
		Modality:         cloneStringPtr(in.Modality),
		Tokenizer:        cloneStringPtr(in.Tokenizer),
		InstructType:     cloneStringPtr(in.InstructType),
		InputModalities:  dedupeSortedStrings(in.InputModalities),
		OutputModalities: dedupeSortedStrings(in.OutputModalities),
	}
}

func cloneStringPtr(in *string) *string {
	if in == nil {
		return nil
	}
	out := *in
	return &out
}

func cloneModelFamilyPtr(in *schemas.ModelFamily) *schemas.ModelFamily {
	if in == nil {
		return nil
	}
	out := *in
	return &out
}

func cloneIntPtr(in *int) *int {
	if in == nil {
		return nil
	}
	out := *in
	return &out
}

func cloneFloat64Ptr(in *float64) *float64 {
	if in == nil {
		return nil
	}
	out := *in
	return &out
}

func dedupeSortedStrings(in []string) []string {
	if len(in) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(in))
	out := make([]string, 0, len(in))
	for _, value := range in {
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		out = append(out, value)
	}
	slices.Sort(out)
	return out
}

func stableAgentCardHash(value any) string {
	data, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}
