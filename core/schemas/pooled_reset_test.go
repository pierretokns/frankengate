package schemas

import (
	"context"
	"fmt"
	"math/rand"
	"reflect"
	"testing"
)

var sensitivePooledStructFields = map[reflect.Type][]string{
	reflect.TypeOf(HTTPRequest{}): {
		"Method",
		"Path",
		"Headers",
		"Query",
		"Body",
		"PathParams",
	},
	reflect.TypeOf(HTTPResponse{}): {
		"StatusCode",
		"Headers",
		"Body",
	},
	reflect.TypeOf(ChatToResponsesStreamState{}): {
		"ToolArgumentBuffers",
		"ItemIDs",
		"ToolCallNames",
		"ToolCallIndexToID",
		"MessageID",
		"Model",
		"CreatedAt",
		"HasEmittedCreated",
		"HasEmittedInProgress",
		"TextItemAdded",
		"TextItemClosed",
		"TextItemHasContent",
		"TextBuffer",
		"CurrentOutputIndex",
		"ToolCallOutputIndices",
		"SequenceNumber",
	},
	reflect.TypeOf(pluginLogStore{}): {
		"mu",
		"logs",
	},
}

func TestSensitivePooledStructFieldInventoryIsExplicit(t *testing.T) {
	for typ, fields := range sensitivePooledStructFields {
		covered := make(map[string]bool, len(fields))
		for _, field := range fields {
			covered[field] = true
			if _, ok := typ.FieldByName(field); !ok {
				t.Fatalf("%s inventory names unknown field %q", typ.Name(), field)
			}
		}

		for i := 0; i < typ.NumField(); i++ {
			field := typ.Field(i)
			if !covered[field.Name] {
				t.Fatalf("%s field %q is not classified in sensitivePooledStructFields", typ.Name(), field.Name)
			}
		}
	}
}

func assertResetChecksCoverInventory(t *testing.T, typ reflect.Type, checkedFields []string) {
	t.Helper()

	inventory, ok := sensitivePooledStructFields[typ]
	if !ok {
		t.Fatalf("%s has no sensitive pooled field inventory", typ.Name())
	}

	checked := make(map[string]bool, len(checkedFields))
	for _, field := range checkedFields {
		checked[field] = true
	}
	for _, field := range inventory {
		if !checked[field] {
			t.Fatalf("%s field %q is inventoried but not checked by reset assertion", typ.Name(), field)
		}
	}
	for field := range checked {
		if _, ok := typ.FieldByName(field); !ok {
			t.Fatalf("%s reset assertion checks unknown field %q", typ.Name(), field)
		}
	}
}

func assertHTTPRequestReset(t *testing.T, req *HTTPRequest) {
	t.Helper()
	assertResetChecksCoverInventory(t, reflect.TypeOf(HTTPRequest{}), []string{
		"Method",
		"Path",
		"Headers",
		"Query",
		"Body",
		"PathParams",
	})
	if req.Method != "" || req.Path != "" || req.Body != nil {
		t.Fatalf("request kept scalar residue: method=%q path=%q body=%q", req.Method, req.Path, string(req.Body))
	}
	if req.Headers == nil || len(req.Headers) != 0 {
		t.Fatalf("request Headers = %#v, want non-nil empty map", req.Headers)
	}
	if req.Query == nil || len(req.Query) != 0 {
		t.Fatalf("request Query = %#v, want non-nil empty map", req.Query)
	}
	if req.PathParams == nil || len(req.PathParams) != 0 {
		t.Fatalf("request PathParams = %#v, want non-nil empty map", req.PathParams)
	}
}

func assertHTTPResponseReset(t *testing.T, resp *HTTPResponse) {
	t.Helper()
	assertResetChecksCoverInventory(t, reflect.TypeOf(HTTPResponse{}), []string{
		"StatusCode",
		"Headers",
		"Body",
	})
	if resp.StatusCode != 0 || resp.Body != nil {
		t.Fatalf("response kept scalar residue: status=%d body=%q", resp.StatusCode, string(resp.Body))
	}
	if resp.Headers == nil || len(resp.Headers) != 0 {
		t.Fatalf("response Headers = %#v, want non-nil empty map", resp.Headers)
	}
}

func assertChatToResponsesStreamStateReset(t *testing.T, state *ChatToResponsesStreamState) {
	t.Helper()
	assertResetChecksCoverInventory(t, reflect.TypeOf(ChatToResponsesStreamState{}), []string{
		"ToolArgumentBuffers",
		"ItemIDs",
		"ToolCallNames",
		"ToolCallIndexToID",
		"MessageID",
		"Model",
		"CreatedAt",
		"HasEmittedCreated",
		"HasEmittedInProgress",
		"TextItemAdded",
		"TextItemClosed",
		"TextItemHasContent",
		"TextBuffer",
		"CurrentOutputIndex",
		"ToolCallOutputIndices",
		"SequenceNumber",
	})
	if len(state.ToolArgumentBuffers) != 0 || len(state.ItemIDs) != 0 ||
		len(state.ToolCallNames) != 0 || len(state.ToolCallIndexToID) != 0 ||
		len(state.ToolCallOutputIndices) != 0 {
		t.Fatalf("stream state kept map residue: %#v", state)
	}
	if state.MessageID != nil || state.Model != nil {
		t.Fatalf("stream state kept pointer residue: message=%v model=%v", state.MessageID, state.Model)
	}
	if state.CreatedAt <= 0 {
		t.Fatalf("stream state CreatedAt = %d, want refreshed positive timestamp", state.CreatedAt)
	}
	if state.HasEmittedCreated || state.HasEmittedInProgress ||
		state.TextItemAdded || state.TextItemClosed || state.TextItemHasContent {
		t.Fatalf("stream state kept boolean residue: %#v", state)
	}
	if state.TextBuffer.Len() != 0 || state.TextBuffer.String() != "" {
		t.Fatalf("stream state kept text buffer residue: %q", state.TextBuffer.String())
	}
	if state.CurrentOutputIndex != 0 || state.SequenceNumber != 0 {
		t.Fatalf("stream state kept counter residue: output=%d sequence=%d", state.CurrentOutputIndex, state.SequenceNumber)
	}
}

func assertPluginLogStoreReset(t *testing.T, store *pluginLogStore) {
	t.Helper()
	assertResetChecksCoverInventory(t, reflect.TypeOf(pluginLogStore{}), []string{
		"mu",
		"logs",
	})
	store.mu.Lock()
	defer store.mu.Unlock()
	if len(store.logs) != 0 {
		t.Fatalf("plugin log store kept log residue: %#v", store.logs)
	}
}

func TestReleaseHTTPRequestRestoresReusableMapFields(t *testing.T) {
	req := AcquireHTTPRequest()
	req.Method = "POST"
	req.Path = "/tenant-a"
	req.Headers["Authorization"] = "Bearer tenant-a"
	req.Query["api_key"] = "tenant-a-query"
	req.PathParams["tenant"] = "tenant-a"
	req.Body = []byte("tenant-a-body")

	req.Headers = nil
	req.Query = nil
	req.PathParams = nil

	ReleaseHTTPRequest(req)
	reacquired := AcquireHTTPRequest()
	assertHTTPRequestReset(t, reacquired)
	ReleaseHTTPRequest(reacquired)
}

func TestReleaseHTTPResponseRestoresReusableHeaderMap(t *testing.T) {
	resp := AcquireHTTPResponse()
	resp.StatusCode = 403
	resp.Headers["X-Tenant"] = "tenant-a"
	resp.Body = []byte("tenant-a-body")

	resp.Headers = nil

	ReleaseHTTPResponse(resp)
	reacquired := AcquireHTTPResponse()
	assertHTTPResponseReset(t, reacquired)
	ReleaseHTTPResponse(reacquired)
}

func TestReleaseChatToResponsesStreamStateClearsSensitiveFields(t *testing.T) {
	state := AcquireChatToResponsesStreamState()
	fillChatToResponsesStreamState(state, "tenant-a")

	ReleaseChatToResponsesStreamState(state)
	reacquired := AcquireChatToResponsesStreamState()
	assertChatToResponsesStreamStateReset(t, reacquired)
	ReleaseChatToResponsesStreamState(reacquired)
}

func TestDrainPluginLogsDoesNotExposePreviousTenantToNextContext(t *testing.T) {
	rootA := NewBifrostContext(context.Background(), NoDeadline)
	pluginA := "tenant-a-plugin"
	scopedA := rootA.WithPluginScope(&pluginA)
	scopedA.Log(LogLevelInfo, "tenant-a-secret")
	scopedA.ReleasePluginScope()

	logsA := rootA.DrainPluginLogs()
	if len(logsA) != 1 || logsA[0].PluginName != pluginA || logsA[0].Message != "tenant-a-secret" {
		t.Fatalf("tenant A drain returned unexpected logs: %#v", logsA)
	}

	rootB := NewBifrostContext(context.Background(), NoDeadline)
	pluginB := "tenant-b-plugin"
	scopedB := rootB.WithPluginScope(&pluginB)
	if logs := rootB.GetPluginLogs(); logs != nil {
		t.Fatalf("new context observed previous tenant plugin logs before logging: %#v", logs)
	}
	scopedB.ReleasePluginScope()

	store := rootB.pluginLogs.Load()
	if store == nil {
		t.Fatal("expected rootB to have initialized a plugin log store")
	}
	assertPluginLogStoreReset(t, store)
	if logs := rootB.DrainPluginLogs(); logs != nil {
		t.Fatalf("tenant B drain returned unexpected logs: %#v", logs)
	}
}

func TestPooledObjectsRandomizedReleasedReuseAndInterruptedLifecyclesDoNotExposeResidue(t *testing.T) {
	rng := rand.New(rand.NewSource(1005))
	var interruptedRequests []*HTTPRequest
	var interruptedResponses []*HTTPResponse
	var interruptedStates []*ChatToResponsesStreamState
	retainedRequests := make(map[*HTTPRequest]string)
	retainedResponses := make(map[*HTTPResponse]string)
	retainedStates := make(map[*ChatToResponsesStreamState]string)

	defer func() {
		for _, req := range interruptedRequests {
			ReleaseHTTPRequest(req)
		}
		for _, resp := range interruptedResponses {
			ReleaseHTTPResponse(resp)
		}
		for _, state := range interruptedStates {
			ReleaseChatToResponsesStreamState(state)
		}
	}()

	for i := 0; i < 500; i++ {
		tenant := fmt.Sprintf("tenant-%03d", i)

		req := AcquireHTTPRequest()
		if owner, retained := retainedRequests[req]; retained {
			t.Fatalf("acquired request retained by interrupted lifecycle for %s without release", owner)
		}
		assertHTTPRequestReset(t, req)
		fillHTTPRequest(req, tenant)
		if rng.Intn(5) == 0 {
			interruptedRequests = append(interruptedRequests, req)
			retainedRequests[req] = tenant
		} else {
			if rng.Intn(7) == 0 {
				req.Headers = nil
				req.Query = nil
				req.PathParams = nil
			}
			ReleaseHTTPRequest(req)
		}

		resp := AcquireHTTPResponse()
		if owner, retained := retainedResponses[resp]; retained {
			t.Fatalf("acquired response retained by interrupted lifecycle for %s without release", owner)
		}
		assertHTTPResponseReset(t, resp)
		fillHTTPResponse(resp, tenant)
		if rng.Intn(5) == 0 {
			interruptedResponses = append(interruptedResponses, resp)
			retainedResponses[resp] = tenant
		} else {
			if rng.Intn(7) == 0 {
				resp.Headers = nil
			}
			ReleaseHTTPResponse(resp)
		}

		state := AcquireChatToResponsesStreamState()
		if owner, retained := retainedStates[state]; retained {
			t.Fatalf("acquired stream state retained by interrupted lifecycle for %s without release", owner)
		}
		assertChatToResponsesStreamStateReset(t, state)
		fillChatToResponsesStreamState(state, tenant)
		if rng.Intn(5) == 0 {
			interruptedStates = append(interruptedStates, state)
			retainedStates[state] = tenant
		} else {
			if rng.Intn(7) == 0 {
				state.ToolArgumentBuffers = nil
				state.ItemIDs = nil
				state.ToolCallNames = nil
				state.ToolCallIndexToID = nil
				state.ToolCallOutputIndices = nil
			}
			ReleaseChatToResponsesStreamState(state)
		}
	}

	if len(interruptedRequests) == 0 || len(interruptedResponses) == 0 || len(interruptedStates) == 0 {
		t.Fatalf("randomized lifecycle did not exercise interrupted objects: req=%d resp=%d state=%d", len(interruptedRequests), len(interruptedResponses), len(interruptedStates))
	}

	for _, req := range interruptedRequests {
		delete(retainedRequests, req)
		ReleaseHTTPRequest(req)
	}
	interruptedRequests = nil

	for _, resp := range interruptedResponses {
		delete(retainedResponses, resp)
		ReleaseHTTPResponse(resp)
	}
	interruptedResponses = nil

	for _, state := range interruptedStates {
		delete(retainedStates, state)
		ReleaseChatToResponsesStreamState(state)
	}
	interruptedStates = nil
	if len(retainedRequests) != 0 || len(retainedResponses) != 0 || len(retainedStates) != 0 {
		t.Fatalf("interrupted object cleanup left retained identities: req=%d resp=%d state=%d", len(retainedRequests), len(retainedResponses), len(retainedStates))
	}

	for i := 0; i < 100; i++ {
		tenant := fmt.Sprintf("post-cleanup-tenant-%03d", i)

		req := AcquireHTTPRequest()
		assertHTTPRequestReset(t, req)
		fillHTTPRequest(req, tenant)
		ReleaseHTTPRequest(req)
		reacquiredReq := AcquireHTTPRequest()
		assertHTTPRequestReset(t, reacquiredReq)
		ReleaseHTTPRequest(reacquiredReq)

		resp := AcquireHTTPResponse()
		assertHTTPResponseReset(t, resp)
		fillHTTPResponse(resp, tenant)
		ReleaseHTTPResponse(resp)
		reacquiredResp := AcquireHTTPResponse()
		assertHTTPResponseReset(t, reacquiredResp)
		ReleaseHTTPResponse(reacquiredResp)

		state := AcquireChatToResponsesStreamState()
		assertChatToResponsesStreamStateReset(t, state)
		fillChatToResponsesStreamState(state, tenant)
		ReleaseChatToResponsesStreamState(state)
		reacquiredState := AcquireChatToResponsesStreamState()
		assertChatToResponsesStreamStateReset(t, reacquiredState)
		ReleaseChatToResponsesStreamState(reacquiredState)
	}
}

func fillHTTPRequest(req *HTTPRequest, tenant string) {
	req.Method = "POST"
	req.Path = "/" + tenant
	req.Headers["Authorization"] = "Bearer " + tenant
	req.Query["api_key"] = tenant + "-query"
	req.PathParams["tenant"] = tenant
	req.Body = []byte(tenant + "-body")
}

func fillHTTPResponse(resp *HTTPResponse, tenant string) {
	resp.StatusCode = 403
	resp.Headers["X-Tenant"] = tenant
	resp.Body = []byte(tenant + "-response")
}

func fillChatToResponsesStreamState(state *ChatToResponsesStreamState, tenant string) {
	messageID := tenant + "-message-id"
	model := tenant + "-model"
	state.ToolArgumentBuffers["call"] = `{"secret":"` + tenant + `"}`
	state.ItemIDs["call"] = tenant + "-item"
	state.ToolCallNames["call"] = tenant + "-tool"
	state.ToolCallIndexToID[7] = tenant + "-call"
	state.MessageID = &messageID
	state.Model = &model
	state.CreatedAt = -1
	state.HasEmittedCreated = true
	state.HasEmittedInProgress = true
	state.TextItemAdded = true
	state.TextItemClosed = true
	state.TextItemHasContent = true
	state.TextBuffer.WriteString(tenant + "-text")
	state.CurrentOutputIndex = 42
	state.ToolCallOutputIndices["call"] = 9
	state.SequenceNumber = 99
}
