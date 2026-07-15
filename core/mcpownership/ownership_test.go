package mcpownership

import (
	"errors"
	"testing"
	"time"
)

func TestFencedOwnershipRejectsStalePodAfterPodLoss(t *testing.T) {
	reg := NewRegistry()
	now := time.Unix(100, 0)
	ttl := 5 * time.Second
	key := ConnectionKey{ClientID: "jira", Principal: "vk:team-a", SessionKey: "server-session"}

	claimA, err := reg.Claim(now, key, "pod-a", ttl)
	if err != nil {
		t.Fatalf("claim pod-a: %v", err)
	}
	if claimA.Fence != 1 || claimA.Reconnect.Action != ReconnectFresh {
		t.Fatalf("claimA = %+v, want fence 1 fresh reconnect", claimA)
	}
	if err := reg.AttachServerSession(now, key, "pod-a", claimA.Fence, "srv-123", true); err != nil {
		t.Fatalf("attach server session: %v", err)
	}
	startA, err := reg.StartCall(now.Add(time.Second), key, "pod-a", claimA.Fence, "op-1")
	if err != nil {
		t.Fatalf("start call pod-a: %v", err)
	}
	if startA.Status != OperationPending || startA.Attempt != 1 {
		t.Fatalf("startA = %+v, want first pending attempt", startA)
	}

	claimB, err := reg.Claim(now.Add(6*time.Second), key, "pod-b", ttl)
	if err != nil {
		t.Fatalf("claim pod-b after lease expiry: %v", err)
	}
	if claimB.Fence != 2 {
		t.Fatalf("claimB fence = %d, want 2", claimB.Fence)
	}
	if claimB.Reconnect.Action != ReconnectResume || claimB.Reconnect.ServerSessionID != "srv-123" {
		t.Fatalf("claimB reconnect = %+v, want resumable server session", claimB.Reconnect)
	}
	if got := claimB.Reconnect.AmbiguousOperations; len(got) != 1 || got[0] != "op-1" {
		t.Fatalf("ambiguous operations = %#v, want [op-1]", got)
	}

	_, err = reg.CompleteCall(now.Add(6*time.Second), key, "pod-a", claimA.Fence, "op-1", true)
	if !errors.Is(err, ErrStaleFence) {
		t.Fatalf("stale completion err = %v, want ErrStaleFence", err)
	}

	startB, err := reg.StartCall(now.Add(7*time.Second), key, "pod-b", claimB.Fence, "op-1")
	if err != nil {
		t.Fatalf("restart ambiguous op on pod-b: %v", err)
	}
	if !startB.AmbiguousPrevious || startB.Attempt != 2 || startB.Status != OperationPending {
		t.Fatalf("startB = %+v, want second pending attempt with ambiguous previous", startB)
	}
	doneB, err := reg.CompleteCall(now.Add(8*time.Second), key, "pod-b", claimB.Fence, "op-1", true)
	if err != nil {
		t.Fatalf("complete pod-b: %v", err)
	}
	if doneB.Status != OperationSucceeded || !doneB.AmbiguousPrevious {
		t.Fatalf("doneB = %+v, want succeeded with ambiguous history", doneB)
	}
}

func TestLiveOwnerPreventsSplitBrain(t *testing.T) {
	reg := NewRegistry()
	now := time.Unix(200, 0)
	key := ConnectionKey{ClientID: "github", Principal: "user:42", SessionKey: "oauth"}

	claimA, err := reg.Claim(now, key, "pod-a", 10*time.Second)
	if err != nil {
		t.Fatalf("claim pod-a: %v", err)
	}
	claimAgain, err := reg.Claim(now.Add(time.Second), key, "pod-a", 10*time.Second)
	if err != nil {
		t.Fatalf("idempotent same-pod claim: %v", err)
	}
	if claimAgain.Fence != claimA.Fence || claimAgain.Reconnect.Action != ReconnectNone {
		t.Fatalf("same-pod claim = %+v, want same fence and no reconnect", claimAgain)
	}

	_, err = reg.Claim(now.Add(2*time.Second), key, "pod-b", 10*time.Second)
	if !errors.Is(err, ErrAlreadyOwned) {
		t.Fatalf("competing claim err = %v, want ErrAlreadyOwned", err)
	}
}

func TestOAuthCallbackRoutesToCurrentOwnerAfterReclaim(t *testing.T) {
	reg := NewRegistry()
	now := time.Unix(300, 0)
	key := ConnectionKey{ClientID: "linear", Principal: "user:7", SessionKey: "oauth"}

	claimA, err := reg.Claim(now, key, "pod-a", 5*time.Second)
	if err != nil {
		t.Fatalf("claim pod-a: %v", err)
	}
	if err := reg.BeginOAuth(now, key, "pod-a", claimA.Fence, "state-1", time.Minute); err != nil {
		t.Fatalf("begin oauth: %v", err)
	}

	routeA, err := reg.RouteOAuthCallback(now.Add(time.Second), "state-1")
	if err != nil {
		t.Fatalf("route oauth to pod-a: %v", err)
	}
	if routeA.OwnerPod != "pod-a" || routeA.Fence != claimA.Fence {
		t.Fatalf("routeA = %+v, want pod-a fence %d", routeA, claimA.Fence)
	}

	claimB, err := reg.Claim(now.Add(6*time.Second), key, "pod-b", 5*time.Second)
	if err != nil {
		t.Fatalf("claim pod-b: %v", err)
	}
	routeB, err := reg.RouteOAuthCallback(now.Add(7*time.Second), "state-1")
	if err != nil {
		t.Fatalf("route oauth to pod-b: %v", err)
	}
	if routeB.OwnerPod != "pod-b" || routeB.Fence != claimB.Fence {
		t.Fatalf("routeB = %+v, want pod-b fence %d", routeB, claimB.Fence)
	}
}

func TestNonResumableServerSessionStartsFreshButPreservesAmbiguity(t *testing.T) {
	reg := NewRegistry()
	now := time.Unix(400, 0)
	key := ConnectionKey{ClientID: "stdio-tool", Principal: "team:ops", SessionKey: "shared"}

	claimA, err := reg.Claim(now, key, "pod-a", 5*time.Second)
	if err != nil {
		t.Fatalf("claim pod-a: %v", err)
	}
	if err := reg.AttachServerSession(now, key, "pod-a", claimA.Fence, "stdio-pid-99", false); err != nil {
		t.Fatalf("attach non-resumable session: %v", err)
	}
	if _, err := reg.StartCall(now.Add(time.Second), key, "pod-a", claimA.Fence, "mutation-1"); err != nil {
		t.Fatalf("start mutation: %v", err)
	}

	claimB, err := reg.Claim(now.Add(6*time.Second), key, "pod-b", 5*time.Second)
	if err != nil {
		t.Fatalf("claim pod-b: %v", err)
	}
	if claimB.Reconnect.Action != ReconnectFresh {
		t.Fatalf("reconnect action = %s, want fresh for non-resumable session", claimB.Reconnect.Action)
	}
	if got := reg.Operations(key); len(got) != 1 || got[0].ID != "mutation-1" || got[0].Status != OperationAmbiguous || !got[0].Ambiguous {
		t.Fatalf("operations = %+v, want ambiguous mutation", got)
	}
}

func TestRenewRequiresCurrentFence(t *testing.T) {
	reg := NewRegistry()
	now := time.Unix(500, 0)
	key := ConnectionKey{ClientID: "calendar", Principal: "vk:finance", SessionKey: "shared"}

	claimA, err := reg.Claim(now, key, "pod-a", 5*time.Second)
	if err != nil {
		t.Fatalf("claim pod-a: %v", err)
	}
	claimB, err := reg.Claim(now.Add(6*time.Second), key, "pod-b", 5*time.Second)
	if err != nil {
		t.Fatalf("claim pod-b: %v", err)
	}

	_, err = reg.Renew(now.Add(7*time.Second), key, "pod-a", claimA.Fence, 5*time.Second)
	if !errors.Is(err, ErrStaleFence) {
		t.Fatalf("stale renew err = %v, want ErrStaleFence", err)
	}

	renewed, err := reg.Renew(now.Add(7*time.Second), key, "pod-b", claimB.Fence, 10*time.Second)
	if err != nil {
		t.Fatalf("renew pod-b: %v", err)
	}
	if !renewed.LeaseUntil.Equal(now.Add(17 * time.Second)) {
		t.Fatalf("renewed lease = %s, want %s", renewed.LeaseUntil, now.Add(17*time.Second))
	}
}
