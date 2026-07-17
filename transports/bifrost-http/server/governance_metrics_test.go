package server

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/plugins/governance"
)

type recordingGovernanceSink struct{ reservations, overdrafts, notifications int }

func (s *recordingGovernanceSink) ReservationObserved(context.Context, string, reservations.Amount) {
	s.reservations++
}
func (s *recordingGovernanceSink) OverdraftObserved(context.Context, bool, reservations.Amount) {
	s.overdrafts++
}
func (s *recordingGovernanceSink) NotifierObserved(context.Context, string) { s.notifications++ }

func TestGovernanceMetricsFanoutDeliversEveryEventToEverySink(t *testing.T) {
	left, right := &recordingGovernanceSink{}, &recordingGovernanceSink{}
	fanout := governanceMetricsFanout([]governance.MetricsSink{left, right})
	ctx := context.Background()
	fanout.ReservationObserved(ctx, "accepted", reservations.Amount{Tokens: 1})
	fanout.OverdraftObserved(ctx, true, reservations.Amount{Tokens: 2})
	fanout.NotifierObserved(ctx, "delivered")
	for name, sink := range map[string]*recordingGovernanceSink{"left": left, "right": right} {
		if sink.reservations != 1 || sink.overdrafts != 1 || sink.notifications != 1 {
			t.Fatalf("%s sink counts = %+v, want one of each", name, sink)
		}
	}
}
