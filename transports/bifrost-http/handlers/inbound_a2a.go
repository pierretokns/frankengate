package handlers

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/fasthttp/router"
	"github.com/google/uuid"
	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2apush"
	"github.com/maximhq/bifrost/framework/modelcatalog/inbound"
	"github.com/maximhq/bifrost/framework/modelcatalog/provenance"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

const (
	maxA2ATaskBodyBytes = 128 * 1024
	maxA2ATasks         = 512
	maxA2ATaskTTL       = 1 * time.Hour
	maxA2AStreamEvents  = 128
	maxA2AStreamJournal = 512 * 1024
	a2aTaskObjectPrefix = "frankengate/a2a/tasks/"
	a2aTaskStoreTimeout = 2 * time.Second
)

type InboundA2AHandler struct {
	client *bifrost.Bifrost
	config *lib.Config

	mu             sync.Mutex
	tasks          map[string]storedA2ATask
	now            func() time.Time
	authorityStore configstore.PrincipalAuthorizationEpochStore

	pushStore    a2apush.Store
	pushPolicy   a2apush.Policy
	pushDelivery a2apush.Delivery
	pushRuntime  *a2apush.Runtime
	streamMu     sync.Mutex
	streamStates map[string]*a2aStreamState
}

type storedA2ATask struct {
	Task      a2aTask
	ExpiresAt time.Time
}

type durableA2ATaskEnvelope struct {
	Task      a2aTask `json:"task"`
	ExpiresAt string  `json:"expires_at"`
}

type a2aStreamEvent struct {
	ID   string `json:"id"`
	Body []byte `json:"body"`
}

type durableA2AStreamEnvelope struct {
	Next     int              `json:"next"`
	Events   []a2aStreamEvent `json:"events"`
	Terminal bool             `json:"terminal"`
}

type a2aStreamState struct {
	next        int
	events      []a2aStreamEvent
	subscribers map[chan a2aStreamEvent]struct{}
	terminal    bool
	active      bool
}

func NewInboundA2AHandler(client *bifrost.Bifrost, config *lib.Config) *InboundA2AHandler {
	var authorityStore configstore.PrincipalAuthorizationEpochStore
	if config != nil && config.ConfigStore != nil {
		authorityStore, _ = config.ConfigStore.(configstore.PrincipalAuthorizationEpochStore)
	}
	return &InboundA2AHandler{client: client, config: config, tasks: make(map[string]storedA2ATask), streamStates: make(map[string]*a2aStreamState), now: time.Now, authorityStore: authorityStore}
}

// ConfigurePushNotifications installs the durable configuration store and an
// operator-approved delivery implementation. Push operations remain disabled
// until both are present; configuration alone never causes task payload
// egress or Agent Card capability advertisement.
func (h *InboundA2AHandler) ConfigurePushNotifications(store a2apush.Store, policy a2apush.Policy, delivery a2apush.Delivery) {
	if h == nil {
		return
	}
	policy.RequireDNSResolution = true
	h.pushStore = store
	h.pushPolicy = policy
	h.pushDelivery = delivery
	var outbox a2apush.OutboxStore
	var payloads a2apush.PayloadWriter
	if h.config != nil && h.config.ObjectStore != nil {
		outbox = a2apush.NewDurableOutboxStore(h.config.ObjectStore, "frankengate/a2a/push/outbox", h.now)
		payloads = a2apush.NewDurablePayloadStore(h.config.ObjectStore, "frankengate/a2a/push/payloads")
	} else {
		outbox = a2apush.NewMemoryOutboxStore(h.now)
		payloads = a2apush.NewMemoryPayloadStore()
	}
	h.pushRuntime = a2apush.NewRuntime(store, outbox, payloads, delivery, policy)
}

// StartPushRuntime starts the durable outbox poller after routes and readiness
// have been installed. Construction alone never creates a background worker.
func (h *InboundA2AHandler) StartPushRuntime(ctx context.Context) {
	if h != nil && h.pushRuntime != nil && h.pushDelivery != nil {
		h.pushRuntime.Start(ctx)
	}
}

func (h *InboundA2AHandler) StopPushRuntime() {
	if h != nil && h.pushRuntime != nil {
		h.pushRuntime.Stop()
	}
}

// SetPushObserver attaches a low-cardinality metrics/audit projection to the
// already configured runtime. It never receives payloads or credentials.
func (h *InboundA2AHandler) SetPushObserver(observer a2apush.Observer) {
	if h != nil && h.pushRuntime != nil {
		h.pushRuntime.SetObserver(observer)
	}
}

func (h *InboundA2AHandler) PushHealth() a2apush.RuntimeHealth {
	if h == nil || h.pushRuntime == nil {
		return a2apush.RuntimeHealth{}
	}
	return h.pushRuntime.Health()
}

func (h *InboundA2AHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	// Discovery is intentionally public; task submission and retrieval use the
	// normal gateway middleware chain for identity, governance, audit, and kill
	// switches. A publisher card never grants authority to the caller.
	r.GET(a2adiscovery.WellKnownAgentCardPath, h.agentCard)
	r.GET(a2adiscovery.LegacyAgentCardPath, h.agentCard)
	a2aMiddlewares := append([]schemas.BifrostHTTPMiddleware{a2aChatRequestTypeMiddleware}, middlewares...)
	// A2A JSON-RPC clients POST to the interface URL itself. Registering the
	// root binding avoids router-added slash redirects that clients do not have
	// to follow for a JSON-RPC transport.
	r.POST("/", lib.ChainMiddlewares(h.messageSend, a2aMiddlewares...))
	r.POST("/a2a", lib.ChainMiddlewares(h.messageSend, a2aMiddlewares...))
	r.POST("/a2a/jsonrpc", lib.ChainMiddlewares(h.messageSend, a2aMiddlewares...))
	r.POST("/a2a/stream", lib.ChainMiddlewares(h.messageStream, a2aMiddlewares...))
	// Standard HTTP+JSON aliases. JSON-RPC remains the canonical gateway
	// surface, while these routes make the same task/auth semantics usable by
	// REST clients and SDKs that select the HTTP+JSON interface from a card.
	r.POST("/message:send", lib.ChainMiddlewares(h.restMessageSend, a2aMiddlewares...))
	r.POST("/message:stream", lib.ChainMiddlewares(h.restMessageStream, a2aMiddlewares...))
	r.GET("/a2a/tasks/{task_id}", lib.ChainMiddlewares(h.taskGet, middlewares...))
	r.GET("/tasks/{task_id}", lib.ChainMiddlewares(h.taskGet, middlewares...))
	r.GET("/tasks", lib.ChainMiddlewares(h.restListTasks, middlewares...))
	// fasthttp/router treats a parameter followed by a colon suffix as a
	// wildcard regex. Registering both :cancel and :subscribe independently
	// therefore panics during server startup. Capture the whole segment once
	// and dispatch the standards-defined colon action in restTaskAction.
	r.POST("/tasks/{task_id}", lib.ChainMiddlewares(h.restTaskAction, middlewares...))
	r.POST("/tasks/{task_id}/pushNotificationConfigs", lib.ChainMiddlewares(h.restCreatePushNotificationConfig, middlewares...))
	r.GET("/tasks/{task_id}/pushNotificationConfigs", lib.ChainMiddlewares(h.restListPushNotificationConfigs, middlewares...))
	r.GET("/tasks/{task_id}/pushNotificationConfigs/{config_id}", lib.ChainMiddlewares(h.restGetPushNotificationConfig, middlewares...))
	r.DELETE("/tasks/{task_id}/pushNotificationConfigs/{config_id}", lib.ChainMiddlewares(h.restDeletePushNotificationConfig, middlewares...))
	r.GET("/extendedAgentCard", lib.ChainMiddlewares(h.extendedAgentCardHTTP, middlewares...))
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
	record := h.agentCardRecord(base)
	body, err := inbound.MarshalAgentCardJSON(record)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, fmt.Sprintf("generate agent card: %v", err))
		return
	}
	hash := sha256.Sum256(body)
	etag := `"` + hex.EncodeToString(hash[:]) + `"`
	ctx.Response.Header.Set("ETag", etag)
	ctx.Response.Header.Set("Last-Modified", time.Now().UTC().Format(http.TimeFormat))
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
	Kind      string `json:"kind,omitempty"`
	Text      string `json:"text,omitempty"`
	MediaType string `json:"mediaType,omitempty"`
}

type a2aSendParams struct {
	Message       a2aMessage `json:"message"`
	Configuration struct {
		Provider string `json:"provider,omitempty"`
		Model    string `json:"model,omitempty"`
	} `json:"configuration,omitempty"`
}

type a2aTaskParams struct {
	ID            string `json:"id"`
	HistoryLength int    `json:"historyLength,omitempty"`
}

type a2aListTasksParams struct {
	ContextID        string `json:"contextId,omitempty"`
	Status           string `json:"status,omitempty"`
	PageSize         int    `json:"pageSize,omitempty"`
	PageToken        string `json:"pageToken,omitempty"`
	HistoryLength    int    `json:"historyLength,omitempty"`
	IncludeArtifacts bool   `json:"includeArtifacts,omitempty"`
}

type a2aListTasksResult struct {
	Tasks         []a2aTask `json:"tasks"`
	TotalSize     int       `json:"totalSize"`
	PageSize      int       `json:"pageSize"`
	NextPageToken string    `json:"nextPageToken"`
}

type a2aTask struct {
	ID        string        `json:"id"`
	ContextID string        `json:"contextId,omitempty"`
	Status    a2aTaskStatus `json:"status"`
	History   []a2aMessage  `json:"history,omitempty"`
	Artifacts []a2aArtifact `json:"artifacts,omitempty"`
}

type a2aSendResult struct {
	Task a2aTask `json:"task"`
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

type a2aPushAuthentication struct {
	Scheme           string `json:"scheme,omitempty"`
	Credentials      string `json:"credentials,omitempty"`
	CredentialRef    string `json:"credentialRef,omitempty"`
	SigningSecretRef string `json:"signingSecretRef,omitempty"`
}

type a2aPushNotificationConfig struct {
	ID             string          `json:"id,omitempty"`
	TaskID         string          `json:"taskId,omitempty"`
	URL            string          `json:"url"`
	Token          string          `json:"token,omitempty"`
	TokenRef       string          `json:"tokenRef,omitempty"`
	Authentication json.RawMessage `json:"authentication,omitempty"`
}

type a2aPushConfigRequest struct {
	ID                     string                     `json:"id,omitempty"`
	TaskID                 string                     `json:"taskId,omitempty"`
	URL                    string                     `json:"url,omitempty"`
	Token                  string                     `json:"token,omitempty"`
	TokenRef               string                     `json:"tokenRef,omitempty"`
	Authentication         json.RawMessage            `json:"authentication,omitempty"`
	PushNotificationConfig *a2aPushNotificationConfig `json:"pushNotificationConfig,omitempty"`
}

type a2aPushConfigResult struct {
	ID             string                 `json:"id"`
	TaskID         string                 `json:"taskId"`
	URL            string                 `json:"url"`
	Authentication *a2aPushAuthentication `json:"authentication,omitempty"`
}

type a2aPushConfigListResult struct {
	Configs []a2aPushConfigResult `json:"configs"`
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
	taskPartition, err := inboundA2ATaskPartition(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	switch request.Method {
	case "GetTask", "tasks/get":
		h.rpcGetTask(ctx, request)
		return
	case "ListTasks", "tasks/list":
		h.rpcListTasks(ctx, request)
		return
	case "CancelTask", "tasks/cancel":
		h.rpcCancelTask(ctx, request)
		return
	case "SubscribeToTask", "tasks/subscribe":
		h.rpcSubscribeTask(ctx, request)
		return
	case "CreateTaskPushNotificationConfig", "SetTaskPushNotificationConfig", "tasks/pushNotificationConfig/create", "tasks/pushNotificationConfig/set":
		h.rpcCreatePushNotificationConfig(ctx, request)
		return
	case "GetTaskPushNotificationConfig", "tasks/pushNotificationConfig/get":
		h.rpcGetPushNotificationConfig(ctx, request)
		return
	case "ListTaskPushNotificationConfigs", "tasks/pushNotificationConfig/list":
		h.rpcListPushNotificationConfigs(ctx, request)
		return
	case "DeleteTaskPushNotificationConfig", "tasks/pushNotificationConfig/delete":
		h.rpcDeletePushNotificationConfig(ctx, request)
		return
	case "GetExtendedAgentCard", "GetAuthenticatedExtendedCard":
		h.rpcGetExtendedAgentCard(ctx, request)
		return
	case "SendStreamingMessage", "message/stream":
		h.messageStream(ctx)
		return
	case "SendMessage", "message/send":
		// Both the released PascalCase binding and the older slash binding are
		// accepted during the A2A 1.0 migration window.
	default:
		h.writeRPCError(ctx, request.ID, -32601, "method is not supported")
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
	if err := h.validateInboundA2AAuthority(ctx, taskID); err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	if existing, ok, loadErr := h.loadTask(ctx, taskPartition, taskID); loadErr != nil {
		h.writeRPCError(ctx, request.ID, -32001, "A2A task registry is unavailable")
		return
	} else if ok {
		h.writeRPCResult(ctx, request.ID, a2aSendResult{Task: existing})
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
	attachInboundA2AProvenance(bifrostCtx, ctx, h.config, taskID, h.currentTime(), h.inboundAgentCardDigest(ctx))
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
	output := a2aMessage{MessageID: taskID + "-result", Role: a2aAgentRole(params.Message.Role), Parts: []a2aPart{{Text: answer}}}
	task := a2aTask{ID: taskID, ContextID: params.Message.MessageID, History: []a2aMessage{params.Message, output}, Artifacts: []a2aArtifact{{Name: "response", Parts: output.Parts}}, Status: a2aTaskStatus{State: "TASK_STATE_COMPLETED", Timestamp: h.currentTime().UTC(), Message: &output}}
	bifrostCtx.SetTraceAttribute("frankengate.provenance.outcome", "completed")
	bifrostCtx.SetTraceAttribute("frankengate.provenance.artifact_ref", "a2a://task/"+taskID+"/response")
	if err := h.storeTask(ctx, taskPartition, task); err != nil {
		h.writeRPCError(ctx, request.ID, -32001, "A2A task registry is unavailable")
		return
	}
	h.writeRPCResult(ctx, request.ID, a2aSendResult{Task: task})
}

type a2aStreamStatusUpdate struct {
	TaskID    string        `json:"taskId"`
	ContextID string        `json:"contextId,omitempty"`
	Status    a2aTaskStatus `json:"status"`
	Final     bool          `json:"final,omitempty"`
}

type a2aStreamArtifactUpdate struct {
	TaskID    string      `json:"taskId"`
	ContextID string      `json:"contextId,omitempty"`
	Artifact  a2aArtifact `json:"artifact"`
	Append    bool        `json:"append"`
	LastChunk bool        `json:"lastChunk"`
}

// messageStream is the A2A JSON-RPC and HTTP+JSON SSE binding. It forwards
// provider deltas as ordered A2A artifact events and persists terminal state;
// it does not materialize a unary response and label it as a stream.
func (h *InboundA2AHandler) messageStream(ctx *fasthttp.RequestCtx) {
	var request a2aJSONRPCRequest
	if err := json.Unmarshal(ctx.PostBody(), &request); err != nil {
		h.writeRPCError(ctx, nil, -32700, "Invalid JSON payload")
		return
	}
	if request.JSONRPC != "2.0" {
		h.writeRPCError(ctx, request.ID, -32600, "invalid JSON-RPC request")
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
	partition, err := inboundA2ATaskPartition(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	taskID := boundedTaskID(params.Message.MessageID)
	if err := h.validateInboundA2AAuthority(ctx, taskID); err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	if existing, ok, loadErr := h.loadTask(ctx, partition, taskID); loadErr != nil {
		h.writeRPCError(ctx, request.ID, -32001, "A2A task registry is unavailable")
		return
	} else if ok {
		h.streamExistingTask(ctx, request.ID, partition, existing)
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
	attachInboundA2AProvenance(bifrostCtx, ctx, h.config, taskID, h.currentTime(), h.inboundAgentCardDigest(ctx))
	requestInput := &schemas.BifrostChatRequest{
		Provider: schemas.ModelProvider(params.Configuration.Provider),
		Model:    strings.TrimSpace(params.Configuration.Model),
		Input:    []schemas.ChatMessage{{Role: schemas.ChatMessageRoleUser, Content: &schemas.ChatMessageContent{ContentStr: &text}}},
	}
	if requestInput.Model == "" {
		cancel()
		h.writeRPCError(ctx, request.ID, -32602, "params.configuration.model is required")
		return
	}
	stream, bifrostErr := h.client.ChatCompletionStreamRequest(bifrostCtx, requestInput)
	if bifrostErr != nil {
		cancel()
		h.writeRPCError(ctx, request.ID, -32000, bifrost.GetErrorMessage(bifrostErr))
		return
	}
	if stream == nil {
		cancel()
		h.writeRPCError(ctx, request.ID, -32000, "A2A stream is unavailable")
		return
	}
	submitted := a2aTask{ID: taskID, ContextID: params.Message.MessageID, History: []a2aMessage{params.Message}, Status: a2aTaskStatus{State: "TASK_STATE_SUBMITTED", Timestamp: h.currentTime().UTC()}}
	if err := h.storeTask(ctx, partition, submitted); err != nil {
		cancel()
		h.writeRPCError(ctx, request.ID, -32001, "A2A task registry is unavailable")
		return
	}
	h.markA2AStreamActive(scopedA2ATaskKey(partition, taskID))
	reader := lib.NewSSEStreamReader()
	ctx.SetContentType("text/event-stream")
	ctx.Response.Header.Set("Cache-Control", "no-cache")
	ctx.Response.Header.Set("Connection", "keep-alive")
	ctx.SetUserValue(schemas.BifrostContextKeyDeferTraceCompletion, true)
	ctx.Response.SetBodyStream(reader, -1)
	go h.produceA2AStream(reader, stream, cancel, partition, submitted, params.Message)
}

func (h *InboundA2AHandler) produceA2AStream(reader *lib.SSEStreamReader, stream chan *schemas.BifrostStreamChunk, cancel context.CancelFunc, partition string, task a2aTask, input a2aMessage) {
	streamKey := scopedA2ATaskKey(partition, task.ID)
	defer reader.Done()
	defer cancel()
	terminal := false
	defer func() {
		if terminal {
			h.finishA2AStream(streamKey)
		}
	}()
	send := func(event any, terminalEvent bool) bool {
		body, err := json.Marshal(event)
		if err != nil {
			return false
		}
		published := h.publishA2AStreamEvent(streamKey, body, terminalEvent)
		if persistErr := h.persistA2AStreamState(streamKey); persistErr != nil {
			return false
		}
		return reader.SendEventWithID(published.ID, "message", published.Body)
	}
	if !send(task, false) {
		go drainA2AStream(stream)
		return
	}
	working := task
	working.Status = a2aTaskStatus{State: "TASK_STATE_WORKING", Timestamp: h.currentTime().UTC(), Message: &a2aMessage{MessageID: task.ID + "-working", Role: "agent", Parts: []a2aPart{{MediaType: "text/plain", Text: "Working on the request."}}}}
	if err := h.persistDetachedA2ATask(partition, working); err != nil {
		terminal = true
		_ = send(a2aJSONRPCError{Code: -32001, Message: "A2A task registry is unavailable"}, true)
		go drainA2AStream(stream)
		return
	}
	if !send(a2aStreamStatusUpdate{TaskID: task.ID, ContextID: task.ContextID, Status: working.Status}, false) {
		go drainA2AStream(stream)
		return
	}
	task = working
	var answer strings.Builder
	var pending string
	emitArtifact := func(value string, last bool) bool {
		if value == "" && !last {
			return true
		}
		return send(a2aStreamArtifactUpdate{TaskID: task.ID, ContextID: task.ContextID, Artifact: a2aArtifact{Name: "response", Parts: []a2aPart{{MediaType: "text/plain", Text: value}}}, Append: true, LastChunk: last}, last)
	}
	for chunk := range stream {
		if chunk == nil {
			continue
		}
		if chunk.BifrostError != nil {
			terminal = true
			failed := task
			failed.Status = a2aTaskStatus{State: "TASK_STATE_FAILED", Timestamp: h.currentTime().UTC()}
			_ = h.persistDetachedA2ATask(partition, failed)
			_ = send(a2aJSONRPCError{Code: -32000, Message: bifrost.GetErrorMessage(chunk.BifrostError)}, true)
			return
		}
		delta := a2AStreamChunkText(chunk)
		if delta == "" {
			continue
		}
		if answer.Len()+len(delta) > maxA2ATaskBodyBytes {
			terminal = true
			_ = send(a2aJSONRPCError{Code: -32000, Message: "A2A stream output exceeds the task limit"}, true)
			go drainA2AStream(stream)
			return
		}
		answer.WriteString(delta)
		if pending != "" && !emitArtifact(pending, false) {
			go drainA2AStream(stream)
			return
		}
		pending = delta
	}
	if pending != "" && !emitArtifact(pending, true) {
		return
	}
	output := a2aMessage{MessageID: task.ID + "-result", Role: "agent", Parts: []a2aPart{{Text: strings.TrimSpace(answer.String())}}}
	task.History = append(task.History, output)
	task.Artifacts = []a2aArtifact{{Name: "response", Parts: output.Parts}}
	task.Status = a2aTaskStatus{State: "TASK_STATE_COMPLETED", Timestamp: h.currentTime().UTC(), Message: &output}
	if err := h.persistDetachedA2ATask(partition, task); err != nil {
		terminal = true
		_ = send(a2aJSONRPCError{Code: -32001, Message: "A2A task registry is unavailable"}, true)
		return
	}
	terminal = true
	_ = send(a2aStreamStatusUpdate{TaskID: task.ID, ContextID: task.ContextID, Status: task.Status, Final: true}, true)
}

func (h *InboundA2AHandler) streamExistingTask(ctx *fasthttp.RequestCtx, _ json.RawMessage, partition string, task a2aTask) {
	reader := lib.NewSSEStreamReader()
	ctx.SetContentType("text/event-stream")
	ctx.Response.Header.Set("Cache-Control", "no-cache")
	ctx.Response.Header.Set("Connection", "keep-alive")
	ctx.Response.SetBodyStream(reader, -1)
	after := 0
	if parsed, err := strconv.Atoi(strings.TrimSpace(string(ctx.Request.Header.Peek("Last-Event-ID")))); err == nil && parsed > 0 {
		after = parsed
	}
	streamKey := scopedA2ATaskKey(partition, task.ID)
	replay, subscriber, unsubscribe, terminal, active := h.subscribeA2AStream(ctx, streamKey, after)
	if subscriber == nil && !terminal && !active {
		task = h.recoverInterruptedA2AStream(ctx, partition, task)
		replay, subscriber, unsubscribe, terminal, _ = h.subscribeA2AStream(ctx, streamKey, after)
	}
	go func() {
		defer reader.Done()
		defer unsubscribe()
		if len(replay) == 0 && subscriber == nil {
			if body, err := json.Marshal(task); err == nil {
				_ = reader.SendEventWithID("1", "message", body)
			}
		}
		for _, event := range replay {
			if !reader.SendEventWithID(event.ID, "message", event.Body) {
				return
			}
		}
		if subscriber == nil || terminal {
			return
		}
		for {
			select {
			case <-reader.Closed():
				return
			case event, ok := <-subscriber:
				if !ok {
					return
				}
				if !reader.SendEventWithID(event.ID, "message", event.Body) {
					return
				}
			}
		}
	}()
}

func (h *InboundA2AHandler) publishA2AStreamEvent(taskID string, body []byte, terminal bool) a2aStreamEvent {
	h.streamMu.Lock()
	defer h.streamMu.Unlock()
	if h.streamStates == nil {
		h.streamStates = make(map[string]*a2aStreamState)
	}
	state := h.streamStates[taskID]
	if state == nil {
		state = &a2aStreamState{subscribers: make(map[chan a2aStreamEvent]struct{})}
		h.streamStates[taskID] = state
	}
	state.active = !terminal
	state.next++
	event := a2aStreamEvent{ID: strconv.Itoa(state.next), Body: append([]byte(nil), body...)}
	state.events = append(state.events, event)
	if len(state.events) > maxA2AStreamEvents {
		state.events = state.events[len(state.events)-maxA2AStreamEvents:]
	}
	for totalStreamEventBytes(state.events) > maxA2AStreamJournal && len(state.events) > 1 {
		state.events = state.events[1:]
	}
	if terminal {
		state.terminal = true
	}
	for subscriber := range state.subscribers {
		select {
		case subscriber <- event:
		default:
			close(subscriber)
			delete(state.subscribers, subscriber)
		}
	}
	return event
}

func (h *InboundA2AHandler) subscribeA2AStream(ctx context.Context, taskID string, after int) ([]a2aStreamEvent, <-chan a2aStreamEvent, func(), bool, bool) {
	h.loadDurableA2AStreamState(ctx, taskID)
	h.streamMu.Lock()
	defer h.streamMu.Unlock()
	if h.streamStates == nil {
		h.streamStates = make(map[string]*a2aStreamState)
	}
	state := h.streamStates[taskID]
	if state == nil {
		return nil, nil, func() {}, false, false
	}
	replay := make([]a2aStreamEvent, 0, len(state.events))
	for _, event := range state.events {
		id, _ := strconv.Atoi(event.ID)
		if id > after {
			replay = append(replay, a2aStreamEvent{ID: event.ID, Body: append([]byte(nil), event.Body...)})
		}
	}
	if state.terminal {
		return replay, nil, func() {}, true, false
	}
	active := state.active
	subscriber := make(chan a2aStreamEvent, 16)
	state.subscribers[subscriber] = struct{}{}
	return replay, subscriber, func() {
		h.streamMu.Lock()
		if _, ok := state.subscribers[subscriber]; ok {
			delete(state.subscribers, subscriber)
			close(subscriber)
		}
		h.streamMu.Unlock()
	}, false, active
}

func (h *InboundA2AHandler) finishA2AStream(taskID string) {
	h.streamMu.Lock()
	if state := h.streamStates[taskID]; state != nil {
		state.terminal = true
		state.active = false
		for subscriber := range state.subscribers {
			close(subscriber)
			delete(state.subscribers, subscriber)
		}
	}
	h.streamMu.Unlock()
}

func (h *InboundA2AHandler) markA2AStreamActive(taskID string) {
	h.streamMu.Lock()
	state := h.streamStates[taskID]
	if state == nil {
		state = &a2aStreamState{subscribers: make(map[chan a2aStreamEvent]struct{})}
		h.streamStates[taskID] = state
	}
	state.active = true
	h.streamMu.Unlock()
}

func (h *InboundA2AHandler) persistA2AStreamState(taskID string) error {
	if h == nil || h.config == nil || h.config.ObjectStore == nil {
		return nil
	}
	h.streamMu.Lock()
	state := h.streamStates[taskID]
	if state == nil {
		h.streamMu.Unlock()
		return nil
	}
	envelope := durableA2AStreamEnvelope{Next: state.next, Events: cloneA2AStreamEvents(state.events), Terminal: state.terminal}
	h.streamMu.Unlock()
	body, err := json.Marshal(envelope)
	if err != nil {
		return fmt.Errorf("encode durable A2A stream journal: %w", err)
	}
	storeCtx, cancel := context.WithTimeout(context.Background(), a2aTaskStoreTimeout)
	defer cancel()
	return h.config.ObjectStore.Put(storeCtx, durableA2AStreamKey(taskID), body, map[string]string{"kind": "a2a-stream-journal"})
}

func (h *InboundA2AHandler) loadDurableA2AStreamState(ctx context.Context, taskID string) {
	if h == nil || h.config == nil || h.config.ObjectStore == nil {
		return
	}
	h.streamMu.Lock()
	_, exists := h.streamStates[taskID]
	h.streamMu.Unlock()
	if exists {
		return
	}
	storeCtx, cancel := context.WithTimeout(ctx, a2aTaskStoreTimeout)
	body, err := h.config.ObjectStore.Get(storeCtx, durableA2AStreamKey(taskID))
	cancel()
	if err != nil {
		return
	}
	var envelope durableA2AStreamEnvelope
	if json.Unmarshal(body, &envelope) != nil {
		return
	}
	state := &a2aStreamState{next: envelope.Next, events: cloneA2AStreamEvents(envelope.Events), terminal: envelope.Terminal, subscribers: make(map[chan a2aStreamEvent]struct{})}
	h.streamMu.Lock()
	if _, exists := h.streamStates[taskID]; !exists {
		h.streamStates[taskID] = state
	}
	h.streamMu.Unlock()
}

func (h *InboundA2AHandler) recoverInterruptedA2AStream(ctx context.Context, partition string, task a2aTask) a2aTask {
	if isA2ATerminalState(task.Status.State) {
		return task
	}
	task.Status = a2aTaskStatus{State: "TASK_STATE_FAILED", Timestamp: h.currentTime().UTC(), Message: &a2aMessage{MessageID: task.ID + "-restart", Role: "agent", Parts: []a2aPart{{MediaType: "text/plain", Text: "A2A stream interrupted by gateway restart."}}}}
	_ = h.storeTask(ctx, partition, task)
	key := scopedA2ATaskKey(partition, task.ID)
	h.publishA2AStreamEvent(key, mustJSON(a2aJSONRPCError{Code: -32001, Message: "A2A stream interrupted by gateway restart"}), true)
	_ = h.persistA2AStreamState(key)
	return task
}

func cloneA2AStreamEvents(events []a2aStreamEvent) []a2aStreamEvent {
	clone := make([]a2aStreamEvent, len(events))
	for i, event := range events {
		clone[i] = a2aStreamEvent{ID: event.ID, Body: append([]byte(nil), event.Body...)}
	}
	return clone
}

func totalStreamEventBytes(events []a2aStreamEvent) int {
	total := 0
	for _, event := range events {
		total += len(event.ID) + len(event.Body)
	}
	return total
}

func durableA2AStreamKey(taskID string) string {
	sum := sha256.Sum256([]byte(taskID))
	return a2aTaskObjectPrefix + "streams/" + hex.EncodeToString(sum[:]) + ".json"
}

func (h *InboundA2AHandler) persistDetachedA2ATask(partition string, task a2aTask) error {
	ctx, cancel := context.WithTimeout(context.Background(), a2aTaskStoreTimeout)
	defer cancel()
	return h.storeTask(ctx, partition, task)
}

func drainA2AStream(stream chan *schemas.BifrostStreamChunk) {
	for range stream {
	}
}

func a2AStreamChunkText(chunk *schemas.BifrostStreamChunk) string {
	if chunk == nil || chunk.BifrostChatResponse == nil || len(chunk.BifrostChatResponse.Choices) == 0 {
		return ""
	}
	choice := chunk.BifrostChatResponse.Choices[0]
	if choice.ChatStreamResponseChoice == nil || choice.ChatStreamResponseChoice.Delta == nil || choice.ChatStreamResponseChoice.Delta.Content == nil {
		return ""
	}
	return *choice.ChatStreamResponseChoice.Delta.Content
}

func (h *InboundA2AHandler) restMessageSend(ctx *fasthttp.RequestCtx) {
	h.restRPCCall(ctx, "SendMessage", ctx.PostBody())
}

func (h *InboundA2AHandler) restMessageStream(ctx *fasthttp.RequestCtx) {
	request := a2aJSONRPCRequest{JSONRPC: "2.0", ID: json.RawMessage(`1`), Method: "SendStreamingMessage", Params: append([]byte(nil), ctx.PostBody()...)}
	ctx.Request.SetBody(mustJSON(request))
	h.messageStream(ctx)
}

func (h *InboundA2AHandler) restListTasks(ctx *fasthttp.RequestCtx) {
	args := ctx.QueryArgs()
	params := a2aListTasksParams{
		ContextID:        string(args.Peek("contextId")),
		Status:           string(args.Peek("status")),
		PageToken:        string(args.Peek("pageToken")),
		IncludeArtifacts: string(args.Peek("includeArtifacts")) == "true",
	}
	if raw := args.Peek("pageSize"); len(raw) > 0 {
		params.PageSize, _ = strconv.Atoi(string(raw))
	}
	h.restRPCCall(ctx, "ListTasks", mustJSON(params))
}

func (h *InboundA2AHandler) restCancelTask(ctx *fasthttp.RequestCtx) {
	params := a2aTaskParams{ID: string(ctx.UserValue("task_id").(string))}
	h.restRPCCall(ctx, "CancelTask", mustJSON(params))
}

func (h *InboundA2AHandler) restTaskAction(ctx *fasthttp.RequestCtx) {
	rawTaskID := stringValue(ctx.UserValue("task_id"))
	switch {
	case strings.HasSuffix(rawTaskID, ":cancel"):
		ctx.SetUserValue("task_id", strings.TrimSuffix(rawTaskID, ":cancel"))
		h.restCancelTask(ctx)
	case strings.HasSuffix(rawTaskID, ":subscribe"):
		ctx.SetUserValue("task_id", strings.TrimSuffix(rawTaskID, ":subscribe"))
		h.restSubscribeTask(ctx)
	default:
		SendError(ctx, fasthttp.StatusNotFound, "A2A task action is unavailable")
	}
}

func (h *InboundA2AHandler) restSubscribeTask(ctx *fasthttp.RequestCtx) {
	params := a2aTaskParams{ID: string(ctx.UserValue("task_id").(string))}
	request := a2aJSONRPCRequest{JSONRPC: "2.0", ID: json.RawMessage(`1`), Method: "SubscribeToTask", Params: mustJSON(params)}
	ctx.Request.SetBody(mustJSON(request))
	h.messageSend(ctx)
	if ctx.Response.StatusCode() >= 400 {
		return
	}
	body := append([]byte(nil), ctx.Response.Body()...)
	ctx.SetContentType("text/event-stream")
	ctx.Response.Header.Set("Cache-Control", "no-cache")
	ctx.SetBody(append([]byte("data: "), append(body, '\n', '\n')...))
}

func (h *InboundA2AHandler) restCreatePushNotificationConfig(ctx *fasthttp.RequestCtx) {
	params := append([]byte(nil), ctx.PostBody()...)
	params = ensureTaskID(params, stringValue(ctx.UserValue("task_id")))
	h.restRPCCall(ctx, "CreateTaskPushNotificationConfig", params)
}

func (h *InboundA2AHandler) restListPushNotificationConfigs(ctx *fasthttp.RequestCtx) {
	params := mustJSON(map[string]string{"taskId": stringValue(ctx.UserValue("task_id"))})
	h.restRPCCall(ctx, "ListTaskPushNotificationConfigs", params)
}

func (h *InboundA2AHandler) restGetPushNotificationConfig(ctx *fasthttp.RequestCtx) {
	params := mustJSON(map[string]string{"taskId": stringValue(ctx.UserValue("task_id")), "id": stringValue(ctx.UserValue("config_id"))})
	h.restRPCCall(ctx, "GetTaskPushNotificationConfig", params)
}

func (h *InboundA2AHandler) restDeletePushNotificationConfig(ctx *fasthttp.RequestCtx) {
	params := mustJSON(map[string]string{"taskId": stringValue(ctx.UserValue("task_id")), "id": stringValue(ctx.UserValue("config_id"))})
	h.restRPCCall(ctx, "DeleteTaskPushNotificationConfig", params)
}

func (h *InboundA2AHandler) restRPCCall(ctx *fasthttp.RequestCtx, method string, params []byte) {
	request := a2aJSONRPCRequest{JSONRPC: "2.0", ID: json.RawMessage(`1`), Method: method, Params: append([]byte(nil), params...)}
	ctx.Request.SetBody(mustJSON(request))
	h.messageSend(ctx)
	if ctx.Response.StatusCode() >= 400 {
		return
	}
	var response a2aJSONRPCResponse
	if err := json.Unmarshal(ctx.Response.Body(), &response); err != nil || response.Error != nil {
		return
	}
	ctx.SetContentType("application/a2a+json")
	ctx.SetBody(mustJSON(response.Result))
}

func (h *InboundA2AHandler) extendedAgentCardHTTP(ctx *fasthttp.RequestCtx) {
	base := inboundBaseURL(ctx)
	if base == "" {
		SendError(ctx, fasthttp.StatusBadRequest, "a2a public host is unavailable")
		return
	}
	record := h.agentCardRecord(base)
	if !record.Card.Capabilities.ExtendedAgentCard && !record.Card.SupportsAuthenticatedExtendedCard {
		SendError(ctx, fasthttp.StatusNotFound, "extended agent card is not supported")
		return
	}
	body, err := inbound.MarshalAgentCardJSON(record)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "extended agent card is unavailable")
		return
	}
	ctx.SetContentType("application/a2a+json")
	ctx.SetBody(body)
}

func (h *InboundA2AHandler) rpcGetTask(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	var params a2aTaskParams
	if err := json.Unmarshal(request.Params, &params); err != nil || strings.TrimSpace(params.ID) == "" {
		h.writeRPCError(ctx, request.ID, -32602, "params.id is required")
		return
	}
	task, ok := h.rpcLoadAuthorizedTask(ctx, params.ID)
	if !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	trimTaskHistory(&task, params.HistoryLength)
	h.writeRPCResult(ctx, request.ID, task)
}

func (h *InboundA2AHandler) rpcGetExtendedAgentCard(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	base := inboundBaseURL(ctx)
	if base == "" {
		h.writeRPCError(ctx, request.ID, -32000, "A2A public host is unavailable")
		return
	}
	record := h.agentCardRecord(base)
	if !record.Card.Capabilities.ExtendedAgentCard && !record.Card.SupportsAuthenticatedExtendedCard {
		h.writeRPCError(ctx, request.ID, -32601, "extended agent card is not supported")
		return
	}
	body, err := inbound.MarshalAgentCardJSON(record)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "extended agent card is unavailable")
		return
	}
	h.writeRPCResult(ctx, request.ID, json.RawMessage(body))
}

func (h *InboundA2AHandler) rpcCancelTask(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	var params a2aTaskParams
	if err := json.Unmarshal(request.Params, &params); err != nil || strings.TrimSpace(params.ID) == "" {
		h.writeRPCError(ctx, request.ID, -32602, "params.id is required")
		return
	}
	partition, err := inboundA2ATaskPartition(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	if err := h.validateInboundA2AAuthority(ctx, params.ID); err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	task, ok, loadErr := h.loadTask(ctx, partition, params.ID)
	if loadErr != nil {
		h.writeRPCError(ctx, request.ID, -32001, "A2A task registry is unavailable")
		return
	}
	if !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	if isA2ATerminalState(task.Status.State) {
		h.writeRPCError(ctx, request.ID, -32002, "Task is not cancelable")
		return
	}
	task.Status.State = "TASK_STATE_CANCELED"
	task.Status.Timestamp = h.currentTime().UTC()
	if err := h.storeTask(ctx, partition, task); err != nil {
		h.writeRPCError(ctx, request.ID, -32001, "A2A task registry is unavailable")
		return
	}
	h.writeRPCResult(ctx, request.ID, task)
}

func (h *InboundA2AHandler) rpcListTasks(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	var params a2aListTasksParams
	if len(request.Params) > 0 && string(request.Params) != "null" {
		if err := json.Unmarshal(request.Params, &params); err != nil {
			h.writeRPCError(ctx, request.ID, -32602, "invalid task list parameters")
			return
		}
	}
	if params.PageSize == 0 {
		params.PageSize = 50
	}
	if params.PageSize < 1 || params.PageSize > 100 {
		h.writeRPCError(ctx, request.ID, -32602, "pageSize must be between 1 and 100")
		return
	}
	offset := 0
	if params.PageToken != "" {
		parsed, parseErr := strconv.Atoi(params.PageToken)
		if parseErr != nil || parsed < 0 {
			h.writeRPCError(ctx, request.ID, -32602, "pageToken is invalid")
			return
		}
		offset = parsed
	}
	partition, err := inboundA2ATaskPartition(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	tasks := h.listTasks(partition, params.ContextID, params.Status)
	if offset > len(tasks) {
		h.writeRPCError(ctx, request.ID, -32602, "pageToken is invalid")
		return
	}
	end := offset + params.PageSize
	if end > len(tasks) {
		end = len(tasks)
	}
	result := a2aListTasksResult{TotalSize: len(tasks), PageSize: params.PageSize, Tasks: tasks[offset:end]}
	if end < len(tasks) {
		result.NextPageToken = strconv.Itoa(end)
	}
	if !params.IncludeArtifacts {
		for i := range result.Tasks {
			result.Tasks[i].Artifacts = nil
		}
	}
	h.writeRPCResult(ctx, request.ID, result)
}

func (h *InboundA2AHandler) rpcSubscribeTask(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	var params a2aTaskParams
	if err := json.Unmarshal(request.Params, &params); err != nil || strings.TrimSpace(params.ID) == "" {
		h.writeRPCError(ctx, request.ID, -32602, "params.id is required")
		return
	}
	task, ok := h.rpcLoadAuthorizedTask(ctx, params.ID)
	if !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	if isA2ATerminalState(task.Status.State) {
		h.writeRPCError(ctx, request.ID, -32003, "Task subscription is not supported for terminal tasks")
		return
	}
	h.writeSSETask(ctx, request.ID, task)
}

func (h *InboundA2AHandler) rpcCreatePushNotificationConfig(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	if !h.pushNotificationsAvailable() {
		h.writeRPCError(ctx, request.ID, -32004, "push notifications are not supported")
		return
	}
	var params a2aPushConfigRequest
	if err := json.Unmarshal(request.Params, &params); err != nil {
		h.writeRPCError(ctx, request.ID, -32602, "invalid push notification configuration")
		return
	}
	taskID := strings.TrimSpace(params.TaskID)
	if taskID == "" {
		h.writeRPCError(ctx, request.ID, -32602, "taskId is required")
		return
	}
	if _, ok := h.rpcLoadAuthorizedTask(ctx, taskID); !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	principal, err := inboundA2ATaskPrincipal(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	cfg, err := pushConfigFromRequest(params, principal.Tenant, taskID)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32602, err.Error())
		return
	}
	if err := a2apush.ValidateConfig(ctx, cfg, h.pushPolicy); err != nil {
		h.writeRPCError(ctx, request.ID, -32602, safePushConfigError(err))
		return
	}
	if err := h.pushStore.Create(ctx, cfg); err != nil {
		h.writeRPCError(ctx, request.ID, pushStoreErrorCode(err), safePushConfigError(err))
		return
	}
	h.writeRPCResult(ctx, request.ID, pushConfigResult(cfg))
}

func (h *InboundA2AHandler) rpcGetPushNotificationConfig(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	if !h.pushNotificationsAvailable() {
		h.writeRPCError(ctx, request.ID, -32004, "push notifications are not supported")
		return
	}
	var params a2aTaskParams
	if err := json.Unmarshal(request.Params, &params); err != nil || strings.TrimSpace(params.ID) == "" {
		h.writeRPCError(ctx, request.ID, -32602, "id is required")
		return
	}
	taskID := pushTaskID(request.Params)
	if taskID == "" {
		h.writeRPCError(ctx, request.ID, -32602, "taskId is required")
		return
	}
	if _, ok := h.rpcLoadAuthorizedTask(ctx, taskID); !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	principal, err := inboundA2ATaskPrincipal(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	cfg, err := h.pushStore.Get(ctx, principal.Tenant, taskID, params.ID)
	if err != nil {
		h.writeRPCError(ctx, request.ID, pushStoreErrorCode(err), safePushConfigError(err))
		return
	}
	h.writeRPCResult(ctx, request.ID, pushConfigResult(cfg))
}

func (h *InboundA2AHandler) rpcListPushNotificationConfigs(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	if !h.pushNotificationsAvailable() {
		h.writeRPCError(ctx, request.ID, -32004, "push notifications are not supported")
		return
	}
	taskID := pushTaskID(request.Params)
	if taskID == "" {
		h.writeRPCError(ctx, request.ID, -32602, "taskId is required")
		return
	}
	if _, ok := h.rpcLoadAuthorizedTask(ctx, taskID); !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	principal, err := inboundA2ATaskPrincipal(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	configs, err := h.pushStore.List(ctx, principal.Tenant, taskID)
	if err != nil {
		h.writeRPCError(ctx, request.ID, pushStoreErrorCode(err), safePushConfigError(err))
		return
	}
	result := a2aPushConfigListResult{Configs: make([]a2aPushConfigResult, 0, len(configs))}
	for _, cfg := range configs {
		result.Configs = append(result.Configs, pushConfigResult(cfg))
	}
	h.writeRPCResult(ctx, request.ID, result)
}

func (h *InboundA2AHandler) rpcDeletePushNotificationConfig(ctx *fasthttp.RequestCtx, request a2aJSONRPCRequest) {
	if !h.pushNotificationsAvailable() {
		h.writeRPCError(ctx, request.ID, -32004, "push notifications are not supported")
		return
	}
	var params a2aTaskParams
	if err := json.Unmarshal(request.Params, &params); err != nil || strings.TrimSpace(params.ID) == "" {
		h.writeRPCError(ctx, request.ID, -32602, "id is required")
		return
	}
	taskID := pushTaskID(request.Params)
	if taskID == "" {
		h.writeRPCError(ctx, request.ID, -32602, "taskId is required")
		return
	}
	if _, ok := h.rpcLoadAuthorizedTask(ctx, taskID); !ok {
		h.writeRPCError(ctx, request.ID, -32001, "Task not found")
		return
	}
	principal, err := inboundA2ATaskPrincipal(ctx)
	if err != nil {
		h.writeRPCError(ctx, request.ID, -32000, "A2A caller authority is invalid")
		return
	}
	if err := h.pushStore.Delete(ctx, principal.Tenant, taskID, params.ID); err != nil && !errors.Is(err, a2apush.ErrNotFound) {
		h.writeRPCError(ctx, request.ID, pushStoreErrorCode(err), safePushConfigError(err))
		return
	}
	h.writeRPCResult(ctx, request.ID, map[string]bool{"deleted": true})
}

func (h *InboundA2AHandler) pushNotificationsAvailable() bool {
	return h != nil && h.pushStore != nil && h.pushDelivery != nil
}

func pushConfigFromRequest(params a2aPushConfigRequest, tenant, taskID string) (a2apush.Config, error) {
	input := a2aPushNotificationConfig{ID: params.ID, TaskID: params.TaskID, URL: params.URL, Token: params.Token, TokenRef: params.TokenRef, Authentication: params.Authentication}
	if params.PushNotificationConfig != nil {
		input = *params.PushNotificationConfig
	}
	cfg := a2apush.Config{ID: strings.TrimSpace(input.ID), TaskID: taskID, TenantID: tenant, URL: strings.TrimSpace(input.URL)}
	if strings.TrimSpace(input.Token) != "" {
		return a2apush.Config{}, a2apush.ErrSecretRef
	}
	cfg.NotificationTokenRef = strings.TrimSpace(input.TokenRef)
	if cfg.ID == "" {
		cfg.ID = uuid.NewString()
	}
	if len(input.Authentication) > 0 && string(input.Authentication) != "null" {
		var auth a2aPushAuthentication
		if err := json.Unmarshal(input.Authentication, &auth); err != nil {
			var legacy []a2aPushAuthentication
			if err := json.Unmarshal(input.Authentication, &legacy); err != nil || len(legacy) != 1 {
				return a2apush.Config{}, errors.New("authentication must be one object")
			}
			auth = legacy[0]
		}
		if strings.TrimSpace(auth.Credentials) != "" {
			return a2apush.Config{}, a2apush.ErrSecretRef
		}
		cfg.AuthScheme = strings.ToLower(strings.TrimSpace(auth.Scheme))
		cfg.CredentialRef = strings.TrimSpace(auth.CredentialRef)
		cfg.SigningSecretRef = strings.TrimSpace(auth.SigningSecretRef)
	}
	return cfg, nil
}

func pushConfigResult(cfg a2apush.Config) a2aPushConfigResult {
	var auth *a2aPushAuthentication
	if cfg.AuthScheme != "" {
		auth = &a2aPushAuthentication{Scheme: cfg.AuthScheme}
	}
	return a2aPushConfigResult{ID: cfg.ID, TaskID: cfg.TaskID, URL: cfg.URL, Authentication: auth}
}

func pushTaskID(raw []byte) string {
	var params struct {
		TaskID string `json:"taskId"`
	}
	if json.Unmarshal(raw, &params) != nil {
		return ""
	}
	return strings.TrimSpace(params.TaskID)
}

func ensureTaskID(raw []byte, taskID string) []byte {
	var params map[string]any
	if json.Unmarshal(raw, &params) != nil {
		return raw
	}
	if _, ok := params["taskId"]; !ok || strings.TrimSpace(fmt.Sprint(params["taskId"])) == "" {
		params["taskId"] = taskID
	}
	return mustJSON(params)
}

func pushStoreErrorCode(err error) int {
	if errors.Is(err, a2apush.ErrNotFound) {
		return -32001
	}
	if errors.Is(err, a2apush.ErrSecretRef) || errors.Is(err, a2apush.ErrAlreadyExists) {
		return -32602
	}
	return -32001
}

func safePushConfigError(err error) string {
	switch {
	case errors.Is(err, a2apush.ErrNotFound):
		return "push notification configuration not found"
	case errors.Is(err, a2apush.ErrAlreadyExists):
		return "push notification configuration already exists"
	case errors.Is(err, a2apush.ErrSecretRef):
		return "push authentication must use a secret reference"
	default:
		return "push notification configuration is invalid"
	}
}

func (h *InboundA2AHandler) rpcLoadAuthorizedTask(ctx *fasthttp.RequestCtx, taskID string) (a2aTask, bool) {
	partition, err := inboundA2ATaskPartition(ctx)
	if err != nil || h.validateInboundA2AAuthority(ctx, taskID) != nil {
		return a2aTask{}, false
	}
	task, ok, loadErr := h.loadTask(ctx, partition, taskID)
	return task, loadErr == nil && ok
}

func (h *InboundA2AHandler) listTasks(partition, contextID, status string) []a2aTask {
	now := h.currentTime()
	h.mu.Lock()
	defer h.mu.Unlock()
	result := make([]a2aTask, 0)
	for key, stored := range h.tasks {
		if stored.ExpiresAt.Before(now) {
			delete(h.tasks, key)
			continue
		}
		if !strings.HasPrefix(key, partition+"\x00") || (contextID != "" && stored.Task.ContextID != contextID) || (status != "" && stored.Task.Status.State != status) {
			continue
		}
		result = append(result, stored.Task)
	}
	sort.SliceStable(result, func(i, j int) bool {
		if result[i].Status.Timestamp.Equal(result[j].Status.Timestamp) {
			return result[i].ID < result[j].ID
		}
		return result[i].Status.Timestamp.After(result[j].Status.Timestamp)
	})
	return result
}

func (h *InboundA2AHandler) writeSSETask(ctx *fasthttp.RequestCtx, id json.RawMessage, task a2aTask) {
	response := a2aJSONRPCResponse{JSONRPC: "2.0", ID: id, Result: map[string]any{"task": task}}
	body := mustJSON(response)
	ctx.SetContentType("text/event-stream")
	ctx.Response.Header.Set("Cache-Control", "no-cache")
	ctx.SetBody(append([]byte("data: "), append(body, '\n', '\n')...))
}

func trimTaskHistory(task *a2aTask, historyLength int) {
	if task == nil || historyLength <= 0 || len(task.History) <= historyLength {
		return
	}
	task.History = task.History[len(task.History)-historyLength:]
}

func isA2ATerminalState(state string) bool {
	switch state {
	case "completed", "failed", "canceled", "rejected", "TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_CANCELED", "TASK_STATE_REJECTED":
		return true
	default:
		return false
	}
}

func (h *InboundA2AHandler) taskGet(ctx *fasthttp.RequestCtx) {
	taskIDValue := ctx.UserValue("task_id")
	taskID, ok := taskIDValue.(string)
	if !ok {
		taskID = ""
	}
	taskID = strings.TrimSpace(taskID)
	if taskID == "" {
		h.writeRPCError(ctx, nil, -32602, "task_id is required")
		return
	}
	taskPartition, err := inboundA2ATaskPartition(ctx)
	if err != nil {
		SendError(ctx, fasthttp.StatusForbidden, "A2A caller authority is invalid")
		return
	}
	if err := h.validateInboundA2AAuthority(ctx, taskID); err != nil {
		SendError(ctx, fasthttp.StatusForbidden, "A2A caller authority is invalid")
		return
	}
	task, ok, loadErr := h.loadTask(ctx, taskPartition, taskID)
	if loadErr != nil {
		SendError(ctx, fasthttp.StatusServiceUnavailable, "A2A task registry is unavailable")
		return
	}
	if !ok {
		SendError(ctx, fasthttp.StatusNotFound, "A2A task not found")
		return
	}
	ctx.SetContentType("application/json")
	ctx.SetBody(mustJSON(task))
}

func (h *InboundA2AHandler) storeTask(ctx context.Context, partition string, task a2aTask) error {
	now := h.currentTime()
	if h.config != nil && h.config.ObjectStore != nil {
		envelope := durableA2ATaskEnvelope{Task: task, ExpiresAt: now.Add(maxA2ATaskTTL).UTC().Format(time.RFC3339Nano)}
		body, err := json.Marshal(envelope)
		if err != nil {
			return fmt.Errorf("encode durable A2A task: %w", err)
		}
		storeCtx, cancel := context.WithTimeout(ctx, a2aTaskStoreTimeout)
		err = h.config.ObjectStore.Put(storeCtx, durableA2ATaskKey(partition, task.ID), body, map[string]string{
			"kind":       "a2a-task",
			"expires_at": envelope.ExpiresAt,
		})
		cancel()
		if err != nil {
			return fmt.Errorf("persist durable A2A task: %w", err)
		}
	}
	h.mu.Lock()
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
	h.tasks[scopedA2ATaskKey(partition, task.ID)] = storedA2ATask{Task: task, ExpiresAt: now.Add(maxA2ATaskTTL)}
	pushRuntime := h.pushRuntime
	h.mu.Unlock()
	if pushRuntime != nil {
		payload := mustJSON(task)
		if err := pushRuntime.Enqueue(ctx, strings.SplitN(partition, "\x00", 2)[0], task.ID, payload); err != nil && !errors.Is(err, a2apush.ErrDisabled) {
			return fmt.Errorf("enqueue A2A push updates: %w", err)
		}
	}
	return nil
}

func (h *InboundA2AHandler) loadTask(ctx context.Context, partition string, id string) (a2aTask, bool, error) {
	if h.config != nil && h.config.ObjectStore != nil {
		storeCtx, cancel := context.WithTimeout(ctx, a2aTaskStoreTimeout)
		body, err := h.config.ObjectStore.Get(storeCtx, durableA2ATaskKey(partition, id))
		cancel()
		if err == nil {
			var envelope durableA2ATaskEnvelope
			if decodeErr := json.Unmarshal(body, &envelope); decodeErr != nil {
				return a2aTask{}, false, fmt.Errorf("decode durable A2A task: %w", decodeErr)
			}
			expiresAt, parseErr := time.Parse(time.RFC3339Nano, envelope.ExpiresAt)
			if parseErr != nil {
				return a2aTask{}, false, fmt.Errorf("decode durable A2A task expiry: %w", parseErr)
			}
			if expiresAt.Before(h.currentTime()) {
				return a2aTask{}, false, nil
			}
			return envelope.Task, true, nil
		}
		if !isA2AObjectNotFound(err) {
			return a2aTask{}, false, fmt.Errorf("load durable A2A task: %w", err)
		}
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	key := scopedA2ATaskKey(partition, id)
	stored, ok := h.tasks[key]
	if !ok || stored.ExpiresAt.Before(h.currentTime()) {
		if ok {
			delete(h.tasks, key)
		}
		return a2aTask{}, false, nil
	}
	return stored.Task, true, nil
}

func durableA2ATaskKey(partition, taskID string) string {
	digest := sha256.Sum256([]byte(partition + "\x00" + taskID))
	return a2aTaskObjectPrefix + hex.EncodeToString(digest[:]) + ".json"
}

func isA2AObjectNotFound(err error) bool {
	message := strings.ToLower(err.Error())
	return strings.Contains(message, "not found") || strings.Contains(message, "no such key") || strings.Contains(message, "nosuchkey")
}

func (h *InboundA2AHandler) validateInboundA2AAuthority(ctx *fasthttp.RequestCtx, artifactID string) error {
	principal, err := inboundA2ATaskPrincipal(ctx)
	if err != nil {
		return err
	}
	if h == nil {
		return nil
	}
	authorityStore := h.authorityStore
	if authorityStore == nil && h.config != nil && h.config.ConfigStore != nil {
		authorityStore, _ = h.config.ConfigStore.(configstore.PrincipalAuthorizationEpochStore)
	}
	if authorityStore == nil {
		return nil
	}
	reference, ok := ctx.UserValue(schemas.BifrostContextKeyAuthorizationEpochReference).(authorityepoch.Reference)
	if ok {
		if reference.Principal != principal {
			return authorityepoch.ErrInvalidReference
		}
		if err := authorityepoch.ValidateReferenceShape(reference); err != nil {
			return err
		}
		return authorityStore.ValidatePrincipalAuthorizationEpoch(ctx, reference)
	}
	if strings.TrimSpace(artifactID) == "" {
		return authorityepoch.ErrInvalidReference
	}
	row, err := authorityStore.GetPrincipalAuthorizationEpoch(ctx, principal)
	if err != nil {
		return err
	}
	if row == nil {
		return authorityepoch.ErrUnknownPrincipal
	}
	return authorityStore.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     row.Epoch,
		Kind:      authorityepoch.ArtifactA2ATask,
		ID:        artifactID,
	})
}

func (h *InboundA2AHandler) currentTime() time.Time {
	if h != nil && h.now != nil {
		return h.now()
	}
	return time.Now()
}

// inboundA2ATaskPartition is deliberately derived from the trusted principal
// installed by auth middleware, never from Agent Card publisher metadata or a
// caller-controlled tenant header. Missing authority fails closed so the
// in-memory idempotency cache cannot become a cross-tenant oracle.
func inboundA2ATaskPartition(ctx *fasthttp.RequestCtx) (string, error) {
	if ctx == nil {
		return "", authorityepoch.ErrInvalidPrincipal
	}
	principal, ok := ctx.UserValue(schemas.BifrostContextKeyAuthorizationPrincipal).(authorityepoch.Principal)
	if !ok || principal.Tenant == "" || principal.Issuer == "" || principal.Subject == "" {
		return "", authorityepoch.ErrInvalidPrincipal
	}
	return principal.Tenant + "\x00" + principal.Issuer + "\x00" + principal.Subject, nil
}

func scopedA2ATaskKey(partition, taskID string) string {
	return partition + "\x00" + taskID
}

func attachInboundA2AProvenance(bifrostCtx *schemas.BifrostContext, requestCtx *fasthttp.RequestCtx, config *lib.Config, taskID string, observedAt time.Time, cardDigest string) {
	if bifrostCtx == nil || requestCtx == nil {
		return
	}
	principal, err := inboundA2ATaskPrincipal(requestCtx)
	if err != nil {
		return
	}
	policyEpoch := ""
	if reference, ok := requestCtx.UserValue(schemas.BifrostContextKeyAuthorizationEpochReference).(authorityepoch.Reference); ok && reference.Epoch > 0 {
		policyEpoch = fmt.Sprintf("%d", reference.Epoch)
	}
	event := provenance.Event{
		SchemaVersion:      provenance.SchemaVersion,
		EventID:            "a2a:" + taskID,
		TenantID:           principal.Tenant,
		RequestID:          stringValue(requestCtx.UserValue(schemas.BifrostContextKeyRequestID)),
		TraceID:            stringValue(bifrostCtx.Value(schemas.BifrostContextKeyTraceID)),
		TaskID:             taskID,
		CardDigest:         cardDigest,
		CardRevision:       "inbound-agent-v1",
		PolicyEpoch:        policyEpoch,
		CapabilityDecision: "admitted",
		Outcome:            "accepted",
		ObservedAt:         observedAt.UTC(),
	}
	attributes, err := provenance.TraceAttributes(event)
	if err != nil {
		return
	}
	for key, value := range attributes {
		bifrostCtx.SetTraceAttribute(key, value)
	}
}

func inboundA2ATaskPrincipal(ctx *fasthttp.RequestCtx) (authorityepoch.Principal, error) {
	if ctx == nil {
		return authorityepoch.Principal{}, authorityepoch.ErrInvalidPrincipal
	}
	principal, ok := ctx.UserValue(schemas.BifrostContextKeyAuthorizationPrincipal).(authorityepoch.Principal)
	if !ok || authorityepoch.ValidatePrincipal(principal) != nil {
		return authorityepoch.Principal{}, authorityepoch.ErrInvalidPrincipal
	}
	return principal, nil
}

func stringValue(value interface{}) string {
	result, _ := value.(string)
	return result
}

func (h *InboundA2AHandler) inboundAgentCardDigest(ctx *fasthttp.RequestCtx) string {
	base := inboundBaseURL(ctx)
	if base == "" {
		return ""
	}
	body, err := inbound.MarshalAgentCardJSON(h.agentCardRecord(base))
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(body)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func (h *InboundA2AHandler) agentCardRecord(base string) inbound.Record {
	record := inboundRecordForConfig(base, h.config)
	record.Card.Capabilities.PushNotifications = h.pushNotificationsAvailable()
	return record
}

// inboundRecordForConfig is the production workflow-registry seam. The
// transport always exposes the governed gateway workflow, while a live model
// catalog revision is included as bounded card metadata so a publisher can
// prove which center-plane snapshot produced the card.
func inboundRecordForConfig(base string, config *lib.Config) inbound.Record {
	record := defaultInboundRecord(base)
	if config == nil || config.ModelCatalog == nil {
		return record
	}
	snapshot := config.ModelCatalog.CompileAgentModelCards()
	if snapshot.Revision.ID != "" {
		record.Card.Version = snapshot.Revision.ID
	}
	if record.Card.Extensions == nil {
		record.Card.Extensions = make(map[string]json.RawMessage)
	}
	metadata, err := json.Marshal(map[string]any{
		"revision":   snapshot.Revision.ID,
		"card_count": snapshot.Revision.CardCount,
	})
	if err == nil {
		record.Card.Extensions["frankengate.model_catalog"] = metadata
	}
	return record
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
		// A2A 1.0 uses a oneof JSON shape (`text`/`file`/`data`) without
		// the draft `kind` discriminator. Accept both wire forms.
		if (part.Kind == "" || part.Kind == "text") && strings.TrimSpace(part.Text) != "" {
			parts = append(parts, strings.TrimSpace(part.Text))
		}
	}
	return strings.Join(parts, "\n")
}

func a2aAgentRole(input string) string {
	if strings.HasPrefix(strings.ToUpper(strings.TrimSpace(input)), "ROLE_") {
		return "ROLE_AGENT"
	}
	return "agent"
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
	return inbound.Record{
		Card: inbound.CardRecord{
			Name:        "FrankenGate Agent Gateway",
			Description: "Governed A2A access to FrankenGate agent workflows.",
			Version:     "1",
			Interfaces: []inbound.InterfaceRecord{
				{URL: base, Transport: a2adiscovery.TransportJSONRPC},
				// HTTP+JSON clients append the operation binding (for example
				// /message:send) to this interface URL. JSON-RPC clients post to
				// the interface URL itself, so these URLs intentionally differ.
				{URL: base, Transport: a2adiscovery.TransportHTTPJSON},
			},
			Capabilities:                      a2adiscovery.AgentCapabilities{Streaming: true, StateTransitionHistory: true},
			DefaultInputModes:                 []string{"text"},
			DefaultOutputModes:                []string{"text"},
			SecuritySchemes:                   []inbound.SecuritySchemeRecord{{ID: "bearer", Scheme: a2adiscovery.SecurityScheme{Type: "http", Scheme: "bearer", BearerFormat: "JWT"}}},
			Security:                          []inbound.SecurityRequirementRecord{{Schemes: []inbound.SecurityRequirementScheme{{ID: "bearer", Scopes: []string{"a2a:invoke"}}}}},
			SupportsAuthenticatedExtendedCard: true,
		},
		Workflows: []inbound.WorkflowRecord{{ID: "gateway-chat", Name: "Governed chat", Description: "Routes an authenticated A2A message through the normal FrankenGate policy pipeline.", InputModes: []string{"text"}, OutputModes: []string{"text"}}},
	}
}

func mustJSON(value interface{}) []byte {
	body, _ := json.Marshal(value)
	return body
}
