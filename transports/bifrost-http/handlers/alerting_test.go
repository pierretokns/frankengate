package handlers

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
)

type alertingConfigStoreStub struct {
	configstore.ConfigStore
	row *tables.TableGovernanceConfig
}

func (s *alertingConfigStoreStub) GetConfig(_ context.Context, _ string) (*tables.TableGovernanceConfig, error) {
	return s.row, nil
}

func TestValidAlertChannelType(t *testing.T) {
	for _, kind := range []string{"webhook", "SNS", "email"} {
		if !validAlertChannelType(kind) {
			t.Fatalf("expected channel type %q to be accepted", kind)
		}
	}
	for _, kind := range []string{"", "slack", "pagerduty"} {
		if validAlertChannelType(kind) {
			t.Fatalf("expected channel type %q to be rejected", kind)
		}
	}
}

func TestLoadAlertingWebhookConfigProjectsEnabledWebhook(t *testing.T) {
	store := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[{"type":"sns","enabled":true,"config":{"url":"https://sns.invalid"}},{"type":"webhook","enabled":true,"config":{"url":"https://alerts.invalid/hook","signing_key":"k","buffer":"9"}}]}`}}
	got, ok, err := LoadAlertingWebhookConfig(context.Background(), store)
	if err != nil || !ok {
		t.Fatalf("projection failed: ok=%v err=%v", ok, err)
	}
	if got.URL != "https://alerts.invalid/hook" || got.SigningKey != "k" || got.Buffer != 9 {
		t.Fatalf("unexpected projection: %+v", got)
	}
}

func TestLoadAlertingWebhookConfigIgnoresUnsupportedOrInvalidChannels(t *testing.T) {
	store := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[{"type":"sns","enabled":true,"config":{"url":"https://sns.invalid"}},{"type":"webhook","enabled":true,"config":{"url":"file:///not-a-webhook"}}]}`}}
	if _, ok, err := LoadAlertingWebhookConfig(context.Background(), store); err != nil || ok {
		t.Fatalf("expected no projected notifier, ok=%v err=%v", ok, err)
	}
}
