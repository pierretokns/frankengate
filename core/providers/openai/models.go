package openai

import (
	"strings"

	providerUtils "github.com/maximhq/bifrost/core/providers/utils"
	"github.com/maximhq/bifrost/core/schemas"
)

// ToCodexListModelsResponse adds the richer model-catalog fields consumed by
// Codex TUI. Ordinary OpenAI clients continue to receive the standard schema.
func ToCodexListModelsResponse(ctx *schemas.BifrostContext, response *schemas.BifrostListModelsResponse) *OpenAIListModelsResponse {
	result := ToOpenAIListModelsResponse(response)
	if result == nil || ctx == nil {
		return result
	}
	ua, _ := ctx.Value(schemas.BifrostContextKeyUserAgent).(string)
	if !schemas.CodexCLI.Matches(ua) {
		return result
	}
	for i := range result.Data {
		model := &result.Data[i]
		model.Slug = codexModelSlug(model.ID)
		model.DisplayName = "Codex " + model.Slug[strings.LastIndex(model.Slug, "/")+1:]
		model.ShellType, model.Visibility, model.DefaultReasoningLevel = "shell_command", "list", "medium"
		yes := true
		model.SupportedInAPI, model.SupportsReasoningSummaries, model.SupportVerbosity = &yes, &yes, &yes
		model.DefaultReasoningSummary = "none"
		if strings.Contains(strings.ToLower(model.Slug), "gpt-") {
			lite := true
			model.UseResponsesLite = &lite
			model.SupportedReasoningLevels = []CodexReasoningLevel{{Effort: "low", Description: "Fast responses with lighter reasoning"}, {Effort: "medium", Description: "Balances speed and reasoning depth for everyday tasks"}, {Effort: "high", Description: "Greater reasoning depth for complex problems"}}
		} else {
			lite := false
			model.UseResponsesLite = &lite
			model.DefaultReasoningLevel = ""
		}
	}
	return result
}

func codexModelSlug(id string) string {
	parts := strings.SplitN(id, "/", 2)
	if len(parts) == 2 && strings.HasPrefix(parts[1], "openai.") {
		return parts[0] + "/" + strings.TrimPrefix(parts[1], "openai.")
	}
	return id
}

// ToBifrostListModelsResponse converts an OpenAI list models response to a Bifrost list models response
func (response *OpenAIListModelsResponse) ToBifrostListModelsResponse(providerKey schemas.ModelProvider, allowedModels schemas.WhiteList, blacklistedModels schemas.BlackList, aliases schemas.KeyAliases, unfiltered bool) *schemas.BifrostListModelsResponse {
	if response == nil {
		return nil
	}

	bifrostResponse := &schemas.BifrostListModelsResponse{
		Data: make([]schemas.Model, 0, len(response.Data)),
	}

	pipeline := &providerUtils.ListModelsPipeline{
		AllowedModels:     allowedModels,
		BlacklistedModels: blacklistedModels,
		Aliases:           aliases,
		Unfiltered:        unfiltered,
		ProviderKey:       providerKey,
		MatchFns:          providerUtils.DefaultMatchFns(),
	}
	if pipeline.ShouldEarlyExit() {
		return bifrostResponse
	}

	included := make(map[string]bool)

	for _, model := range response.Data {
		for _, result := range pipeline.FilterModel(model.ID) {
			entry := schemas.Model{
				ID:            string(providerKey) + "/" + result.ResolvedID,
				Created:       model.Created,
				OwnedBy:       schemas.Ptr(model.OwnedBy),
				ContextLength: model.ContextWindow,
			}
			if result.AliasValue != "" {
				entry.Alias = schemas.Ptr(result.AliasValue)
			}
			bifrostResponse.Data = append(bifrostResponse.Data, entry)
			included[strings.ToLower(result.ResolvedID)] = true
		}
	}

	bifrostResponse.Data = append(bifrostResponse.Data,
		pipeline.BackfillModels(included)...)

	return bifrostResponse
}

// ToOpenAIListModelsResponse converts a Bifrost list models response to an OpenAI list models response
func ToOpenAIListModelsResponse(response *schemas.BifrostListModelsResponse) *OpenAIListModelsResponse {
	if response == nil {
		return nil
	}
	openaiResponse := &OpenAIListModelsResponse{
		Data: make([]OpenAIModel, 0, len(response.Data)),
	}
	for _, model := range response.Data {
		openaiModel := OpenAIModel{
			ID:     model.ID,
			Object: "model",
		}
		if model.Created != nil {
			openaiModel.Created = model.Created
		}
		if model.OwnedBy != nil {
			openaiModel.OwnedBy = *model.OwnedBy
		}
		if model.ContextLength != nil {
			openaiModel.ContextWindow = model.ContextLength
		} else if model.MaxInputTokens != nil {
			openaiModel.ContextWindow = model.MaxInputTokens // Fallback to MaxInputTokens if ContextLength is not set
		}

		openaiResponse.Data = append(openaiResponse.Data, openaiModel)

	}
	return openaiResponse
}
