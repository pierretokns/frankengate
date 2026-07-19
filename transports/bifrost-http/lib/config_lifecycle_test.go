package lib

import (
	"context"
	"testing"
)

func TestConfigCloseCancelsOwnedLifecycle(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	c := &Config{lifecycleCancel: cancel}
	c.Close(context.Background())
	select {
	case <-ctx.Done():
	default:
		t.Fatal("Config.Close did not cancel the owned lifecycle context")
	}
	if c.lifecycleCancel != nil {
		t.Fatal("Config.Close retained the lifecycle cancel function")
	}
}
