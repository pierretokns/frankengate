package mantleservice

import (
	"encoding/json"
	"testing"
)

func TestNegativeObservationRowsCannotMutateIntoChatAuthority(t *testing.T) {
	var original Coverage
	if err := json.Unmarshal(coverageJSON, &original); err != nil {
		t.Fatal(err)
	}
	mutations := []struct {
		name  string
		apply func(*ModelRow)
	}{
		{"chat flag", func(row *ModelRow) { row.Chat = true }},
		{"chat path", func(row *ModelRow) { row.ChatPath = "/openai/v1/chat/completions" }},
		{"chat grammar", func(row *ModelRow) { row.ChatEventGrammar = "openai-chat-completions-json-v1" }},
		{"chat streaming", func(row *ModelRow) { row.ChatStreaming = true }},
		{"internally consistent chat trio", func(row *ModelRow) {
			row.Chat = true
			row.ChatPath = "/openai/v1/chat/completions"
			row.ChatEventGrammar = "openai-chat-completions-json-v1"
		}},
	}
	for _, mutation := range mutations {
		t.Run(mutation.name, func(t *testing.T) {
			candidate := original
			candidate.Rows = append([]ModelRow(nil), original.Rows...)
			for index := range candidate.Rows {
				if candidate.Rows[index].ModelID == "openai.gpt-5.6-sol" {
					mutation.apply(&candidate.Rows[index])
					break
				}
			}
			data, err := json.Marshal(candidate)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := newServiceFromCoverage(data); err == nil {
				t.Fatal("negative route observation authorized Chat after mutation")
			}
		})
	}
}
