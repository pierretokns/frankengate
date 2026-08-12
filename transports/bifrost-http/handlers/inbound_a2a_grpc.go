package handlers

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"iter"
	"net"
	"strings"
	"time"

	"github.com/a2aproject/a2a-go/v2/a2a"
	a2agrpc "github.com/a2aproject/a2a-go/v2/a2agrpc/v1"
	"github.com/a2aproject/a2a-go/v2/a2asrv"
	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2apush"
	"github.com/maximhq/bifrost/framework/modelcatalog/inbound"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

const (
	// A2A's protobuf messages are bounded at the hosted boundary. The limit is
	// deliberately independent from the HTTP body limit so a gRPC client cannot
	// turn a task or stream journal into an unbounded allocation.
	maxA2AGRPCMessageBytes = 256 * 1024
	maxA2AGRPCPageSize     = 100
)

// A2AGRPCAuthenticator verifies the incoming metadata and returns the
// canonical principal that owns the task namespace. Implementations must
// validate credentials (for example a JWT or mTLS identity) before returning;
// raw tenant/issuer/subject metadata is never accepted by this package.
type A2AGRPCAuthenticator func(context.Context, metadata.MD) (authorityepoch.Principal, authorityepoch.Reference, error)

// A2AGRPCOptions controls the hosted gRPC binding. Endpoint and Health are
// also used to gate Agent Card advertisement. A nil authenticator fails closed.
type A2AGRPCOptions struct {
	Endpoint      string
	Authenticator A2AGRPCAuthenticator
	Health        func(context.Context) bool
	Provider      string
	Model         string
	MaxRecvBytes  int
	MaxSendBytes  int
}

type inboundA2AGRPCHandler struct {
	owner   *InboundA2AHandler
	options A2AGRPCOptions
}

// ServeA2AGRPC owns the generated server and the supplied listener for the
// duration of the call. The Agent Card advertises gRPC only while this serve
// loop is live and the configured health predicate is true.
func (h *InboundA2AHandler) ServeA2AGRPC(listener net.Listener, options A2AGRPCOptions, serverOptions ...grpc.ServerOption) error {
	if h == nil || listener == nil {
		return errors.New("A2A gRPC handler and listener are required")
	}
	server, err := h.NewA2AGRPCServer(options, serverOptions...)
	if err != nil {
		return err
	}
	h.SetA2AGRPCReady(true)
	defer h.SetA2AGRPCReady(false)
	if err := server.Serve(listener); err != nil && !errors.Is(err, grpc.ErrServerStopped) {
		return err
	}
	return nil
}

// SetA2AGRPCReady is for callers that register on an externally managed
// grpc.Server. ServeA2AGRPC and the HTTP server lifecycle set it automatically.
func (h *InboundA2AHandler) SetA2AGRPCReady(ready bool) {
	if h == nil {
		return
	}
	h.grpcCardMu.Lock()
	h.grpcRunning = ready
	h.grpcCardMu.Unlock()
}

var _ a2asrv.RequestHandler = (*inboundA2AGRPCHandler)(nil)

// RegisterA2AGRPCServer registers the official A2A v1 gRPC service on an
// existing server. The generated service and protobuf conversion are supplied
// by github.com/a2aproject/a2a-go/v2; this method only adapts Bifrost policy
// and execution to a2asrv.RequestHandler.
func (h *InboundA2AHandler) RegisterA2AGRPCServer(server *grpc.Server, options A2AGRPCOptions) error {
	if h == nil || server == nil {
		return errors.New("A2A gRPC handler and server are required")
	}
	if options.Authenticator == nil {
		return errors.New("A2A gRPC metadata authenticator is required")
	}
	h.configureA2AGRPCCard(options)
	a2agrpc.NewHandler(&inboundA2AGRPCHandler{owner: h, options: options}).RegisterWith(server)
	return nil
}

// NewA2AGRPCServer creates a bounded official A2A v1 gRPC server. It is useful
// for a dedicated listener or bufconn and keeps message limits at construction
// time, where grpc-go applies them to every generated RPC.
func (h *InboundA2AHandler) NewA2AGRPCServer(options A2AGRPCOptions, serverOptions ...grpc.ServerOption) (*grpc.Server, error) {
	if h == nil {
		return nil, errors.New("A2A gRPC handler is required")
	}
	if options.Authenticator == nil {
		return nil, errors.New("A2A gRPC metadata authenticator is required")
	}
	if options.MaxRecvBytes <= 0 {
		options.MaxRecvBytes = maxA2AGRPCMessageBytes
	}
	if options.MaxSendBytes <= 0 {
		options.MaxSendBytes = maxA2AGRPCMessageBytes
	}
	serverOptions = append(serverOptions,
		grpc.MaxRecvMsgSize(options.MaxRecvBytes),
		grpc.MaxSendMsgSize(options.MaxSendBytes),
	)
	server := grpc.NewServer(serverOptions...)
	if err := h.RegisterA2AGRPCServer(server, options); err != nil {
		return nil, err
	}
	return server, nil
}

func (h *InboundA2AHandler) configureA2AGRPCCard(options A2AGRPCOptions) {
	h.grpcCardMu.Lock()
	h.grpcEndpoint = strings.TrimSpace(options.Endpoint)
	h.grpcHealth = options.Health
	h.grpcCardMu.Unlock()
}

func (h *InboundA2AHandler) a2AGRPCHealthy(ctx context.Context) bool {
	h.grpcCardMu.RLock()
	endpoint, health, running := h.grpcEndpoint, h.grpcHealth, h.grpcRunning
	h.grpcCardMu.RUnlock()
	return endpoint != "" && running && health != nil && health(ctx)
}

func (h *inboundA2AGRPCHandler) authorized(ctx context.Context, artifactID string) (context.Context, authorityepoch.Principal, error) {
	if err := ctx.Err(); err != nil {
		return nil, authorityepoch.Principal{}, err
	}
	md, _ := metadata.FromIncomingContext(ctx)
	principal, reference, err := h.options.Authenticator(ctx, md)
	if err != nil || authorityepoch.ValidatePrincipal(principal) != nil {
		return nil, authorityepoch.Principal{}, a2a.NewError(a2a.ErrUnauthenticated, "A2A metadata authentication failed")
	}
	if reference != (authorityepoch.Reference{}) {
		if reference.Principal != principal || authorityepoch.ValidateReferenceShape(reference) != nil {
			return nil, authorityepoch.Principal{}, a2a.NewError(a2a.ErrUnauthorized, "A2A authorization reference is invalid")
		}
	}
	if err := h.owner.validateInboundA2AGRPCAuthority(ctx, principal, reference, artifactID); err != nil {
		return nil, authorityepoch.Principal{}, a2a.NewError(a2a.ErrUnauthorized, "A2A caller authority is invalid")
	}
	ctx = context.WithValue(ctx, schemas.BifrostContextKeyAuthorizationPrincipal, principal)
	if reference != (authorityepoch.Reference{}) {
		ctx = context.WithValue(ctx, schemas.BifrostContextKeyAuthorizationEpochReference, reference)
	}
	return ctx, principal, nil
}

func (h *InboundA2AHandler) validateInboundA2AGRPCAuthority(ctx context.Context, principal authorityepoch.Principal, reference authorityepoch.Reference, artifactID string) error {
	if h == nil || h.authorityStore == nil {
		return nil
	}
	if reference != (authorityepoch.Reference{}) {
		return h.authorityStore.ValidatePrincipalAuthorizationEpoch(ctx, reference)
	}
	row, err := h.authorityStore.GetPrincipalAuthorizationEpoch(ctx, principal)
	if err != nil {
		return err
	}
	if row == nil {
		return authorityepoch.ErrUnknownPrincipal
	}
	if strings.TrimSpace(artifactID) == "" {
		return nil
	}
	return h.authorityStore.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     row.Epoch,
		Kind:      authorityepoch.ArtifactA2ATask,
		ID:        artifactID,
	})
}

func grpcPartition(principal authorityepoch.Principal) string {
	return principal.Tenant + "\x00" + principal.Issuer + "\x00" + principal.Subject
}

func grpcError(sentinel error, message string) error {
	return a2a.NewError(sentinel, message)
}

func grpcMessageToInternal(message *a2a.Message) (a2aMessage, string, error) {
	if message == nil || strings.TrimSpace(message.ID) == "" {
		return a2aMessage{}, "", grpcError(a2a.ErrInvalidParams, "message.messageId is required")
	}
	if len(message.Parts) == 0 || len(message.Parts) > maxA2AStreamEvents {
		return a2aMessage{}, "", grpcError(a2a.ErrInvalidParams, "message must contain bounded parts")
	}
	internal := a2aMessage{MessageID: message.ID, TaskID: string(message.TaskID), ContextID: message.ContextID, Role: string(message.Role)}
	var text []string
	for _, part := range message.Parts {
		if part == nil {
			return a2aMessage{}, "", grpcError(a2a.ErrInvalidParams, "message contains a nil part")
		}
		converted := a2aPart{Filename: part.Filename, MediaType: part.MediaType}
		switch value := part.Content.(type) {
		case a2a.Text:
			converted.Text = string(value)
			if strings.TrimSpace(converted.Text) != "" {
				text = append(text, strings.TrimSpace(converted.Text))
			}
		case a2a.Raw:
			converted.Raw = base64.StdEncoding.EncodeToString(value)
		case a2a.URL:
			converted.URL = string(value)
		case a2a.Data:
			data, err := json.Marshal(value.Value)
			if err != nil {
				return a2aMessage{}, "", grpcError(a2a.ErrInvalidParams, "message data is not valid JSON")
			}
			converted.Data = data
		default:
			return a2aMessage{}, "", grpcError(a2a.ErrUnsupportedContentType, "message content type is not supported")
		}
		if len(converted.Text)+len(converted.Raw)+len(converted.URL)+len(converted.Data)+len(converted.Filename)+len(converted.MediaType) > maxA2ATaskBodyBytes {
			return a2aMessage{}, "", grpcError(a2a.ErrInvalidParams, "message part exceeds the task limit")
		}
		internal.Parts = append(internal.Parts, converted)
	}
	joined := strings.Join(text, "\n")
	if joined == "" {
		return a2aMessage{}, "", grpcError(a2a.ErrUnsupportedContentType, "message must contain text content")
	}
	if len(joined) > maxA2ATaskBodyBytes {
		return a2aMessage{}, "", grpcError(a2a.ErrInvalidParams, "message exceeds the task limit")
	}
	return internal, joined, nil
}

func internalPartToGRPC(part a2aPart) *a2a.Part {
	result := &a2a.Part{Filename: part.Filename, MediaType: part.MediaType}
	switch {
	case part.Text != "":
		result.Content = a2a.Text(part.Text)
	case part.Raw != "":
		if raw, err := base64.StdEncoding.DecodeString(part.Raw); err == nil {
			result.Content = a2a.Raw(raw)
		} else {
			result.Content = a2a.Raw([]byte(part.Raw))
		}
	case part.URL != "":
		result.Content = a2a.URL(part.URL)
	case len(part.Data) > 0:
		var value any
		if json.Unmarshal(part.Data, &value) == nil {
			result.Content = a2a.Data{Value: value}
		}
	}
	return result
}

func internalMessageToGRPC(message *a2aMessage) *a2a.Message {
	if message == nil {
		return nil
	}
	parts := make(a2a.ContentParts, 0, len(message.Parts))
	for _, part := range message.Parts {
		parts = append(parts, internalPartToGRPC(part))
	}
	return &a2a.Message{ID: message.MessageID, TaskID: a2a.TaskID(message.TaskID), ContextID: message.ContextID, Role: a2a.MessageRole(message.Role), Parts: parts}
}

func internalTaskToGRPC(task a2aTask) *a2a.Task {
	result := &a2a.Task{ID: a2a.TaskID(task.ID), ContextID: task.ContextID, History: make([]*a2a.Message, 0, len(task.History)), Artifacts: make([]*a2a.Artifact, 0, len(task.Artifacts))}
	for i := range task.History {
		result.History = append(result.History, internalMessageToGRPC(&task.History[i]))
	}
	for _, artifact := range task.Artifacts {
		converted := &a2a.Artifact{ID: a2a.ArtifactID(artifact.ArtifactID), Name: artifact.Name, Parts: make(a2a.ContentParts, 0, len(artifact.Parts))}
		for _, part := range artifact.Parts {
			converted.Parts = append(converted.Parts, internalPartToGRPC(part))
		}
		result.Artifacts = append(result.Artifacts, converted)
	}
	statusMessage := internalMessageToGRPC(task.Status.Message)
	var timestamp *time.Time
	if !task.Status.Timestamp.IsZero() {
		value := task.Status.Timestamp
		timestamp = &value
	}
	result.Status = a2a.TaskStatus{State: a2a.TaskState(task.Status.State), Message: statusMessage, Timestamp: timestamp}
	return result
}

func (h *inboundA2AGRPCHandler) sendMessage(ctx context.Context, req *a2a.SendMessageRequest, streaming bool) (context.Context, a2aMessage, string, string, string, bool, a2aTask, error) {
	if req == nil {
		return nil, a2aMessage{}, "", "", "", false, a2aTask{}, grpcError(a2a.ErrInvalidRequest, "A2A request is required")
	}
	ctx, principal, err := h.authorized(ctx, "")
	if err != nil {
		return nil, a2aMessage{}, "", "", "", false, a2aTask{}, err
	}
	input, text, err := grpcMessageToInternal(req.Message)
	if err != nil {
		return nil, a2aMessage{}, "", "", "", false, a2aTask{}, err
	}
	requestedTaskID := strings.TrimSpace(string(input.TaskID))
	if requestedTaskID == "" {
		requestedTaskID = strings.TrimSpace(string(req.Message.TaskID))
	}
	contextID := strings.TrimSpace(input.ContextID)
	if contextID == "" {
		contextID = req.Message.ContextID
	}
	if contextID == "" {
		contextID = input.MessageID
	}
	taskID := requestedTaskID
	if taskID == "" {
		taskID = newA2ATaskID()
	}
	partition := grpcPartition(principal)
	if err := h.owner.validateInboundA2AGRPCAuthority(ctx, principal, authorityepoch.Reference{}, taskID); err != nil {
		return nil, a2aMessage{}, "", "", "", false, a2aTask{}, grpcError(a2a.ErrUnauthorized, "A2A caller authority is invalid")
	}
	var previous a2aTask
	followUp := requestedTaskID != ""
	if existing, ok, loadErr := h.owner.loadTask(ctx, partition, taskID); loadErr != nil {
		return nil, a2aMessage{}, "", "", "", false, a2aTask{}, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable")
	} else if ok {
		if !followUp {
			return ctx, input, text, taskID, contextID, false, existing, nil
		}
		if input.ContextID != "" && input.ContextID != existing.ContextID {
			return nil, a2aMessage{}, "", "", "", false, a2aTask{}, grpcError(a2a.ErrInvalidParams, "taskId and contextId do not match")
		}
		if isA2ATerminalState(existing.Status.State) && (streaming || followUp) {
			return nil, a2aMessage{}, "", "", "", false, a2aTask{}, grpcError(a2a.ErrTaskNotCancelable, "task is not available for another execution")
		}
		previous = existing
		contextID = existing.ContextID
	}
	return ctx, input, text, taskID, contextID, followUp, previous, nil
}

func (h *inboundA2AGRPCHandler) SendMessage(ctx context.Context, req *a2a.SendMessageRequest) (a2a.SendMessageResult, error) {
	ctx, input, text, taskID, contextID, followUp, previous, err := h.sendMessage(ctx, req, false)
	if err != nil {
		return nil, err
	}
	// A non-follow-up hit is an idempotent task read. The helper returns it with
	// empty input only when the task already exists.
	if previous.ID == taskID && input.MessageID != "" && !followUp {
		return internalTaskToGRPC(previous), nil
	}
	modes := []string(nil)
	if req.Config != nil {
		modes = append(modes, req.Config.AcceptedOutputModes...)
	}
	execution, handled, err := h.owner.resolveA2AExecution(ctx, A2AExecutionInput{MessageID: input.MessageID, TaskID: taskID, ContextID: contextID, InputText: text, AcceptedOutputModes: modes, FollowUp: followUp})
	if handled {
		if err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return nil, err
			}
			return nil, grpcError(a2a.ErrServerError, err.Error())
		}
		task, output := h.owner.taskFromExecutionResult(taskID, contextID, input, previous, followUp, execution)
		if execution.ReturnMessage {
			return internalMessageToGRPC(output), nil
		}
		if err := h.owner.storeTask(ctx, grpcPartition(mustPrincipal(ctx)), task); err != nil {
			return nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable")
		}
		return internalTaskToGRPC(task), nil
	}
	if h.owner.client == nil || h.owner.config == nil {
		return nil, grpcError(a2a.ErrInternalError, "A2A execution is unavailable")
	}
	response, err := h.grpcUnaryCompletion(ctx, input, text, req)
	if err != nil {
		return nil, err
	}
	output := a2aMessage{MessageID: taskID + "-result", Role: "ROLE_AGENT", Parts: []a2aPart{{Text: response, MediaType: "text/plain"}}}
	history := []a2aMessage{input, output}
	if followUp {
		history = append(append([]a2aMessage(nil), previous.History...), history...)
	}
	task := a2aTask{ID: taskID, ContextID: contextID, History: history, Artifacts: []a2aArtifact{{ArtifactID: taskID + "-response", Name: "response", Parts: output.Parts}}, Status: a2aTaskStatus{State: "TASK_STATE_COMPLETED", Timestamp: h.owner.currentTime().UTC(), Message: &output}}
	if err := h.owner.storeTask(ctx, grpcPartition(mustPrincipal(ctx)), task); err != nil {
		return nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable")
	}
	return internalTaskToGRPC(task), nil
}

func mustPrincipal(ctx context.Context) authorityepoch.Principal {
	principal, _ := schemas.AuthorizationPrincipalFromContext(ctx)
	return principal
}

func (h *inboundA2AGRPCHandler) grpcUnaryCompletion(ctx context.Context, input a2aMessage, text string, req *a2a.SendMessageRequest) (string, error) {
	bifrostCtx, cancel := schemas.NewBifrostContextWithCancel(ctx)
	defer cancel()
	principal := mustPrincipal(ctx)
	if err := schemas.SetAuthorizationPrincipal(bifrostCtx, principal); err != nil {
		return "", grpcError(a2a.ErrUnauthorized, "A2A caller authority is invalid")
	}
	if reference, err := schemas.AuthorizationEpochReferenceFromContext(ctx); err == nil {
		_ = schemas.SetAuthorizationEpochReference(bifrostCtx, reference)
	}
	provider, model := h.options.Provider, h.options.Model
	_ = input
	response, bifrostErr := h.owner.client.ChatCompletionRequest(bifrostCtx, &schemas.BifrostChatRequest{Provider: schemas.ModelProvider(provider), Model: model, Input: []schemas.ChatMessage{{Role: schemas.ChatMessageRoleUser, Content: &schemas.ChatMessageContent{ContentStr: &text}}}})
	if bifrostErr != nil {
		return "", grpcError(a2a.ErrInternalError, bifrost.GetErrorMessage(bifrostErr))
	}
	answer := chatResponseText(response)
	if answer == "" {
		return "", grpcError(a2a.ErrInvalidAgentResponse, "model returned no text content")
	}
	return answer, nil
}

func (h *inboundA2AGRPCHandler) SendStreamingMessage(ctx context.Context, req *a2a.SendMessageRequest) iter.Seq2[a2a.Event, error] {
	return func(yield func(a2a.Event, error) bool) {
		ctx, input, text, taskID, contextID, followUp, previous, err := h.sendMessage(ctx, req, true)
		if err != nil {
			yield(nil, err)
			return
		}
		partition := grpcPartition(mustPrincipal(ctx))
		submitted := a2aTask{ID: taskID, ContextID: contextID, History: []a2aMessage{input}, Status: a2aTaskStatus{State: "TASK_STATE_SUBMITTED", Timestamp: h.owner.currentTime().UTC()}}
		if previous.ID == taskID {
			submitted = previous
		}
		if err := h.owner.storeTask(ctx, partition, submitted); err != nil {
			yield(nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable"))
			return
		}
		streamKey := grpcStreamKey(partition, taskID)
		h.owner.markA2AStreamActive(streamKey)
		publish := func(event a2a.Event, terminal bool) bool {
			if !h.owner.publishGRPCA2AEvent(streamKey, event, terminal) {
				return false
			}
			return yield(event, nil)
		}
		if !publish(internalTaskToGRPC(submitted), false) {
			return
		}
		working := submitted
		working.Status = a2aTaskStatus{State: "TASK_STATE_WORKING", Timestamp: h.owner.currentTime().UTC(), Message: &a2aMessage{MessageID: taskID + "-working", Role: "ROLE_AGENT", Parts: []a2aPart{{Text: "Working on the request.", MediaType: "text/plain"}}}}
		if err := h.owner.storeTask(ctx, partition, working); err != nil {
			yield(nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable"))
			return
		}
		if !publish(&a2a.TaskStatusUpdateEvent{TaskID: a2a.TaskID(taskID), ContextID: contextID, Status: a2a.TaskStatus{State: a2a.TaskStateWorking, Message: internalMessageToGRPC(working.Status.Message), Timestamp: timePtr(working.Status.Timestamp)}}, false) {
			return
		}
		modes := []string(nil)
		if req.Config != nil {
			modes = append(modes, req.Config.AcceptedOutputModes...)
		}
		execution, handled, err := h.owner.resolveA2AExecution(ctx, A2AExecutionInput{MessageID: input.MessageID, TaskID: taskID, ContextID: contextID, InputText: text, AcceptedOutputModes: modes, FollowUp: followUp})
		if handled {
			if err != nil {
				if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
					yield(nil, err)
					return
				}
				yield(nil, grpcError(a2a.ErrServerError, err.Error()))
				return
			}
			task, output := h.owner.taskFromExecutionResult(taskID, contextID, input, previous, followUp, execution)
			for _, artifact := range task.Artifacts {
				if !publish(&a2a.TaskArtifactUpdateEvent{TaskID: a2a.TaskID(taskID), ContextID: contextID, Artifact: internalArtifactToGRPC(artifact), LastChunk: true}, false) {
					return
				}
			}
			if err := h.owner.storeTask(ctx, partition, task); err != nil {
				yield(nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable"))
				return
			}
			publish(&a2a.TaskStatusUpdateEvent{TaskID: a2a.TaskID(taskID), ContextID: contextID, Status: grpcTaskStatus(task.Status)}, true)
			_ = output
			return
		}
		if h.owner.client == nil || h.owner.config == nil {
			yield(nil, grpcError(a2a.ErrInternalError, "A2A execution is unavailable"))
			return
		}
		bifrostCtx, cancel := schemas.NewBifrostContextWithCancel(ctx)
		defer cancel()
		_ = schemas.SetAuthorizationPrincipal(bifrostCtx, mustPrincipal(ctx))
		if reference, refErr := schemas.AuthorizationEpochReferenceFromContext(ctx); refErr == nil {
			_ = schemas.SetAuthorizationEpochReference(bifrostCtx, reference)
		}
		provider, model := h.options.Provider, h.options.Model
		stream, bifrostErr := h.owner.client.ChatCompletionStreamRequest(bifrostCtx, &schemas.BifrostChatRequest{Provider: schemas.ModelProvider(provider), Model: model, Input: []schemas.ChatMessage{{Role: schemas.ChatMessageRoleUser, Content: &schemas.ChatMessageContent{ContentStr: &text}}}})
		if bifrostErr != nil || stream == nil {
			yield(nil, grpcError(a2a.ErrInternalError, "A2A stream is unavailable"))
			return
		}
		var answer strings.Builder
		for {
			select {
			case <-ctx.Done():
				h.owner.finishA2AStream(streamKey)
				return
			case chunk, ok := <-stream:
				if !ok {
					output := a2aMessage{MessageID: taskID + "-result", Role: "ROLE_AGENT", Parts: []a2aPart{{Text: strings.TrimSpace(answer.String()), MediaType: "text/plain"}}}
					final := working
					final.History = append(final.History, output)
					final.Artifacts = []a2aArtifact{{ArtifactID: taskID + "-response", Name: "response", Parts: output.Parts}}
					final.Status = a2aTaskStatus{State: "TASK_STATE_COMPLETED", Timestamp: h.owner.currentTime().UTC(), Message: &output}
					if err := h.owner.storeTask(ctx, partition, final); err != nil {
						yield(nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable"))
						return
					}
					publish(&a2a.TaskStatusUpdateEvent{TaskID: a2a.TaskID(taskID), ContextID: contextID, Status: grpcTaskStatus(final.Status)}, true)
					return
				}
				if chunk == nil {
					continue
				}
				if chunk.BifrostError != nil {
					h.owner.finishA2AStream(streamKey)
					yield(nil, grpcError(a2a.ErrInternalError, bifrost.GetErrorMessage(chunk.BifrostError)))
					return
				}
				delta := a2AStreamChunkText(chunk)
				if delta == "" {
					continue
				}
				if answer.Len()+len(delta) > maxA2ATaskBodyBytes {
					h.owner.finishA2AStream(streamKey)
					yield(nil, grpcError(a2a.ErrInvalidAgentResponse, "A2A stream output exceeds the task limit"))
					return
				}
				answer.WriteString(delta)
				if !publish(&a2a.TaskArtifactUpdateEvent{TaskID: a2a.TaskID(taskID), ContextID: contextID, Append: true, Artifact: &a2a.Artifact{ID: a2a.ArtifactID(taskID + "-response"), Name: "response", Parts: a2a.ContentParts{&a2a.Part{Content: a2a.Text(delta), MediaType: "text/plain"}}}}, false) {
					return
				}
			}
		}
	}
}

func timePtr(value time.Time) *time.Time { return &value }

func grpcTaskStatus(value a2aTaskStatus) a2a.TaskStatus {
	return a2a.TaskStatus{State: a2a.TaskState(value.State), Message: internalMessageToGRPC(value.Message), Timestamp: timePtr(value.Timestamp)}
}

func internalArtifactToGRPC(value a2aArtifact) *a2a.Artifact {
	result := &a2a.Artifact{ID: a2a.ArtifactID(value.ArtifactID), Name: value.Name, Parts: make(a2a.ContentParts, 0, len(value.Parts))}
	for _, part := range value.Parts {
		result.Parts = append(result.Parts, internalPartToGRPC(part))
	}
	return result
}

func (h *inboundA2AGRPCHandler) GetTask(ctx context.Context, req *a2a.GetTaskRequest) (*a2a.Task, error) {
	ctx, principal, err := h.authorized(ctx, string(req.ID))
	if err != nil {
		return nil, err
	}
	task, ok, loadErr := h.owner.loadTask(ctx, grpcPartition(principal), string(req.ID))
	if loadErr != nil {
		return nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable")
	}
	if !ok {
		return nil, grpcError(a2a.ErrTaskNotFound, "Task not found")
	}
	if req.HistoryLength != nil {
		trimTaskHistory(&task, *req.HistoryLength)
	}
	return internalTaskToGRPC(task), nil
}

func (h *inboundA2AGRPCHandler) ListTasks(ctx context.Context, req *a2a.ListTasksRequest) (*a2a.ListTasksResponse, error) {
	ctx, principal, err := h.authorized(ctx, "")
	if err != nil {
		return nil, err
	}
	pageSize := req.PageSize
	if pageSize == 0 {
		pageSize = 50
	}
	if pageSize < 1 || pageSize > maxA2AGRPCPageSize {
		return nil, grpcError(a2a.ErrInvalidParams, "pageSize must be between 1 and 100")
	}
	offset := 0
	if req.PageToken != "" {
		if _, scanErr := fmt.Sscanf(req.PageToken, "%d", &offset); scanErr != nil || offset < 0 {
			return nil, grpcError(a2a.ErrInvalidParams, "pageToken is invalid")
		}
	}
	tasks := h.owner.listTasks(grpcPartition(principal), req.ContextID, string(req.Status))
	if offset > len(tasks) {
		return nil, grpcError(a2a.ErrInvalidParams, "pageToken is invalid")
	}
	end := offset + pageSize
	if end > len(tasks) {
		end = len(tasks)
	}
	result := &a2a.ListTasksResponse{Tasks: make([]*a2a.Task, 0, end-offset), TotalSize: len(tasks), PageSize: pageSize}
	for _, task := range tasks[offset:end] {
		if !req.IncludeArtifacts {
			task.Artifacts = nil
		}
		if req.HistoryLength != nil {
			trimTaskHistory(&task, *req.HistoryLength)
		}
		result.Tasks = append(result.Tasks, internalTaskToGRPC(task))
	}
	if end < len(tasks) {
		result.NextPageToken = fmt.Sprintf("%d", end)
	}
	_ = ctx
	return result, nil
}

func (h *inboundA2AGRPCHandler) CancelTask(ctx context.Context, req *a2a.CancelTaskRequest) (*a2a.Task, error) {
	ctx, principal, err := h.authorized(ctx, string(req.ID))
	if err != nil {
		return nil, err
	}
	partition := grpcPartition(principal)
	task, ok, loadErr := h.owner.loadTask(ctx, partition, string(req.ID))
	if loadErr != nil {
		return nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable")
	}
	if !ok {
		return nil, grpcError(a2a.ErrTaskNotFound, "Task not found")
	}
	if isA2ATerminalState(task.Status.State) {
		return nil, grpcError(a2a.ErrTaskNotCancelable, "Task is not cancelable")
	}
	task.Status = a2aTaskStatus{State: "TASK_STATE_CANCELED", Timestamp: h.owner.currentTime().UTC()}
	if err := h.owner.storeTask(ctx, partition, task); err != nil {
		return nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable")
	}
	return internalTaskToGRPC(task), nil
}

func grpcStreamKey(partition string, taskID string) string {
	return partition + "\x00" + taskID + "\x00grpc"
}

func (h *InboundA2AHandler) publishGRPCA2AEvent(key string, event a2a.Event, terminal bool) bool {
	body, err := json.Marshal(a2a.StreamResponse{Event: event})
	if err != nil {
		return false
	}
	h.publishA2AStreamEvent(key, body, terminal)
	return true
}

func grpcEventFromBody(body []byte) (a2a.Event, error) {
	var wire struct {
		Message        *a2a.Message                 `json:"message"`
		Task           *a2a.Task                    `json:"task"`
		StatusUpdate   *a2a.TaskStatusUpdateEvent   `json:"statusUpdate"`
		ArtifactUpdate *a2a.TaskArtifactUpdateEvent `json:"artifactUpdate"`
	}
	if err := json.Unmarshal(body, &wire); err != nil {
		return nil, err
	}
	switch {
	case wire.Message != nil:
		return wire.Message, nil
	case wire.Task != nil:
		return wire.Task, nil
	case wire.StatusUpdate != nil:
		return wire.StatusUpdate, nil
	case wire.ArtifactUpdate != nil:
		return wire.ArtifactUpdate, nil
	default:
		return nil, errors.New("unknown A2A gRPC stream event")
	}
}

func (h *inboundA2AGRPCHandler) SubscribeToTask(ctx context.Context, req *a2a.SubscribeToTaskRequest) iter.Seq2[a2a.Event, error] {
	return func(yield func(a2a.Event, error) bool) {
		ctx, principal, err := h.authorized(ctx, string(req.ID))
		if err != nil {
			yield(nil, err)
			return
		}
		partition := grpcPartition(principal)
		task, ok, loadErr := h.owner.loadTask(ctx, partition, string(req.ID))
		if loadErr != nil {
			yield(nil, grpcError(a2a.ErrInternalError, "A2A task registry is unavailable"))
			return
		}
		if !ok {
			yield(nil, grpcError(a2a.ErrTaskNotFound, "Task not found"))
			return
		}
		if isA2ATerminalState(task.Status.State) {
			yield(nil, grpcError(a2a.ErrUnsupportedOperation, "Task subscription is not supported for terminal tasks"))
			return
		}
		replay, subscriber, unsubscribe, terminal, _ := h.owner.subscribeA2AStream(ctx, grpcStreamKey(partition, string(req.ID)), 0)
		defer unsubscribe()
		if len(replay) == 0 && subscriber == nil {
			if !yield(internalTaskToGRPC(task), nil) {
				return
			}
		}
		for _, event := range replay {
			converted, convertErr := grpcEventFromBody(event.Body)
			if convertErr != nil || !yield(converted, convertErr) {
				return
			}
		}
		if subscriber == nil || terminal {
			return
		}
		for {
			select {
			case <-ctx.Done():
				return
			case event, ok := <-subscriber:
				if !ok {
					return
				}
				converted, convertErr := grpcEventFromBody(event.Body)
				if convertErr != nil || !yield(converted, convertErr) {
					return
				}
			}
		}
	}
}

func (h *inboundA2AGRPCHandler) CreateTaskPushConfig(ctx context.Context, req *a2a.PushConfig) (*a2a.PushConfig, error) {
	ctx, principal, err := h.authorized(ctx, string(req.TaskID))
	if err != nil {
		return nil, err
	}
	if !h.owner.pushNotificationsAvailable() {
		return nil, grpcError(a2a.ErrPushNotificationNotSupported, "push notifications are not supported")
	}
	if req.Auth != nil && strings.TrimSpace(req.Auth.Credentials) != "" {
		return nil, grpcError(a2a.ErrInvalidParams, "push credentials must be secret references")
	}
	if _, ok, loadErr := h.owner.loadTask(ctx, grpcPartition(principal), string(req.TaskID)); loadErr != nil || !ok {
		return nil, grpcError(a2a.ErrTaskNotFound, "Task not found")
	}
	var auth json.RawMessage
	if req.Auth != nil {
		auth, _ = json.Marshal(map[string]string{"scheme": req.Auth.Scheme})
	}
	cfg, err := pushConfigFromRequest(a2aPushConfigRequest{ID: req.ID, TaskID: string(req.TaskID), URL: req.URL, Token: req.Token, Authentication: auth}, principal.Tenant, string(req.TaskID))
	if err != nil {
		return nil, grpcError(a2a.ErrInvalidParams, err.Error())
	}
	if err := a2apush.ValidateConfig(ctx, cfg, h.owner.pushPolicy); err != nil {
		return nil, grpcError(a2a.ErrInvalidParams, safePushConfigError(err))
	}
	if err := h.owner.pushStore.Create(ctx, cfg); err != nil {
		return nil, grpcError(a2a.ErrInvalidParams, safePushConfigError(err))
	}
	return grpcPushConfig(cfg), nil
}

func grpcPushConfig(cfg a2apush.Config) *a2a.PushConfig {
	result := &a2a.PushConfig{ID: cfg.ID, TaskID: a2a.TaskID(cfg.TaskID), URL: cfg.URL}
	if cfg.AuthScheme != "" {
		result.Auth = &a2a.PushAuthInfo{Scheme: cfg.AuthScheme}
	}
	return result
}

func (h *inboundA2AGRPCHandler) GetTaskPushConfig(ctx context.Context, req *a2a.GetTaskPushConfigRequest) (*a2a.PushConfig, error) {
	ctx, principal, err := h.authorized(ctx, string(req.TaskID))
	if err != nil {
		return nil, err
	}
	if !h.owner.pushNotificationsAvailable() {
		return nil, grpcError(a2a.ErrPushNotificationNotSupported, "push notifications are not supported")
	}
	cfg, err := h.owner.pushStore.Get(ctx, principal.Tenant, string(req.TaskID), req.ID)
	if err != nil {
		return nil, grpcError(a2a.ErrTaskNotFound, "push notification configuration not found")
	}
	return grpcPushConfig(cfg), nil
}

func (h *inboundA2AGRPCHandler) ListTaskPushConfigs(ctx context.Context, req *a2a.ListTaskPushConfigRequest) (*a2a.ListTaskPushConfigResponse, error) {
	ctx, principal, err := h.authorized(ctx, string(req.TaskID))
	if err != nil {
		return nil, err
	}
	if !h.owner.pushNotificationsAvailable() {
		return nil, grpcError(a2a.ErrPushNotificationNotSupported, "push notifications are not supported")
	}
	configs, err := h.owner.pushStore.List(ctx, principal.Tenant, string(req.TaskID))
	if err != nil {
		return nil, grpcError(a2a.ErrInternalError, "push notification configuration lookup failed")
	}
	result := &a2a.ListTaskPushConfigResponse{Configs: make([]*a2a.PushConfig, 0, len(configs))}
	for _, cfg := range configs {
		result.Configs = append(result.Configs, grpcPushConfig(cfg))
	}
	return result, nil
}

func (h *inboundA2AGRPCHandler) DeleteTaskPushConfig(ctx context.Context, req *a2a.DeleteTaskPushConfigRequest) error {
	ctx, principal, err := h.authorized(ctx, string(req.TaskID))
	if err != nil {
		return err
	}
	if !h.owner.pushNotificationsAvailable() {
		return grpcError(a2a.ErrPushNotificationNotSupported, "push notifications are not supported")
	}
	err = h.owner.pushStore.Delete(ctx, principal.Tenant, string(req.TaskID), req.ID)
	if errors.Is(err, a2apush.ErrNotFound) {
		return nil
	}
	if err != nil {
		return grpcError(a2a.ErrInternalError, "push notification configuration deletion failed")
	}
	return nil
}

func (h *inboundA2AGRPCHandler) GetExtendedAgentCard(ctx context.Context, _ *a2a.GetExtendedAgentCardRequest) (*a2a.AgentCard, error) {
	ctx, _, err := h.authorized(ctx, "grpc-card")
	if err != nil {
		return nil, err
	}
	if !h.owner.a2AGRPCHealthy(ctx) {
		return nil, grpcError(a2a.ErrExtendedCardNotConfigured, "extended agent card is not available")
	}
	h.owner.grpcCardMu.RLock()
	endpoint := h.owner.grpcEndpoint
	h.owner.grpcCardMu.RUnlock()
	record := h.owner.agentCardRecord(endpoint)
	body, err := inbound.MarshalAgentCardJSON(record)
	if err != nil {
		return nil, grpcError(a2a.ErrInternalError, "extended agent card is unavailable")
	}
	var card a2a.AgentCard
	if err := json.Unmarshal(body, &card); err != nil {
		return nil, grpcError(a2a.ErrInternalError, "extended agent card conversion failed")
	}
	return &card, nil
}
