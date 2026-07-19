package handlers

import (
	"context"
	"strings"
	"testing"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
	"gorm.io/gorm"
)

type alertingConfigStoreStub struct {
	configstore.ConfigStore
	row *tables.TableGovernanceConfig
}

func (s *alertingConfigStoreStub) GetConfig(_ context.Context, _ string) (*tables.TableGovernanceConfig, error) {
	return s.row, nil
}

func (s *alertingConfigStoreStub) UpdateConfig(_ context.Context, row *tables.TableGovernanceConfig, _ ...*gorm.DB) error {
	s.row = row
	return nil
}

func TestAlertingMutationInvokesHotRefreshCallbackAfterCommit(t *testing.T) {
	store := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[],"rules":[],"history":[]` + "}"}}
	h := NewAlertingHandler(store)
	called := 0
	h.SetOnChanged(func() { called++ })
	ctx := &fasthttp.RequestCtx{}
	h.mutate(ctx, func(state *alertingState) {
		state.Channels = append(state.Channels, AlertChannel{ID: "a", Name: "ops", Type: "webhook", Enabled: true})
	})
	if called != 1 {
		t.Fatalf("expected one hot-refresh callback after commit, got %d", called)
	}
	if !strings.Contains(store.row.Value, `"ops"`) {
		t.Fatalf("mutation was not persisted: %s", store.row.Value)
	}
}

func TestValidAlertChannelType(t *testing.T) {
	for _, kind := range []string{"webhook", "SNS", "email", "cloudflare_email"} {
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

func TestLoadAlertingNativeChannelConfigsFailClosed(t *testing.T) {
	store := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[{"type":"sns","enabled":true,"config":{"topic_arn":"arn:aws:sns:us-east-1:1:alerts","subject":"ops","region":"us-east-1","buffer":"4"}},{"type":"email","enabled":true,"config":{"from":"alerts@example.com","recipients":"ops@example.com, oncall@example.com","region":"us-west-2","buffer":"7"}},{"type":"cloudflare_email","enabled":true,"config":{"account_id":"acct","api_token":"secret","from":"alerts@example.com","recipients":"ops@example.com","subject":"ops","buffer":"8"}}]}`}}
	sns, ok, err := LoadAlertingSNSConfig(context.Background(), store)
	if err != nil || !ok || sns.TopicARN == "" || sns.Region != "us-east-1" || sns.Buffer != 4 {
		t.Fatalf("unexpected SNS config: %+v ok=%v err=%v", sns, ok, err)
	}
	email, ok, err := LoadAlertingEmailConfig(context.Background(), store)
	if err != nil || !ok || email.From == "" || email.Region != "us-west-2" || len(email.Recipients) != 2 || email.Buffer != 7 {
		t.Fatalf("unexpected email config: %+v ok=%v err=%v", email, ok, err)
	}
	cf, ok, err := LoadAlertingCloudflareEmailConfig(context.Background(), store)
	if err != nil || !ok || cf.AccountID != "acct" || cf.APIToken != "secret" || len(cf.Recipients) != 1 || cf.Buffer != 8 {
		t.Fatalf("unexpected Cloudflare email config: %+v ok=%v err=%v", cf, ok, err)
	}
	invalid := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[{"type":"sns","enabled":true,"config":{"topic_arn":"https://not-an-arn"}},{"type":"email","enabled":true,"config":{"from":"","recipients":""}}]}`}}
	if _, ok, err := LoadAlertingSNSConfig(context.Background(), invalid); err != nil || ok {
		t.Fatalf("invalid SNS config should fail closed: ok=%v err=%v", ok, err)
	}
	if _, ok, err := LoadAlertingEmailConfig(context.Background(), invalid); err != nil || ok {
		t.Fatalf("invalid email config should fail closed: ok=%v err=%v", ok, err)
	}
}

func TestNormalizeAlertingStateRemovesDanglingAndDuplicateChannels(t *testing.T) {
	state := alertingState{
		Channels: []AlertChannel{{ID: "ops"}},
		Rules:    []AlertRule{{ChannelIDs: []string{"ops", "missing", "ops"}}},
	}
	normalizeAlertingState(&state)
	if got := strings.Join(state.Rules[0].ChannelIDs, ","); got != "ops" {
		t.Fatalf("expected only the live channel once, got %q", got)
	}
}

func TestPublicAlertingStateRedactsChannelSecrets(t *testing.T) {
	state := alertingState{Channels: []AlertChannel{{ID: "cf", Config: map[string]string{
		"api_token": "real-token", "signing_key": "real-signing-key", "from": "alerts@example.com",
	}}}}
	public := publicAlertingState(state)
	if public.Channels[0].Config["api_token"] != redactedAlertSecret || public.Channels[0].Config["signing_key"] != redactedAlertSecret {
		t.Fatalf("channel secrets were not redacted: %#v", public.Channels[0].Config)
	}
	if public.Channels[0].Config["from"] != "alerts@example.com" || state.Channels[0].Config["api_token"] != "real-token" {
		t.Fatalf("redaction mutated state or non-secret fields: public=%#v state=%#v", public.Channels[0].Config, state.Channels[0].Config)
	}
}

func TestPreserveAlertChannelSecretsOnRedactedUpdate(t *testing.T) {
	existing := AlertChannel{Config: map[string]string{"api_token": "real-token", "signing_key": "real-signing"}}
	incoming := AlertChannel{Config: map[string]string{"api_token": redactedAlertSecret, "signing_key": "", "from": "alerts@example.com"}}
	merged := preserveAlertChannelSecrets(existing, incoming)
	if merged.Config["api_token"] != "real-token" || merged.Config["signing_key"] != "real-signing" || merged.Config["from"] != "alerts@example.com" {
		t.Fatalf("secret preservation failed: %#v", merged.Config)
	}
}

func TestAlertingMutationRepairsDanglingRuleReferences(t *testing.T) {
	store := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[{"id":"ops"}],"rules":[{"id":"r","channel_ids":["missing"]}]}`}}
	h := NewAlertingHandler(store)
	ctx := &fasthttp.RequestCtx{}
	h.mutate(ctx, func(state *alertingState) { state.History = append(state.History, AlertDelivery{ID: "d"}) })
	state, ok, err := loadAlertingState(context.Background(), store)
	if err != nil || !ok || len(state.Rules) != 1 || len(state.Rules[0].ChannelIDs) != 0 {
		t.Fatalf("expected repaired durable state: state=%+v ok=%v err=%v", state, ok, err)
	}
}

func TestAlertingRoutesExposeDurableCRUDSurface(t *testing.T) {
	store := &alertingConfigStoreStub{row: &tables.TableGovernanceConfig{Value: `{"channels":[],"rules":[],"history":[]}`}}
	r := router.New()
	NewAlertingHandler(store).RegisterRoutes(r)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetMethod(fasthttp.MethodPost)
	ctx.Request.SetRequestURI("/api/alerting/channels")
	ctx.Request.SetBodyString(`{"name":"ops","type":"webhook","enabled":true,"config":{"url":"https://alerts.invalid/hook"}}`)
	r.Handler(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("create channel route returned %d: %s", ctx.Response.StatusCode(), ctx.Response.Body())
	}

	ctx.Response.Reset()
	ctx.Request.Header.SetMethod(fasthttp.MethodGet)
	ctx.Request.SetRequestURI("/api/alerting/channels")
	ctx.Request.SetBody(nil)
	r.Handler(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusOK || !strings.Contains(string(ctx.Response.Body()), `"ops"`) {
		t.Fatalf("list channels route returned %d: %s", ctx.Response.StatusCode(), ctx.Response.Body())
	}
}
