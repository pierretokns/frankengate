package handlers

import (
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"github.com/bytedance/sonic"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/logstore"
	"github.com/valyala/fasthttp"
)

const (
	selfServiceHistoryDefaultLimit = 50
	selfServiceHistoryMaxLimit     = 200
	selfServiceEvalSampleLimit     = 200
)

type evalSuggestionEvidence struct {
	MatchingTraces int      `json:"matching_traces"`
	SampleTraceIDs []string `json:"sample_trace_ids,omitempty"`
	Explanation    string   `json:"explanation"`
}

type evalGuidedQuestion struct {
	ID       string `json:"id"`
	Question string `json:"question"`
	Why      string `json:"why"`
}

type evalSuggestion struct {
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	Description      string                 `json:"description"`
	Priority         int                    `json:"priority"`
	Capability       string                 `json:"capability"`
	ExampleRequest   string                 `json:"example_request,omitempty"`
	RecommendedCheck string                 `json:"recommended_check"`
	Verifier         string                 `json:"verifier"`
	Evidence         evalSuggestionEvidence `json:"evidence"`
	Questions        []evalGuidedQuestion   `json:"questions"`
}

type evalAssistantResponse struct {
	TraceCount  int              `json:"trace_count"`
	Suggestions []evalSuggestion `json:"suggestions"`
	Method      struct {
		TraceUse        string `json:"trace_use"`
		Workflow        string `json:"workflow"`
		Interchange     string `json:"interchange"`
		SourceVersion   string `json:"source_version"`
		SourceReference string `json:"source_reference"`
	} `json:"method"`
}

type evalPlanRequest struct {
	SuggestionID string            `json:"suggestion_id"`
	Answers      map[string]string `json:"answers"`
}

type evalPlanResponse struct {
	SuggestionID string            `json:"suggestion_id"`
	TaskID       string            `json:"task_id"`
	Capability   string            `json:"capability"`
	Scenario     string            `json:"scenario"`
	Runtime      string            `json:"runtime"`
	Dependencies string            `json:"dependencies"`
	Success      string            `json:"success"`
	Verifier     string            `json:"verifier"`
	Answers      map[string]string `json:"answers"`
	NextSteps    []string          `json:"next_steps"`
}

func authenticatedUserID(ctx *fasthttp.RequestCtx) (string, bool) {
	userID, ok := ctx.UserValue(schemas.BifrostContextKeyUserID).(string)
	userID = strings.TrimSpace(userID)
	return userID, ok && userID != ""
}

func parseSelfServicePagination(ctx *fasthttp.RequestCtx) (*logstore.PaginationOptions, error) {
	pagination := &logstore.PaginationOptions{
		Limit:  selfServiceHistoryDefaultLimit,
		Offset: 0,
		SortBy: "timestamp",
		Order:  "desc",
	}
	if raw := string(ctx.QueryArgs().Peek("limit")); raw != "" {
		limit, err := strconv.Atoi(raw)
		if err != nil || limit < 1 || limit > selfServiceHistoryMaxLimit {
			return nil, fmt.Errorf("limit must be between 1 and %d", selfServiceHistoryMaxLimit)
		}
		pagination.Limit = limit
	}
	if raw := string(ctx.QueryArgs().Peek("offset")); raw != "" {
		offset, err := strconv.Atoi(raw)
		if err != nil || offset < 0 {
			return nil, fmt.Errorf("offset must be a non-negative integer")
		}
		pagination.Offset = offset
	}
	return pagination, nil
}

// getMyPromptHistory is intentionally separate from the operator log APIs. The
// caller cannot supply a user ID: identity is taken only from authenticated
// request context and the query fails closed when that identity is unavailable.
func (h *LoggingHandler) getMyPromptHistory(ctx *fasthttp.RequestCtx) {
	userID, ok := authenticatedUserID(ctx)
	if !ok {
		SendError(ctx, fasthttp.StatusUnauthorized, "authenticated user identity is required")
		return
	}
	pagination, err := parseSelfServicePagination(ctx)
	if err != nil {
		SendError(ctx, fasthttp.StatusBadRequest, err.Error())
		return
	}
	result, err := h.logManager.Search(ctx, &logstore.SearchFilters{UserIDs: []string{userID}}, pagination)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "failed to load prompt history")
		return
	}
	if result == nil {
		result = &logstore.SearchResult{Logs: []logstore.Log{}, Pagination: *pagination}
	}
	SendJSON(ctx, result)
}

func sampleIDs(logs []logstore.Log, match func(logstore.Log) bool) []string {
	ids := make([]string, 0, 3)
	for _, entry := range logs {
		if match(entry) {
			ids = append(ids, entry.ID)
			if len(ids) == 3 {
				break
			}
		}
	}
	return ids
}

func lastUserPrompt(entry logstore.Log) string {
	for i := len(entry.InputHistoryParsed) - 1; i >= 0; i-- {
		message := entry.InputHistoryParsed[i]
		if message.Role != schemas.ChatMessageRoleUser || message.Content == nil || message.Content.ContentStr == nil {
			continue
		}
		if prompt := strings.TrimSpace(*message.Content.ContentStr); prompt != "" {
			const maxPromptLength = 240
			if len(prompt) > maxPromptLength {
				return prompt[:maxPromptLength] + "…"
			}
			return prompt
		}
	}
	if summary := strings.TrimSpace(entry.ContentSummary); summary != "" {
		return summary
	}
	return ""
}

func commonQuestions() []evalGuidedQuestion {
	return []evalGuidedQuestion{
		{ID: "good_result", Question: "What would a clearly good result look like for this request?", Why: "This defines the behavior to score without treating a recorded answer as ground truth."},
		{ID: "must_not_happen", Question: "What failure must never happen?", Why: "This identifies a safety or regression invariant."},
		{ID: "runtime", Question: "Can the active application run safely against frozen or simulated dependencies?", Why: "This sets the controlled runtime and environment boundary."},
	}
}

func buildEvalSuggestions(logs []logstore.Log) []evalSuggestion {
	if len(logs) == 0 {
		return []evalSuggestion{}
	}

	errorCount, toolCount, longContextCount, stopRiskCount := 0, 0, 0, 0
	models := make(map[string]struct{})
	latencies := make([]float64, 0, len(logs))
	for _, entry := range logs {
		models[entry.Model] = struct{}{}
		if entry.Status == "error" {
			errorCount++
		}
		if len(entry.ToolCallsParsed) > 0 || len(entry.ToolsParsed) > 1 {
			toolCount++
		}
		if len(entry.InputHistoryParsed)+len(entry.ResponsesInputHistoryParsed) >= 6 {
			longContextCount++
		}
		if entry.StopReason != nil && (*entry.StopReason == "content_filter" || *entry.StopReason == "length") {
			stopRiskCount++
		}
		if entry.Latency != nil {
			latencies = append(latencies, *entry.Latency)
		}
	}

	firstPrompt := lastUserPrompt(logs[0])
	suggestions := []evalSuggestion{{
		ID:               "trace-regression",
		Name:             "Representative prompt regression",
		Description:      "Turn a recurring real request into a small, versioned regression case.",
		Priority:         60,
		Capability:       "Preserve useful behavior on representative user requests",
		ExampleRequest:   firstPrompt,
		RecommendedCheck: "Use a semantic judge for task success plus deterministic checks for required structure, citations, or actions.",
		Verifier:         "hybrid",
		Evidence: evalSuggestionEvidence{
			MatchingTraces: len(logs),
			SampleTraceIDs: sampleIDs(logs, func(logstore.Log) bool { return true }),
			Explanation:    "Your recent history supplies realistic requests, but recorded outputs should be treated as examples rather than truth.",
		},
		Questions: commonQuestions(),
	}}

	if errorCount > 0 {
		suggestions = append(suggestions, evalSuggestion{
			ID:               "error-recovery",
			Name:             "Failure recovery and fallback",
			Description:      "Check that transient provider or tool failures produce an honest recovery, fallback, or actionable error.",
			Priority:         100 + errorCount,
			Capability:       "Recover safely from dependency failures",
			RecommendedCheck: "Inject a controlled failure and deterministically verify retry/fallback behavior; judge only the final user-facing usefulness.",
			Verifier:         "hybrid",
			Evidence:         evalSuggestionEvidence{MatchingTraces: errorCount, SampleTraceIDs: sampleIDs(logs, func(l logstore.Log) bool { return l.Status == "error" }), Explanation: "Recent traces contain failed requests."},
			Questions:        commonQuestions(),
		})
	}
	if toolCount > 0 {
		suggestions = append(suggestions, evalSuggestion{
			ID:               "tool-selection",
			Name:             "Tool choice and argument correctness",
			Description:      "Distinguish correct tool selection, valid arguments, and grounded use of tool results.",
			Priority:         90 + toolCount,
			Capability:       "Choose and use the right tool",
			RecommendedCheck: "Use competing tools and frozen records; deterministically score calls and state, then semantically score the answer.",
			Verifier:         "hybrid",
			Evidence:         evalSuggestionEvidence{MatchingTraces: toolCount, SampleTraceIDs: sampleIDs(logs, func(l logstore.Log) bool { return len(l.ToolCallsParsed) > 0 || len(l.ToolsParsed) > 1 }), Explanation: "Recent traces exercise tool-enabled requests."},
			Questions:        commonQuestions(),
		})
	}
	if longContextCount > 0 {
		suggestions = append(suggestions, evalSuggestion{
			ID:               "context-retention",
			Name:             "Multi-turn context retention",
			Description:      "Check whether the assistant preserves relevant constraints across a longer conversation without carrying forward stale facts.",
			Priority:         80 + longContextCount,
			Capability:       "Use relevant prior-turn context",
			RecommendedCheck: "Create a multi-turn task with one required earlier constraint and one distractor; score both retention and non-use of stale context.",
			Verifier:         "hybrid",
			Evidence:         evalSuggestionEvidence{MatchingTraces: longContextCount, SampleTraceIDs: sampleIDs(logs, func(l logstore.Log) bool { return len(l.InputHistoryParsed)+len(l.ResponsesInputHistoryParsed) >= 6 }), Explanation: "Recent traces contain longer conversation histories."},
			Questions:        commonQuestions(),
		})
	}
	if stopRiskCount > 0 {
		suggestions = append(suggestions, evalSuggestion{
			ID:               "boundary-behavior",
			Name:             "Length and policy boundary behavior",
			Description:      "Check that truncation or policy boundaries lead to safe, useful, and explicit behavior.",
			Priority:         85 + stopRiskCount,
			Capability:       "Handle output and policy boundaries honestly",
			RecommendedCheck: "Deterministically assert the boundary condition and use a semantic rubric for clarity, safety, and next-step usefulness.",
			Verifier:         "hybrid",
			Evidence: evalSuggestionEvidence{MatchingTraces: stopRiskCount, SampleTraceIDs: sampleIDs(logs, func(l logstore.Log) bool {
				return l.StopReason != nil && (*l.StopReason == "content_filter" || *l.StopReason == "length")
			}), Explanation: "Recent traces stopped because of a length or content boundary."},
			Questions: commonQuestions(),
		})
	}
	if len(models) > 1 {
		suggestions = append(suggestions, evalSuggestion{
			ID:               "model-portability",
			Name:             "Model portability",
			Description:      "Run the same representative cases across the models present in your history.",
			Priority:         70 + len(models),
			Capability:       "Maintain task quality across model changes",
			RecommendedCheck: "Use the same frozen dataset, prompt version, judge rubric, and deterministic checks for every model candidate.",
			Verifier:         "hybrid",
			Evidence:         evalSuggestionEvidence{MatchingTraces: len(logs), SampleTraceIDs: sampleIDs(logs, func(logstore.Log) bool { return true }), Explanation: fmt.Sprintf("Recent traces use %d different models.", len(models))},
			Questions:        commonQuestions(),
		})
	}
	if len(latencies) >= 5 {
		sort.Float64s(latencies)
		p95 := latencies[int(math.Ceil(float64(len(latencies))*0.95))-1]
		suggestions = append(suggestions, evalSuggestion{
			ID:               "latency-budget",
			Name:             "Latency budget",
			Description:      "Protect user-visible responsiveness while preserving task quality.",
			Priority:         50,
			Capability:       "Complete representative work within an explicit latency budget",
			RecommendedCheck: "Measure wall-clock latency deterministically and keep quality as a separate score; do not collapse them into one opaque judge score.",
			Verifier:         "deterministic",
			Evidence:         evalSuggestionEvidence{MatchingTraces: len(latencies), SampleTraceIDs: sampleIDs(logs, func(l logstore.Log) bool { return l.Latency != nil }), Explanation: fmt.Sprintf("Observed p95 latency in this sample is %.0f ms.", p95)},
			Questions:        commonQuestions(),
		})
	}

	sort.SliceStable(suggestions, func(i, j int) bool { return suggestions[i].Priority > suggestions[j].Priority })
	return suggestions
}

func (h *LoggingHandler) getMyEvalSuggestions(ctx *fasthttp.RequestCtx) {
	userID, ok := authenticatedUserID(ctx)
	if !ok {
		SendError(ctx, fasthttp.StatusUnauthorized, "authenticated user identity is required")
		return
	}
	result, err := h.logManager.Search(ctx, &logstore.SearchFilters{UserIDs: []string{userID}}, &logstore.PaginationOptions{
		Limit: selfServiceEvalSampleLimit, SortBy: "timestamp", Order: "desc",
	})
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "failed to analyze prompt history")
		return
	}
	logs := []logstore.Log{}
	if result != nil {
		logs = result.Logs
	}
	response := evalAssistantResponse{TraceCount: len(logs), Suggestions: buildEvalSuggestions(logs)}
	response.Method.TraceUse = "Traces identify realistic requests and failure patterns; recorded outputs are never treated as ground truth."
	response.Method.Workflow = "Choose one capability, answer the guided questions, approve the runtime and dependency boundary, then build one isolated eval task."
	response.Method.Interchange = "Preserve native logs; use OpenTelemetry/OpenInference for correlation and explicit trajectory projections for replay or eval."
	response.Method.SourceVersion = "langchain-ai/langchain-skills@26b7f14e9657ca7c9caadc6eacc844240489305b"
	response.Method.SourceReference = "config/skills/eval-engineering"
	SendJSON(ctx, response)
}

func (h *LoggingHandler) createMyEvalPlan(ctx *fasthttp.RequestCtx) {
	userID, ok := authenticatedUserID(ctx)
	if !ok {
		SendError(ctx, fasthttp.StatusUnauthorized, "authenticated user identity is required")
		return
	}
	var request evalPlanRequest
	if err := sonic.Unmarshal(ctx.PostBody(), &request); err != nil {
		SendError(ctx, fasthttp.StatusBadRequest, "invalid eval plan request")
		return
	}
	result, err := h.logManager.Search(ctx, &logstore.SearchFilters{UserIDs: []string{userID}}, &logstore.PaginationOptions{
		Limit: selfServiceEvalSampleLimit, SortBy: "timestamp", Order: "desc",
	})
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "failed to analyze prompt history")
		return
	}
	logs := []logstore.Log{}
	if result != nil {
		logs = result.Logs
	}
	var selected *evalSuggestion
	for _, suggestion := range buildEvalSuggestions(logs) {
		if suggestion.ID == strings.TrimSpace(request.SuggestionID) {
			copy := suggestion
			selected = &copy
			break
		}
	}
	if selected == nil {
		SendError(ctx, fasthttp.StatusBadRequest, "unknown or unavailable suggestion_id")
		return
	}
	answers := request.Answers
	if answers == nil {
		answers = map[string]string{}
	}
	scenario := selected.ExampleRequest
	if scenario == "" {
		scenario = "Select and redact one representative request from the cited traces."
	}
	if value := strings.TrimSpace(answers["good_result"]); value != "" {
		scenario += " A good result: " + value
	}
	plan := evalPlanResponse{
		SuggestionID: selected.ID,
		TaskID:       "eval-" + selected.ID,
		Capability:   selected.Capability,
		Scenario:     scenario,
		Runtime:      firstNonEmpty(answers["runtime"], "Active application entrypoint in an isolated environment; use a reconstruction only when the active runtime cannot be controlled."),
		Dependencies: "Freeze or simulate backing data and dependency behavior; never write to production.",
		Success:      firstNonEmpty(answers["good_result"], selected.RecommendedCheck),
		Verifier:     selected.Verifier,
		Answers:      answers,
		NextSteps: []string{
			"Review and approve the runtime, credentials, backing data, and mutation boundary.",
			"Create one task for this capability with hidden expected outcomes and resettable state.",
			"Test the verifier with one clearly valid and one realistic invalid result before running the target.",
			"Keep the trace-to-dataset lineage and record infrastructure failures separately from target failures.",
		},
	}
	if forbidden := strings.TrimSpace(answers["must_not_happen"]); forbidden != "" {
		plan.Success += " The eval must reject: " + forbidden
	}
	SendJSON(ctx, plan)
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			return trimmed
		}
	}
	return ""
}
