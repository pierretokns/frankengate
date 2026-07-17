package otel

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/reservations"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
)

func TestGovernanceMetricsAreInitializedAndRecordable(t *testing.T) {
	provider := sdkmetric.NewMeterProvider()
	defer provider.Shutdown(context.Background())

	exporter := &MetricsExporter{provider: provider, meter: provider.Meter("frankengate-test")}
	exporter.initMetrics()

	ctx := context.Background()
	exporter.ReservationObserved(ctx, "accepted", reservations.Amount{Tokens: 12})
	exporter.OverdraftObserved(ctx, true, reservations.Amount{Tokens: 3})
	exporter.NotifierObserved(ctx, "success")

	for name, instrument := range map[string]any{
		"reservations": exporter.governanceReservationsTotal,
		"reservation_tokens": exporter.governanceReservationTokensTotal,
		"overdrafts": exporter.governanceOverdraftsTotal,
		"overdraft_tokens": exporter.governanceOverdraftTokensTotal,
		"notifier_deliveries": exporter.governanceNotifierDeliveriesTotal,
	} {
		if instrument == nil {
			t.Fatalf("governance %s instrument was not initialized", name)
		}
	}
}
