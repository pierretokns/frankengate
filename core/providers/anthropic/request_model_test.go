package anthropic

import "testing"

func TestRequestModelForBetaFiltering(t *testing.T) {
	tests := []struct {
		name string
		body string
		want string
	}{
		{name: "anthropic request", body: `{"model":"claude-sonnet-4-6","messages":[]}`, want: "claude-sonnet-4-6"},
		{name: "whitespace trimmed", body: `{"model":"  claude-opus-4-6  "}`, want: "claude-opus-4-6"},
		{name: "missing fails closed", body: `{"messages":[]}`, want: ""},
		{name: "malformed fails closed", body: `{`, want: ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := requestModelForBetaFiltering([]byte(tt.body)); got != tt.want {
				t.Fatalf("requestModelForBetaFiltering() = %q, want %q", got, tt.want)
			}
		})
	}
}
