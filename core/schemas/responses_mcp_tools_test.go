package schemas

import (
	"testing"

	"github.com/bytedance/sonic"
	"github.com/tidwall/gjson"
)

func TestResponsesToolMCPAllowedToolsArrayRoundTrip(t *testing.T) {
	raw := `{"type":"mcp","server_label":"corp","allowed_tools":["search","read"]}`
	var tool ResponsesTool
	if err := sonic.Unmarshal([]byte(raw), &tool); err != nil {
		t.Fatal(err)
	}
	out, err := sonic.Marshal(&tool)
	if err != nil {
		t.Fatal(err)
	}
	if got := gjson.GetBytes(out, "allowed_tools.#").Int(); got != 2 {
		t.Fatalf("allowed_tools array lost: %s", out)
	}
	if got := gjson.GetBytes(out, "allowed_tools.0").String(); got != "search" {
		t.Fatalf("first allowed tool = %q", got)
	}
}

func TestResponsesToolMCPAllowedToolsFilterRoundTrip(t *testing.T) {
	raw := `{"type":"mcp","server_label":"corp","allowed_tools":{"read_only":true,"tool_names":["search"]}}`
	var tool ResponsesTool
	if err := sonic.Unmarshal([]byte(raw), &tool); err != nil {
		t.Fatal(err)
	}
	out, err := sonic.Marshal(&tool)
	if err != nil {
		t.Fatal(err)
	}
	if !gjson.GetBytes(out, "allowed_tools").IsObject() {
		t.Fatalf("allowed_tools filter was not an object: %s", out)
	}
	if got := gjson.GetBytes(out, "allowed_tools.read_only").Bool(); !got {
		t.Fatal("read_only filter was lost")
	}
	if got := gjson.GetBytes(out, "allowed_tools.tool_names.0").String(); got != "search" {
		t.Fatalf("filter tool name = %q", got)
	}
}
