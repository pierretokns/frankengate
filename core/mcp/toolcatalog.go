//go:build !tinygo && !wasm

package mcp

import (
	"slices"
	"strings"
	"unicode"

	"github.com/maximhq/bifrost/core/schemas"
)

// ToolSearchResult is the compact, deterministic result returned by the
// gateway-native tool catalog. The full JSON schema is included so callers
// can load a result into a model context without listing every tool first.
type ToolSearchResult struct {
	Tool  schemas.ChatTool `json:"tool"`
	Score int              `json:"score"`
}

// SearchTools searches only the tools visible in ctx. Authorization and
// request filters are applied by GetToolPerClient before the catalog is
// scored, so a hidden tool cannot be revealed by a query.
//
// The scorer is intentionally small and dependency-free: exact name matches
// win, followed by name-token and description-token matches. Stable name
// ordering makes results reproducible for caching and audit records.
func (m *MCPManager) SearchTools(ctx *schemas.BifrostContext, query string, limit int) []ToolSearchResult {
	if ctx == nil {
		ctx = schemas.NewBifrostContext(m.ctx, schemas.NoDeadline)
	}
	if limit <= 0 {
		limit = 10
	}
	if limit > 50 {
		limit = 50
	}

	terms := toolSearchTerms(query)
	available := m.toolsManager.GetAvailableTools(ctx)
	results := make([]ToolSearchResult, 0, len(available))
	for _, tool := range available {
		if tool.Function == nil || tool.Function.Name == "" {
			continue
		}
		name := tool.Function.Name
		description := ""
		if tool.Function.Description != nil {
			description = *tool.Function.Description
		}
		score := scoreToolSearch(name, description, terms)
		if len(terms) > 0 && score == 0 {
			continue
		}
		results = append(results, ToolSearchResult{Tool: tool, Score: score})
	}

	slices.SortStableFunc(results, func(a, b ToolSearchResult) int {
		if a.Score != b.Score {
			if a.Score > b.Score {
				return -1
			}
			return 1
		}
		return strings.Compare(a.Tool.Function.Name, b.Tool.Function.Name)
	})
	if len(results) > limit {
		results = results[:limit]
	}
	return results
}

func toolSearchTerms(query string) []string {
	seen := make(map[string]struct{})
	terms := make([]string, 0, 4)
	for _, term := range strings.FieldsFunc(strings.ToLower(query), func(r rune) bool {
		return !unicode.IsLetter(r) && !unicode.IsNumber(r)
	}) {
		if term == "" {
			continue
		}
		if _, ok := seen[term]; ok {
			continue
		}
		seen[term] = struct{}{}
		terms = append(terms, term)
	}
	return terms
}

func scoreToolSearch(name, description string, terms []string) int {
	if len(terms) == 0 {
		return 1
	}
	lowerName := strings.ToLower(name)
	lowerDescription := strings.ToLower(description)
	nameTerms := toolSearchTerms(name)
	descriptionTerms := toolSearchTerms(description)
	score := 0
	for _, term := range terms {
		matched := false
		for _, nameTerm := range nameTerms {
			if nameTerm == term {
				score += 10
				matched = true
			} else if strings.HasPrefix(nameTerm, term) || strings.HasPrefix(term, nameTerm) {
				score += 6
				matched = true
			}
		}
		if !matched && strings.Contains(lowerName, term) {
			score += 4
			matched = true
		}
		if matched {
			continue
		}
		for _, descriptionTerm := range descriptionTerms {
			if descriptionTerm == term {
				score += 3
				matched = true
				break
			}
		}
		if !matched && strings.Contains(lowerDescription, term) {
			score++
		}
	}
	return score
}
