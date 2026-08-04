package handlers

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/fasthttp/router"
	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
	"github.com/maximhq/bifrost/framework/modelcatalog/inbound"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

const (
	maxA2ATaskBodyBytes = 128 * 1024
	maxA2ATasks         = 512
	maxA2ATaskTTL       = 1 * time.Hour
)

type InboundA2AHandler struct {
	client *bifrost.Bifrost
	config *lib.Config

	mu    sync.Mutex
	tasks map[string]storedA2ATask
}

type storedA2ATask struct {
	Task      a2aTask
	ExpiresAt time.Time
}

func NewInboundA2AHandler(client *bifrost.Bifrost, config *lib.Config) *InboundA2AHandler {
	return &InboundA2AHandler{client: client, config: config, tasks: make(map[string]storedA2ATask)}
}

func (h *InboundA2AHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	// Discovery is intentionally public; task submission and retrieval use the
	// normal gateway middleware chain for identity, governance, audit, and kill
	// switches. A publisher card never grants authority to the caller.
	r.GET(a2adiscovery.WellKnownAgentCardPath, h.agentCard)
	r.GET(a2adiscovery.LegacyAgentCardPath, h.agentCard)
	a2aMiddlewares := append([]schemas.BifrostHTTPMiddleware{a2aChatRequestTypeMiddleware}, middlewares...)
	r.POST("/a2a", lib.ChainMiddlewares(h.messageSend, a2aMiddlewares...))
	r.POST("/a2a/jsonrpc", lib.ChainMiddlewares(h.messageSend, a2aMiddlewares...))
	r.GET("/a2a/tasks/{task_id}", lib.ChainMiddlewares(h.taskGet, middlewares...))
}

func a2aChatRequestTypeMiddleware(next fasthttp.RequestHandler) fasthttp.RequestHandler {
	return func(ctx *fasthttp.RequestCtx) {
		ctx.SetUserValue(schemas.BifrostContextKeyHTTPRequestType, schemas.ChatCompletionRequest)
		next(ctx)
	}
}

func (h *InboundA2AHandler) agentCard(ctx *fasthttp.RequestCtx) {
	base := inboundBaseURL(ctx)
	if base == "" {
		SendError(ctx, fasthttp.StatusBadRequest, "a2a public host is unavailable")
		return
	}
	record := defaultInboundRecord(base)
	body, err := inbound.MarshalAgentCardJSON(record)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, fmt.Sprintf("generate agent card: %v", err))
		return
	}
	hash := sha256.Sum256(body)
	etag := `"` + hex.EncodeToString(hash[:]) + `"`
	ctx.Response.Header.Set("ETag", etag)
	ctx.Response.Header.Set("Cache-Control", "public, max-age=60, must-revalidate")
	if string(ctx.Request.Header.Peek("If-None-Match")) == etag {
		ctx.SetStatusCode(fasthttp.StatusNotModified)
		return
	}
	ctx.SetContentType("application/json")
	ctx.SetBody(body)
}

type a2aJSONRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
}

type a2aMessage struct {
	MessageID string      `json:"messageId"`
	Role      string      `json:"role"`
	Parts     []a2aPart   `json:"parts"`
	Metadata  interface{} `json:"metadata,omitempty"`
}

type a2aPart struct {
	Kind string `json:"kind"`
	Text string `json:"text,omitempty"`
}

type a2aSendParams struct {
	Message       a2aMessage `json:"message"`
	Configuration struct {
		Provider string `json:"provider,omitempty"`
		Model    string `json:"model,omitempty"`
	} `json:"configuration,omitempty"`
}

type a2aTask struct {
	ID        string        `json:"id"`
	ContextID string        `json:"contextId,omitempty"`
	Status    a2aTaskStatus `json:"status"`
	History   []a2aMessage  `json:"history,omitempty"`
	Artifacts []a2aArtifact `json:"artifacts,omitempty"`
}

type a2aTaskStatus struct {
	State     string      `json:"state"`
	Timestamp time.Time   `json:"timestamp"`
	Message   *a2aMessage `json:"message,omitempty"`
}

type a2aArtifact struct {
	Name  string    `json:"name,omitempty"`
	Parts []a2aPart `json:"parts"`
}

type a2aJSONRPCResponse struct {
	JSONRPC string           `json:"jsonrpc"`
	ID      json.RawMessage  `json:"id"`
	Result  interface{}      `json:"result,omitempty"`
	Error   *a2aJSONRPCError `json:"error,omitempty"`
}

type a2aJSONRPCError struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

func (h *InboundA2AHandler) messageSend(ctx *fasthttp.RequestCtx) {
	if len(ctx.PostBody()) > maxA2ATaskBodyBytes {
		h.writeRPCError(ctx, nil, -32600, "request body exceeds A2A limit")
		return
	}
	var request a2aJSONRPCRequest
	if err := json.Unmarshal(ctx.PostBody(), &request); err != nil || request.JSONRPC != "2.0" {
		h.writeRPCError(ctx, request.ID, -32600, "invalid JSON-RPC request")
		return
	}
	if request.Method != "message/send" {
		h.writeRPCError(ctx, request.ID, -32601, "only message/send is supported")
		return
	}
	var params a2aSendParams
	if err := json.Unmarshal(request.Params, &params); err != nil || strings.TrimSpace(params.Message.MessageID) == "" {
		h.writeRPCError(ctx, request.ID, -32602, "params.message.messageId is required")
		return
	}
	text := a2aMessageText(params.Message)
	if text == "" || len(text) > maxA2ATaskBodyBytes {
		h.writeRPCError(ctx, request.ID, -32602, "message must contain bounded text content")
		return
	}
	taskID := boundedTaskID(params.Message.MessageID)
	if existing, ok := h.loadTask(taskID); ok {
		h.writeRPCResult(ctx, request.ID, existing)
		return
	}
	if h.client == nil || h.config == nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A execution is unavailable")
		return
	}
	bifrostCtx, cancel := lib.ConvertToBifrostContext(ctx, h.config)
	if bifrostCtx == nil {
		h.writeRPCError(ctx, request.ID, -32000, "failed to establish gateway request context")
		return
	}
	defer cancel()
	requestInput := &schemas.BifrostChatRequest{
		Provider: schemas.ModelProvider(params.Configuration.Provider),
		Model:    strings.TrimSpace(params.Configuration.Model),
		Input:    []schemas.ChatMessage{{Role: schemas.ChatMessageRoleUser, Content: &schemas.ChatMessageContent{ContentStr: &text}}},
	}
	if requestInput.Model == "" {
		h.writeRPCError(ctx, request.ID, -32602, "params.configuration.model is required")
		return
	}
	response, bifrostErr := h.client.ChatCompletionRequest(bifrostCtx, requestInput)
	if bifrostErr != nil {
		h.writeRPCError(ctx, request.ID, -32000, bifrost.GetErrorMessage(bifrostErr))
		return
	}
	answer := chatResponseText(response)
	if answer == "" {
		h.writeRPCError(ctx, request.ID, -32000, "model returned no text content")
		return
	}
	output := a2aMessage{MessageID: taskID + "-result", Role: "agent", Parts: []a2aPart{{Kind: "text", Text: answer}}}
	task := a2aTask{ID: taskID, ContextID: params.Message.MessageID, History: []a2aMessage{params.Message, output}, Artifacts: []a2aArtifact{{Name: "response", Parts: output.Parts}}, Status: a2aTaskStatus{State: "completed", Timestamp: time.Now().UTC(), Message: &output}}
	h.storeTask(task)
	h.writeRPCResult(ctx, request.ID, task)
}

func (h *InboundA2AHandler) taskGet(ctx *fasthttp.RequestCtx) {
	taskID := strings.TrimSpace(string(ctx.UserValue("task_id")))
	if taskID == "" {
		h.writeRPCError(ctx, nil, -32602, "task_id is required")
		return
	}
	task, ok := h.loadTask(taskID)
	if !ok {
		SendError(ctx, fasthttp.StatusNotFound, "A2A task not found")
		return
	}
	ctx.SetContentType("application/json")
	ctx.SetBody(mustJSON(task))
}

func (h *InboundA2AHandler) storeTask(task a2aTask) {
	h.mu.Lock()
	defer h.mu.Unlock()
	now := time.Now()
	for id, stored := range h.tasks {
		if stored.ExpiresAt.Before(now) {
			delete(h.tasks, id)
		}
	}
	if len(h.tasks) >= maxA2ATasks {
		var oldestID string
		var oldest time.Time
		for id, stored := range h.tasks {
			if oldestID == "" || stored.ExpiresAt.Before(oldest) {
				oldestID, oldest = id, stored.ExpiresAt
			}
		}
		delete(h.tasks, oldestID)
	}
	h.tasks[task.ID] = storedA2ATask{Task: task, ExpiresAt: now.Add(maxA2ATaskTTL)}
}

func (h *InboundA2AHandler) loadTask(id string) (a2aTask, bool) {
	h.mu.Lock()
	defer h.mu.Unlock()
	stored, ok := h.tasks[id]
	if !ok || stored.ExpiresAt.Before(time.Now()) {
		if ok {
			delete(h.tasks, id)
		}
		return a2aTask{}, false
	}
	return stored.Task, true
}

func (h *InboundA2AHandler) writeRPCResult(ctx *fasthttp.RequestCtx, id json.RawMessage, result interface{}) {
	h.writeRPC(ctx, a2aJSONRPCResponse{JSONRPC: "2.0", ID: id, Result: result})
}

func (h *InboundA2AHandler) writeRPCError(ctx *fasthttp.RequestCtx, id json.RawMessage, code int, message string) {
	h.writeRPC(ctx, a2aJSONRPCResponse{JSONRPC: "2.0", ID: id, Error: &a2aJSONRPCError{Code: code, Message: message}})
}

func (h *InboundA2AHandler) writeRPC(ctx *fasthttp.RequestCtx, response a2aJSONRPCResponse) {
	ctx.SetContentType("application/json")
	ctx.SetBody(mustJSON(response))
}

func a2aMessageText(message a2aMessage) string {
	var parts []string
	for _, part := range message.Parts {
		if part.Kind == "text" && strings.TrimSpace(part.Text) != "" {
			parts = append(parts, strings.TrimSpace(part.Text))
		}
	}
	return strings.Join(parts, "\n")
}

func chatResponseText(response *schemas.BifrostChatResponse) string {
	if response == nil || len(response.Choices) == 0 || response.Choices[0].ChatNonStreamResponseChoice == nil || response.Choices[0].ChatNonStreamResponseChoice.Message == nil {
		return ""
	}
	message := response.Choices[0].ChatNonStreamResponseChoice.Message
	if message.Content == nil || message.Content.ContentStr == nil {
		return ""
	}
	return strings.TrimSpace(*message.Content.ContentStr)
}

func boundedTaskID(messageID string) string {
	messageID = strings.TrimSpace(messageID)
	if len(messageID) <= 128 {
		return messageID
	}
	sum := sha256.Sum256([]byte(messageID))
	return "task-" + hex.EncodeToString(sum[:])
}

func inboundBaseURL(ctx *fasthttp.RequestCtx) string {
	host := strings.TrimSpace(string(ctx.Request.Header.Peek("X-Forwarded-Host")))
	if host == "" || !validForwardedHost(host) {
		host = strings.TrimSpace(string(ctx.Host()))
	}
	if host == "" || !validForwardedHost(host) {
		return ""
	}
	scheme := strings.TrimSpace(string(ctx.Request.Header.Peek("X-Forwarded-Proto")))
	if scheme == "" && ctx.IsTLS() {
		scheme = "https"
	}
	if scheme != "https" {
		// Agent Cards are published as HTTPS interfaces. TLS termination may set
		// X-Forwarded-Proto; a plain local listener must be fronted by TLS.
		return ""
	}
	return "https://" + host
}

func defaultInboundRecord(base string) inbound.Record {
	return inbound.Record{Card: inbound.CardRecord{
		Name: "FrankenGate Agent Gateway", Description: "Governed A2A access to FrankenGate agent workflows.", Version: "1", Interfaces: []inbound.InterfaceRecord{{URL: base + "/a2a", Transport: a2adiscovery.TransportJSONRPC}}, Capabilities: a2adiscovery.AgentCapabilities{Streaming: false, StateTransitionHistory: true}, DefaultInputModes: []string{"text"}, DefaultOutputModes: []string{"text"}, SecuritySchemes: []inbound.SecuritySchemeRecord{{ID: "bearer", Scheme: a2adiscovery.SecurityScheme{Type: "http", Scheme: "bearer", BearerFormat: "JWT"}}}, Security: []inbound.SecurityRequirementRecord{{Schemes: []inbound.SecurityRequirementScheme{{ID: "bearer", Scopes: []string{"a2a:invoke"}}}}}, SupportsAuthenticatedExtendedCard: true,
	}, Workflows: []inbound.WorkflowRecord{{ID: "gateway-chat", Name: "Governed chat", Description: "Routes an authenticated A2A message through the normal FrankenGate policy pipeline.", InputModes: []string{"text"}, OutputModes: []string{"text"}}}}
}

func mustJSON(value interface{}) []byte {
	body, _ := json.Marshal(value)
	return body
}
