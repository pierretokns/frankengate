package bedrock

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestConvertToolMessagesNestedSmithyTypeStaysText(t *testing.T) {
	toolResult := `{"q":{"__type":1}}`
	input := []schemas.ChatMessage{
		{
			ChatToolMessage: &schemas.ChatToolMessage{
				ToolCallID: schemas.Ptr("tooluse_nested_type"),
			},
			Content: &schemas.ChatMessageContent{ContentStr: &toolResult},
		},
	}

	message, err := convertToolMessages(context.Background(), input)
	require.NoError(t, err)
	require.Len(t, message.Content, 1)
	require.NotNil(t, message.Content[0].ToolResult)
	require.Len(t, message.Content[0].ToolResult.Content, 1)

	content := message.Content[0].ToolResult.Content[0]
	assert.Equal(t, toolResult, *content.Text)
	assert.Nil(t, content.JSON)
}

func TestContainsNestedSmithyType(t *testing.T) {
	tests := []struct {
		name string
		raw  string
		want bool
	}{
		{name: "root key is allowed", raw: `{"__type":"value"}`, want: false},
		{name: "nested object is rejected", raw: `{"q":{"__type":"value"}}`, want: true},
		{name: "array object is rejected", raw: `[{"__type":"value"}]`, want: true},
		{name: "unrelated key is allowed", raw: `{"q":{"__typename":"value"}}`, want: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(t, tt.want, containsNestedSmithyType([]byte(tt.raw)))
		})
	}
}
