package otel

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/reservations"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/metric/metricdata"
)

func TestGovernanceMetricsAreInitializedAndRecordable(t *testing.T) {
	reader := sdkmetric.NewManualReader()
	provider := sdkmetric.NewMeterProvider(sdkmetric.WithReader(reader))
	defer provider.Shutdown(context.Background())

	exporter := &MetricsExporter{provider: provider, meter: provider.Meter("frankengate-test")}
	exporter.initMetrics()

	ctx := context.Background()
	exporter.ReservationObserved(ctx, "accepted", reservations.Amount{Tokens: 12})
	exporter.OverdraftObserved(ctx, true, reservations.Amount{Tokens: 3})
	exporter.NotifierObserved(ctx, "success")

	for name, instrument := range map[string]any{
		"reservations":        exporter.governanceReservationsTotal,
		"reservation_tokens":  exporter.governanceReservationTokensTotal,
		"overdrafts":          exporter.governanceOverdraftsTotal,
		"overdraft_tokens":    exporter.governanceOverdraftTokensTotal,
		"notifier_deliveries": exporter.governanceNotifierDeliveriesTotal,
	} {
		if instrument == nil {
			t.Fatalf("governance %s instrument was not initialized", name)
		}
	}

	var metrics metricdata.ResourceMetrics
	if err := reader.Collect(ctx, &metrics); err != nil {
		t.Fatalf("collect governance metrics: %v", err)
	}
	want := map[string]bool{
		"bifrost_governance_reservations_total":        false,
		"bifrost_governance_reserved_tokens_total":     false,
		"bifrost_governance_overdrafts_total":          false,
		"bifrost_governance_overdraft_tokens_total":    false,
		"bifrost_governance_notifier_deliveries_total": false,
	}
	for _, scope := range metrics.ScopeMetrics {
		for _, metric := range scope.Metrics {
			if _, ok := want[metric.Name]; ok {
				want[metric.Name] = true
			}
		}
	}
	for name, found := range want {
		if !found {
			t.Errorf("collected metrics missing %s", name)
		}
	}
}
