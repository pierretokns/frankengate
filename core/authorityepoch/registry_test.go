package authorityepoch

import (
	"errors"
	"testing"
)

func TestMintedReferencesAreBoundToPrincipalAndEpoch(t *testing.T) {
	reg := NewRegistry()
	principal := Principal{
		Tenant:  "tenant-a",
		Issuer:  "https://okta.example.com/oauth2/default",
		Subject: "00u123",
	}

	if err := reg.Activate(principal, 1); err != nil {
		t.Fatalf("activate principal: %v", err)
	}

	ref, err := reg.Mint(principal, ArtifactUnary, "req-1")
	if err != nil {
		t.Fatalf("mint unary reference: %v", err)
	}
	if ref.Principal != principal || ref.Epoch != 1 || ref.Kind != ArtifactUnary || ref.ID != "req-1" {
		t.Fatalf("reference = %+v, want principal-bound unary epoch 1", ref)
	}
	if err := reg.Validate(ref); err != nil {
		t.Fatalf("validate minted reference: %v", err)
	}

	tampered := ref
	tampered.Principal.Issuer = "https://other-issuer.example.com"
	if err := reg.Validate(tampered); err == nil {
		t.Fatal("tampered issuer validated; want fail-closed rejection")
	}
}

func TestGroupRemovalCancelsArtifactsWithinLogicalSLO(t *testing.T) {
	reg := NewRegistry()
	principal := Principal{
		Tenant:  "tenant-a",
		Issuer:  "https://okta.example.com/oauth2/default",
		Subject: "00u123",
	}
	if err := reg.Activate(principal, 1); err != nil {
		t.Fatalf("activate principal: %v", err)
	}

	kinds := []ArtifactKind{
		ArtifactUnary,
		ArtifactSSE,
		ArtifactWebSocket,
		ArtifactQueued,
		ArtifactKey,
		ArtifactCache,
		ArtifactMCPGrant,
		ArtifactMCPLiveConnection,
	}
	refs := make([]Reference, 0, len(kinds))
	cancellations := make([]<-chan Cancellation, 0, len(kinds))
	for _, kind := range kinds {
		ref, err := reg.Mint(principal, kind, string(kind)+"-artifact")
		if err != nil {
			t.Fatalf("mint %s: %v", kind, err)
		}
		cancelled, unsubscribe, err := reg.Subscribe(ref)
		if err != nil {
			t.Fatalf("subscribe %s: %v", kind, err)
		}
		defer unsubscribe()
		refs = append(refs, ref)
		cancellations = append(cancellations, cancelled)
	}

	event, err := reg.AdvanceEpoch(principal, ReasonGroupRemoved)
	if err != nil {
		t.Fatalf("advance epoch: %v", err)
	}
	if event.NewEpoch != 2 || event.Reason != ReasonGroupRemoved {
		t.Fatalf("event = %+v, want group-removal epoch 2", event)
	}

	for i, ref := range refs {
		if err := reg.Validate(ref); err == nil {
			t.Fatalf("%s stale reference validated; want fail-closed rejection", ref.Kind)
		}
		select {
		case cancellation := <-cancellations[i]:
			if cancellation.Reference != ref {
				t.Fatalf("cancellation ref = %+v, want %+v", cancellation.Reference, ref)
			}
			if cancellation.Reason != ReasonGroupRemoved {
				t.Fatalf("cancellation reason = %s, want %s", cancellation.Reason, ReasonGroupRemoved)
			}
			if cancellation.Revision > cancellation.DeadlineRevision {
				t.Fatalf("cancellation revision %d exceeded deadline %d", cancellation.Revision, cancellation.DeadlineRevision)
			}
		default:
			t.Fatalf("%s did not receive synchronous cancellation", ref.Kind)
		}
	}

	newRef, err := reg.Mint(principal, ArtifactUnary, "req-2")
	if err != nil {
		t.Fatalf("mint after group removal: %v", err)
	}
	if newRef.Epoch != 2 {
		t.Fatalf("newRef epoch = %d, want 2", newRef.Epoch)
	}
}

func TestValidationFailsClosedForUnknownMalformedAndStaleReferences(t *testing.T) {
	reg := NewRegistry()
	principal := Principal{
		Tenant:  "tenant-a",
		Issuer:  "https://okta.example.com/oauth2/default",
		Subject: "00u789",
	}

	if err := reg.Validate(Reference{Principal: principal, Epoch: 1, Kind: ArtifactUnary, ID: "req-1"}); !errors.Is(err, ErrUnknownPrincipal) {
		t.Fatalf("unknown principal err = %v, want ErrUnknownPrincipal", err)
	}
	if err := reg.Activate(Principal{Tenant: "tenant-a"}, 1); !errors.Is(err, ErrInvalidPrincipal) {
		t.Fatalf("malformed activate err = %v, want ErrInvalidPrincipal", err)
	}
	if err := reg.Activate(principal, 1); err != nil {
		t.Fatalf("activate principal: %v", err)
	}
	if err := reg.Validate(Reference{Principal: principal, Epoch: 1, Kind: ArtifactKind("unknown"), ID: "x"}); err == nil {
		t.Fatal("unknown artifact kind validated; want fail-closed rejection")
	}
	if err := reg.Validate(Reference{Principal: principal, Epoch: 0, Kind: ArtifactUnary, ID: "x"}); !errors.Is(err, ErrInvalidReference) {
		t.Fatalf("zero epoch err = %v, want ErrInvalidReference", err)
	}

	ref, err := reg.Mint(principal, ArtifactQueued, "job-1")
	if err != nil {
		t.Fatalf("mint queued job: %v", err)
	}
	if _, err := reg.AdvanceEpoch(principal, ReasonGroupRemoved); err != nil {
		t.Fatalf("advance epoch: %v", err)
	}
	if _, _, err := reg.Subscribe(ref); !errors.Is(err, ErrStaleEpoch) {
		t.Fatalf("subscribe stale ref err = %v, want ErrStaleEpoch", err)
	}
}

func TestDeactivationInvalidatesAndStaleEpochsNeverRevive(t *testing.T) {
	reg := NewRegistry()
	principal := Principal{
		Tenant:  "tenant-a",
		Issuer:  "https://okta.example.com/oauth2/default",
		Subject: "00u456",
	}
	if err := reg.Activate(principal, 7); err != nil {
		t.Fatalf("activate principal: %v", err)
	}

	ref, err := reg.Mint(principal, ArtifactWebSocket, "ws-1")
	if err != nil {
		t.Fatalf("mint websocket: %v", err)
	}
	cancelled, unsubscribe, err := reg.Subscribe(ref)
	if err != nil {
		t.Fatalf("subscribe websocket: %v", err)
	}
	defer unsubscribe()

	event, err := reg.Deactivate(principal, ReasonDeactivated)
	if err != nil {
		t.Fatalf("deactivate principal: %v", err)
	}
	if event.OldEpoch != 7 || event.NewEpoch != 8 {
		t.Fatalf("event = %+v, want epoch 7 -> 8", event)
	}
	if _, err := reg.Mint(principal, ArtifactKey, "key-1"); err == nil {
		t.Fatal("mint after deactivation succeeded; want fail-closed rejection")
	}
	if err := reg.Validate(ref); err == nil {
		t.Fatal("old websocket validated after deactivation")
	}
	select {
	case cancellation := <-cancelled:
		if cancellation.Reason != ReasonDeactivated {
			t.Fatalf("cancellation reason = %s, want %s", cancellation.Reason, ReasonDeactivated)
		}
	default:
		t.Fatal("websocket did not receive deactivation cancellation")
	}

	if _, err := reg.AdvanceEpoch(principal, ReasonGroupRemoved); !errors.Is(err, ErrInactivePrincipal) {
		t.Fatalf("advance inactive principal err = %v, want ErrInactivePrincipal", err)
	}
	if _, err := reg.Mint(principal, ArtifactKey, "key-after-invalid-advance"); !errors.Is(err, ErrInactivePrincipal) {
		t.Fatalf("mint after rejected inactive advance err = %v, want ErrInactivePrincipal", err)
	}

	if err := reg.Activate(principal, 8); err == nil {
		t.Fatal("reactivation at stale epoch succeeded; want monotonic rejection")
	}
	if err := reg.Activate(principal, 9); err != nil {
		t.Fatalf("reactivate at newer epoch: %v", err)
	}
	if err := reg.Validate(ref); err == nil {
		t.Fatal("old epoch revived after reactivation")
	}
	newRef, err := reg.Mint(principal, ArtifactKey, "key-2")
	if err != nil {
		t.Fatalf("mint after newer reactivation: %v", err)
	}
	if newRef.Epoch != 9 {
		t.Fatalf("new key epoch = %d, want 9", newRef.Epoch)
	}
}
