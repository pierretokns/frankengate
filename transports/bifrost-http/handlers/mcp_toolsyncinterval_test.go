package handlers

import (
	"testing"
	"time"
)

func TestToolSyncIntervalBoundsRejectNanosecondScaleValues(t *testing.T) {
	for _, interval := range []time.Duration{time.Minute, 10 * time.Minute, time.Hour, -time.Minute} {
		minutes := int64(interval)
		if minutes <= maxToolSyncIntervalMinutes && minutes >= minToolSyncIntervalMinutes {
			t.Fatalf("nanosecond-valued interval %d for %v was not rejected", minutes, interval)
		}
	}
}

func TestToolSyncIntervalBoundsAcceptRealisticValues(t *testing.T) {
	for _, minutes := range []int64{-1, 0, 1, 10, 60, 1440, 525600} {
		if minutes > maxToolSyncIntervalMinutes || minutes < minToolSyncIntervalMinutes {
			t.Fatalf("realistic interval %d was rejected", minutes)
		}
	}
}

func TestToolSyncIntervalBoundsPreventOverflow(t *testing.T) {
	for _, minutes := range []int64{minToolSyncIntervalMinutes, -1, 0, 1, maxToolSyncIntervalMinutes} {
		got := time.Duration(minutes) * time.Minute
		if minutes > 0 && got < 0 || minutes < 0 && got > 0 {
			t.Fatalf("accepted interval %d overflowed to %v", minutes, got)
		}
	}
}
