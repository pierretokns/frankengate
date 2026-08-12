package server

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/transports/bifrost-http/handlers"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/test/bufconn"
)

func TestStartAndStopA2AGRPCOwnsListenerAndGracefullyStops(t *testing.T) {
	handler := handlers.NewInboundA2AHandler(nil, nil)
	server := &BifrostHTTPServer{inboundA2AHandler: handler}
	listener := bufconn.Listen(256 * 1024)
	if err := server.StartA2AGRPC(listener, handlers.A2AGRPCOptions{
		Endpoint:      "bufnet",
		Authenticator: lifecycleTestAuthenticator,
		Health:        func(context.Context) bool { return true },
	}); err != nil {
		t.Fatalf("StartA2AGRPC: %v", err)
	}
	if server.a2aGRPCServer == nil || server.a2aGRPCListener != listener {
		t.Fatal("StartA2AGRPC did not retain its server and listener")
	}
	server.StopA2AGRPC()
	if server.a2aGRPCServer != nil || server.a2aGRPCListener != nil {
		t.Fatal("StopA2AGRPC did not release its server and listener")
	}
}

func lifecycleTestAuthenticator(_ context.Context, _ metadata.MD) (authorityepoch.Principal, authorityepoch.Reference, error) {
	return authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer", Subject: "subject"}, authorityepoch.Reference{}, nil
}
