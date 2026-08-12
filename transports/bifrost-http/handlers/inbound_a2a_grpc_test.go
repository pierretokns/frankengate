package handlers

import (
	"context"
	"errors"
	"io"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/a2aproject/a2a-go/v2/a2a"
	a2apb "github.com/a2aproject/a2a-go/v2/a2apb/v1"
	"github.com/a2aproject/a2a-go/v2/a2apb/v1/pbconv"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2apush"
	"github.com/maximhq/bifrost/framework/modelcatalog/inbound"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
)

func TestInboundA2AGRPCBufconnOfficialClient(t *testing.T) {
	handler := NewInboundA2AHandler(nil, nil)
	handler.SetA2AExecutionResolver(A2AExecutionResolverFunc(func(ctx context.Context, input A2AExecutionInput) (A2AExecutionResult, error) {
		if err := ctx.Err(); err != nil {
			return A2AExecutionResult{}, err
		}
		return A2AExecutionResult{
			Handled:     true,
			MessageText: "done",
			Artifacts: []A2AExecutionArtifact{{
				ArtifactID: "answer",
				Name:       "answer.txt",
				Parts:      []A2AExecutionArtifactPart{{Raw: "ZG9uZQ==", MediaType: "text/plain"}},
			}},
		}, nil
	}))
	handler.ConfigurePushNotifications(
		a2apush.NewMemoryStore(time.Now),
		a2apush.Policy{
			AllowedHosts: []string{"notify.example.test"},
			Resolver: a2apush.ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
				return []net.IPAddr{{IP: net.ParseIP("93.184.216.34")}}, nil
			}),
		},
		grpcTestPushDelivery{},
	)

	client, closeServer := startA2AGRPCBufconn(t, handler, A2AGRPCOptions{
		Endpoint:      "bufnet",
		Authenticator: grpcTestAuthenticator,
		Health:        func(context.Context) bool { return true },
	})
	defer closeServer()

	ctx := grpcTestContext("tenant-a")
	request, err := pbconv.ToProtoSendMessageRequest(grpcTestMessage("message-a", "hello"))
	if err != nil {
		t.Fatal(err)
	}
	response, err := client.SendMessage(ctx, request)
	if err != nil {
		t.Fatalf("SendMessage: %v", err)
	}
	result, err := pbconv.FromProtoSendMessageResponse(response)
	if err != nil {
		t.Fatal(err)
	}
	task, ok := result.(*a2a.Task)
	if !ok || task == nil {
		t.Fatalf("SendMessage result = %T, want *a2a.Task", result)
	}
	if task.Status.State != a2a.TaskStateCompleted || task.ContextID == "" {
		t.Fatalf("task = %#v, want completed task with context", task)
	}
	if len(task.Artifacts) != 1 || len(task.Artifacts[0].Parts) != 1 {
		t.Fatalf("task artifacts = %#v, want one artifact part", task.Artifacts)
	}
	if raw, ok := task.Artifacts[0].Parts[0].Content.(a2a.Raw); !ok || string(raw) != "done" {
		t.Fatalf("artifact raw content = %#v, want decoded bytes", task.Artifacts[0].Parts[0].Content)
	}

	getRequest, err := pbconv.ToProtoGetTaskRequest(&a2a.GetTaskRequest{ID: task.ID})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.GetTask(ctx, getRequest); err != nil {
		t.Fatalf("GetTask in owning tenant: %v", err)
	}
	if _, err := client.GetTask(grpcTestContext("tenant-b"), getRequest); status.Code(err) != codes.NotFound {
		t.Fatalf("GetTask across tenants code = %s, want NotFound", status.Code(err))
	}
	if _, err := client.ListTasks(context.Background(), &a2apb.ListTasksRequest{}); status.Code(err) != codes.Unauthenticated {
		t.Fatalf("missing metadata code = %s, want Unauthenticated", status.Code(err))
	}

	streamRequest, err := pbconv.ToProtoSendMessageRequest(grpcTestMessage("message-stream", "stream me"))
	if err != nil {
		t.Fatal(err)
	}
	stream, err := client.SendStreamingMessage(ctx, streamRequest)
	if err != nil {
		t.Fatalf("SendStreamingMessage: %v", err)
	}
	var events int
	var finalState a2a.TaskState
	for {
		wireEvent, recvErr := stream.Recv()
		if errors.Is(recvErr, io.EOF) {
			break
		}
		if recvErr != nil {
			t.Fatalf("Recv stream event: %v", recvErr)
		}
		event, convertErr := pbconv.FromProtoStreamResponse(wireEvent)
		if convertErr != nil {
			t.Fatal(convertErr)
		}
		events++
		if update, ok := event.(*a2a.TaskStatusUpdateEvent); ok {
			finalState = update.Status.State
		}
	}
	if events < 4 || finalState != a2a.TaskStateCompleted {
		t.Fatalf("stream events = %d, final state = %s; want true multi-event stream ending completed", events, finalState)
	}

	pushRequest, err := pbconv.ToProtoTaskPushConfig(&a2a.PushConfig{
		ID:     "push-1",
		TaskID: task.ID,
		URL:    "https://notify.example.test/callback",
	})
	if err != nil {
		t.Fatal(err)
	}
	created, err := client.CreateTaskPushNotificationConfig(ctx, pushRequest)
	if err != nil {
		t.Fatalf("CreateTaskPushNotificationConfig: %v", err)
	}
	if created.GetId() != "push-1" || created.GetUrl() != pushRequest.GetUrl() {
		t.Fatalf("created push config = %v", created)
	}
	getPush, err := pbconv.ToProtoGetTaskPushConfigRequest(&a2a.GetTaskPushConfigRequest{TaskID: task.ID, ID: "push-1"})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.GetTaskPushNotificationConfig(ctx, getPush); err != nil {
		t.Fatalf("GetTaskPushNotificationConfig: %v", err)
	}
	listPush, err := pbconv.ToProtoListTaskPushConfigRequest(&a2a.ListTaskPushConfigRequest{TaskID: task.ID})
	if err != nil {
		t.Fatal(err)
	}
	listed, err := client.ListTaskPushNotificationConfigs(ctx, listPush)
	if err != nil || len(listed.GetConfigs()) != 1 {
		t.Fatalf("ListTaskPushNotificationConfigs = %v, err=%v", listed, err)
	}
	deletePush, err := pbconv.ToProtoDeleteTaskPushConfigRequest(&a2a.DeleteTaskPushConfigRequest{TaskID: task.ID, ID: "push-1"})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.DeleteTaskPushNotificationConfig(ctx, deletePush); err != nil {
		t.Fatalf("DeleteTaskPushNotificationConfig: %v", err)
	}

	largeRequest, err := pbconv.ToProtoSendMessageRequest(grpcTestMessage("message-large", strings.Repeat("x", 2<<10)))
	if err != nil {
		t.Fatal(err)
	}
	// The default server bound the message at 256 KiB; this call proves the
	// successful path did not rely on an artificially small test limit.
	if _, err := client.SendMessage(ctx, largeRequest); err != nil {
		t.Fatalf("bounded 2 KiB SendMessage: %v", err)
	}
}

func TestInboundA2AGRPCCancellationAndReceiveLimit(t *testing.T) {
	started := make(chan struct{})
	canceled := make(chan struct{})
	handler := NewInboundA2AHandler(nil, nil)
	handler.SetA2AExecutionResolver(A2AExecutionResolverFunc(func(ctx context.Context, _ A2AExecutionInput) (A2AExecutionResult, error) {
		close(started)
		<-ctx.Done()
		close(canceled)
		return A2AExecutionResult{}, ctx.Err()
	}))
	client, closeServer := startA2AGRPCBufconn(t, handler, A2AGRPCOptions{Authenticator: grpcTestAuthenticator})
	defer closeServer()

	ctx, cancel := context.WithCancel(grpcTestContext("tenant-a"))
	callDone := make(chan error, 1)
	request, err := pbconv.ToProtoSendMessageRequest(grpcTestMessage("message-cancel", "wait"))
	if err != nil {
		t.Fatal(err)
	}
	go func() {
		_, callErr := client.SendMessage(ctx, request)
		callDone <- callErr
	}()
	select {
	case <-started:
	case <-time.After(2 * time.Second):
		t.Fatal("resolver was not started")
	}
	cancel()
	select {
	case <-canceled:
	case <-time.After(2 * time.Second):
		t.Fatal("resolver did not observe gRPC cancellation")
	}
	if callErr := <-callDone; callErr == nil {
		t.Fatal("canceled SendMessage succeeded")
	}

	limitHandler := NewInboundA2AHandler(nil, nil)
	limitHandler.SetA2AExecutionResolver(A2AExecutionResolverFunc(func(context.Context, A2AExecutionInput) (A2AExecutionResult, error) {
		return A2AExecutionResult{Handled: true, MessageText: "unexpected"}, nil
	}))
	limitedClient, closeLimited := startA2AGRPCBufconn(t, limitHandler, A2AGRPCOptions{
		Authenticator: grpcTestAuthenticator,
		MaxRecvBytes:  1024,
	})
	defer closeLimited()
	tooLarge, err := pbconv.ToProtoSendMessageRequest(grpcTestMessage("message-too-large", strings.Repeat("x", 2<<10)))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := limitedClient.SendMessage(grpcTestContext("tenant-a"), tooLarge); status.Code(err) != codes.ResourceExhausted {
		t.Fatalf("oversized SendMessage code = %s, want ResourceExhausted", status.Code(err))
	}
}

func TestInboundA2AGRPCCardHealthGate(t *testing.T) {
	handler := NewInboundA2AHandler(nil, nil)
	_, err := handler.NewA2AGRPCServer(A2AGRPCOptions{
		Endpoint:      "grpcs://agent.example.test/a2a",
		Authenticator: grpcTestAuthenticator,
		Health:        func(context.Context) bool { return true },
	})
	if err != nil {
		t.Fatal(err)
	}
	if hasGRPCInterface(handler.agentCardRecord("https://agent.example.test")) {
		t.Fatal("gRPC card interface advertised before server readiness")
	}
	handler.SetA2AGRPCReady(true)
	if !hasGRPCInterface(handler.agentCardRecord("https://agent.example.test")) {
		t.Fatal("healthy running gRPC server was not advertised")
	}
	handler.SetA2AGRPCReady(false)
	if hasGRPCInterface(handler.agentCardRecord("https://agent.example.test")) {
		t.Fatal("gRPC card interface remained advertised after readiness was cleared")
	}
}

type grpcTestPushDelivery struct{}

func (grpcTestPushDelivery) Deliver(context.Context, a2apush.DeliveryRequest) error { return nil }

func grpcTestAuthenticator(_ context.Context, md metadata.MD) (authorityepoch.Principal, authorityepoch.Reference, error) {
	values := md.Get("authorization")
	if len(values) != 1 || !strings.HasPrefix(values[0], "Bearer tenant-") {
		return authorityepoch.Principal{}, authorityepoch.Reference{}, errors.New("missing test credential")
	}
	tenant := strings.TrimPrefix(values[0], "Bearer ")
	return authorityepoch.Principal{Tenant: tenant, Issuer: "test-issuer", Subject: "test-subject"}, authorityepoch.Reference{}, nil
}

func grpcTestContext(tenant string) context.Context {
	return metadata.NewOutgoingContext(context.Background(), metadata.Pairs("authorization", "Bearer "+tenant))
}

func grpcTestMessage(id, text string) *a2a.SendMessageRequest {
	message := a2a.NewMessage(a2a.MessageRoleUser, a2a.NewTextPart(text))
	message.ID = id
	return &a2a.SendMessageRequest{Message: message}
}

func startA2AGRPCBufconn(t *testing.T, handler *InboundA2AHandler, options A2AGRPCOptions) (a2apb.A2AServiceClient, func()) {
	t.Helper()
	server, err := handler.NewA2AGRPCServer(options)
	if err != nil {
		t.Fatal(err)
	}
	listener := bufconn.Listen(maxA2AGRPCMessageBytes)
	serveDone := make(chan error, 1)
	go func() { serveDone <- server.Serve(listener) }()
	handler.SetA2AGRPCReady(true)
	conn, err := grpc.NewClient("passthrough:///bufnet", grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) {
		return listener.Dial()
	}), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		server.Stop()
		_ = listener.Close()
		t.Fatal(err)
	}
	return a2apb.NewA2AServiceClient(conn), func() {
		handler.SetA2AGRPCReady(false)
		_ = conn.Close()
		server.GracefulStop()
		_ = listener.Close()
		select {
		case <-serveDone:
		case <-time.After(2 * time.Second):
			server.Stop()
			t.Errorf("gRPC server did not stop")
		}
	}
}

func hasGRPCInterface(record inbound.Record) bool {
	for _, iface := range record.Card.Interfaces {
		if iface.Transport == a2adiscovery.TransportGRPC {
			return true
		}
	}
	return false
}
