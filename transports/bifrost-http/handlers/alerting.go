package handlers

// AlertingHandler provides the durable dashboard contract for alert channels,
// rules, and delivery history.  State is kept in ConfigStore's transactional
// governance_config table so every replica observes the same configuration;
// delivery workers remain asynchronous and are deliberately outside this
// request path.
import (
	"context"
	"fmt"
	"strings"
	"sync"

	"github.com/bytedance/sonic"
	"github.com/fasthttp/router"
	"github.com/google/uuid"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

const alertingConfigKey = "frankengate.alerting.v1"

// maxAlertHistoryEntries bounds the durable dashboard payload. Delivery
// workers may append indefinitely; retaining the entire history in one JSON
// governance row would eventually make every dashboard request and mutation
// grow without bound. Long-term retention belongs in an external audit store.
const maxAlertHistoryEntries = 1000

// AlertingWebhookConfig is the small, startup-time projection consumed by the
// governance admission notifier.  Alerting CRUD remains durable and
// asynchronous; changing a channel takes effect on the next plugin reload.
// Only webhook channels are projected until native SNS/email workers exist.
type AlertingWebhookConfig struct {
	URL        string
	SigningKey string
	Buffer     int
}

type AlertingSNSConfig struct {
	TopicARN string
	Subject  string
	Region   string
	Buffer   int
}

type AlertingEmailConfig struct {
	From       string
	Recipients []string
	Subject    string
	Region     string
	Buffer     int
}

// AlertingCloudflareEmailConfig configures Cloudflare Email Service's REST
// sender.  It is intentionally separate from SES so deployments can choose a
// provider without ambiguous credential fallback.
type AlertingCloudflareEmailConfig struct {
	AccountID  string
	APIToken   string
	From       string
	Recipients []string
	Subject    string
	Buffer     int
}

type AlertChannel struct {
	ID      string            `json:"id"`
	Name    string            `json:"name"`
	Type    string            `json:"type"`
	Config  map[string]string `json:"config,omitempty"`
	Enabled bool              `json:"enabled"`
}
type AlertRule struct {
	ID         string   `json:"id"`
	Name       string   `json:"name"`
	Event      string   `json:"event"`
	ChannelIDs []string `json:"channel_ids"`
	Enabled    bool     `json:"enabled"`
	// Scope makes alert evaluation explicit for team/user dashboards.  Empty
	// scope is treated as global for backwards-compatible rules.
	Scope   string `json:"scope,omitempty"`
	ScopeID string `json:"scope_id,omitempty"`
	// ApprovalRequired is used by controlled-overdraft rules.  An approval
	// gate is metadata only here; admission remains the source of truth.
	ApprovalRequired bool `json:"approval_required,omitempty"`
	Approved         bool `json:"approved,omitempty"`
}
type AlertDelivery struct {
	ID        string `json:"id"`
	RuleID    string `json:"rule_id"`
	Status    string `json:"status"`
	Error     string `json:"error,omitempty"`
	CreatedAt string `json:"created_at"`
}
type alertingState struct {
	Channels []AlertChannel  `json:"channels"`
	Rules    []AlertRule     `json:"rules"`
	History  []AlertDelivery `json:"history"`
}

const redactedAlertSecret = "***REDACTED***"

// isSensitiveAlertConfigKey is deliberately name-based: channel configuration
// is extensible and new providers often call credentials something other than
// "token" or "secret".  Dashboard responses must never echo those values.
func isSensitiveAlertConfigKey(key string) bool {
	lower := strings.ToLower(strings.TrimSpace(key))
	for _, marker := range []string{
		"token", "secret", "signing_key", "password", "passwd", "api_key",
		"apikey", "private_key", "credential", "authorization", "access_key",
	} {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	return false
}

// publicAlertingState prevents durable channel credentials from being echoed
// through dashboard mutation/list responses. The internal state remains
// unchanged so notifier reloads can still read the real values.
func publicAlertingState(state alertingState) alertingState {
	public := state
	public.Channels = make([]AlertChannel, len(state.Channels))
	for i, channel := range state.Channels {
		public.Channels[i] = channel
		public.Channels[i].Config = make(map[string]string, len(channel.Config))
		for key, value := range channel.Config {
			if isSensitiveAlertConfigKey(key) {
				public.Channels[i].Config[key] = redactedAlertSecret
				continue
			}
			public.Channels[i].Config[key] = value
		}
	}
	return public
}

func preserveAlertChannelSecrets(existing, incoming AlertChannel) AlertChannel {
	merged := incoming
	merged.Config = make(map[string]string, len(incoming.Config)+2)
	for key, value := range incoming.Config {
		merged.Config[key] = value
	}
	for key, value := range existing.Config {
		if !isSensitiveAlertConfigKey(key) {
			continue
		}
		if current := strings.TrimSpace(merged.Config[key]); current == "" || current == redactedAlertSecret {
			merged.Config[key] = value
		}
	}
	return merged
}

// normalizeAlertingState keeps persisted references internally consistent.
// A deleted or partially migrated channel must never remain attached to a
// rule: the notifier would otherwise report a successful rule while silently
// delivering nowhere. Unknown references are removed fail-closed.
func normalizeAlertingState(state *alertingState) {
	if len(state.History) > maxAlertHistoryEntries {
		// History is chronological (oldest first). Keep the most recent entries
		// so alert counters and the dashboard remain useful after compaction.
		state.History = append([]AlertDelivery(nil), state.History[len(state.History)-maxAlertHistoryEntries:]...)
	}
	known := make(map[string]struct{}, len(state.Channels))
	for _, channel := range state.Channels {
		if channel.ID != "" {
			known[channel.ID] = struct{}{}
		}
	}
	for i := range state.Rules {
		ids := state.Rules[i].ChannelIDs[:0]
		seen := make(map[string]struct{}, len(state.Rules[i].ChannelIDs))
		for _, id := range state.Rules[i].ChannelIDs {
			if _, ok := known[id]; !ok {
				continue
			}
			if _, ok := seen[id]; ok {
				continue
			}
			seen[id] = struct{}{}
			ids = append(ids, id)
		}
		state.Rules[i].ChannelIDs = ids
	}
}

// LoadAlertingWebhookConfig reads the durable alerting contract and returns the
// first enabled webhook channel. Unsupported channel types are deliberately
// ignored rather than silently routed through a webhook implementation.
func LoadAlertingWebhookConfig(ctx context.Context, store configstore.ConfigStore) (AlertingWebhookConfig, bool, error) {
	state, ok, err := loadAlertingState(ctx, store)
	if err != nil || !ok {
		return AlertingWebhookConfig{}, false, err
	}
	for _, channel := range state.Channels {
		if !channel.Enabled || strings.ToLower(strings.TrimSpace(channel.Type)) != "webhook" {
			continue
		}
		url := strings.TrimSpace(channel.Config["url"])
		if url == "" || (!strings.HasPrefix(url, "https://") && !strings.HasPrefix(url, "http://")) {
			continue
		}
		buffer := 256
		if raw := strings.TrimSpace(channel.Config["buffer"]); raw != "" {
			if _, e := fmt.Sscanf(raw, "%d", &buffer); e != nil || buffer <= 0 {
				buffer = 256
			}
		}
		return AlertingWebhookConfig{URL: url, SigningKey: channel.Config["signing_key"], Buffer: buffer}, true, nil
	}
	return AlertingWebhookConfig{}, false, nil
}

func loadAlertingState(ctx context.Context, store configstore.ConfigStore) (alertingState, bool, error) {
	if store == nil {
		return alertingState{}, false, nil
	}
	row, err := store.GetConfig(ctx, alertingConfigKey)
	if err != nil {
		return alertingState{}, false, err
	}
	if row == nil || strings.TrimSpace(row.Value) == "" {
		return alertingState{}, false, nil
	}
	var state alertingState
	if err := sonic.Unmarshal([]byte(row.Value), &state); err != nil {
		return alertingState{}, false, fmt.Errorf("decode alerting state: %w", err)
	}
	normalizeAlertingState(&state)
	return state, true, nil
}

func LoadAlertingSNSConfig(ctx context.Context, store configstore.ConfigStore) (AlertingSNSConfig, bool, error) {
	state, ok, err := loadAlertingState(ctx, store)
	if err != nil || !ok {
		return AlertingSNSConfig{}, false, err
	}
	for _, channel := range state.Channels {
		if !channel.Enabled || strings.ToLower(strings.TrimSpace(channel.Type)) != "sns" {
			continue
		}
		topic := strings.TrimSpace(channel.Config["topic_arn"])
		if topic == "" || !strings.HasPrefix(topic, "arn:") {
			continue
		}
		buffer := parseAlertBuffer(channel.Config["buffer"])
		return AlertingSNSConfig{TopicARN: topic, Subject: strings.TrimSpace(channel.Config["subject"]), Region: strings.TrimSpace(channel.Config["region"]), Buffer: buffer}, true, nil
	}
	return AlertingSNSConfig{}, false, nil
}

func LoadAlertingEmailConfig(ctx context.Context, store configstore.ConfigStore) (AlertingEmailConfig, bool, error) {
	state, ok, err := loadAlertingState(ctx, store)
	if err != nil || !ok {
		return AlertingEmailConfig{}, false, err
	}
	for _, channel := range state.Channels {
		if !channel.Enabled || strings.ToLower(strings.TrimSpace(channel.Type)) != "email" {
			continue
		}
		from := strings.TrimSpace(channel.Config["from"])
		recipients := splitAlertRecipients(channel.Config["recipients"])
		if from == "" || len(recipients) == 0 {
			continue
		}
		return AlertingEmailConfig{From: from, Recipients: recipients, Subject: strings.TrimSpace(channel.Config["subject"]), Region: strings.TrimSpace(channel.Config["region"]), Buffer: parseAlertBuffer(channel.Config["buffer"])}, true, nil
	}
	return AlertingEmailConfig{}, false, nil
}

func LoadAlertingCloudflareEmailConfig(ctx context.Context, store configstore.ConfigStore) (AlertingCloudflareEmailConfig, bool, error) {
	state, ok, err := loadAlertingState(ctx, store)
	if err != nil || !ok {
		return AlertingCloudflareEmailConfig{}, false, err
	}
	for _, channel := range state.Channels {
		if !channel.Enabled || strings.ToLower(strings.TrimSpace(channel.Type)) != "cloudflare_email" {
			continue
		}
		accountID := strings.TrimSpace(channel.Config["account_id"])
		token := strings.TrimSpace(channel.Config["api_token"])
		from := strings.TrimSpace(channel.Config["from"])
		recipients := splitAlertRecipients(channel.Config["recipients"])
		if accountID == "" || token == "" || from == "" || len(recipients) == 0 {
			continue
		}
		return AlertingCloudflareEmailConfig{AccountID: accountID, APIToken: token, From: from, Recipients: recipients, Subject: strings.TrimSpace(channel.Config["subject"]), Buffer: parseAlertBuffer(channel.Config["buffer"])}, true, nil
	}
	return AlertingCloudflareEmailConfig{}, false, nil
}

func parseAlertBuffer(raw string) int {
	buffer := 256
	if raw != "" {
		if _, err := fmt.Sscanf(strings.TrimSpace(raw), "%d", &buffer); err != nil || buffer <= 0 {
			buffer = 256
		}
	}
	return buffer
}

func splitAlertRecipients(raw string) []string {
	parts := strings.Split(raw, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if value := strings.TrimSpace(part); value != "" {
			result = append(result, value)
		}
	}
	return result
}

type AlertingHandler struct {
	configStore configstore.ConfigStore
	mu          sync.Mutex
	onChanged   func()
}

func validAlertChannelType(kind string) bool {
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case "webhook", "sns", "email", "cloudflare_email":
		return true
	default:
		return false
	}
}

func NewAlertingHandler(s configstore.ConfigStore) *AlertingHandler {
	return &AlertingHandler{configStore: s}
}

// SetOnChanged installs a callback invoked after durable alerting state is
// committed. The server uses it to refresh notifier projections asynchronously.
func (h *AlertingHandler) SetOnChanged(fn func()) { h.onChanged = fn }
func (h *AlertingHandler) RegisterRoutes(r *router.Router, m ...schemas.BifrostHTTPMiddleware) {
	r.GET("/api/alerting/channels", lib.ChainMiddlewares(h.listChannels, m...))
	r.POST("/api/alerting/channels", lib.ChainMiddlewares(h.createChannel, m...))
	r.PUT("/api/alerting/channels/{id}", lib.ChainMiddlewares(h.updateChannel, m...))
	r.DELETE("/api/alerting/channels/{id}", lib.ChainMiddlewares(h.deleteChannel, m...))
	r.GET("/api/alerting/rules", lib.ChainMiddlewares(h.listRules, m...))
	r.POST("/api/alerting/rules", lib.ChainMiddlewares(h.createRule, m...))
	r.PUT("/api/alerting/rules/{id}", lib.ChainMiddlewares(h.updateRule, m...))
	r.DELETE("/api/alerting/rules/{id}", lib.ChainMiddlewares(h.deleteRule, m...))
	r.GET("/api/alerting/history", lib.ChainMiddlewares(h.history, m...))
}
func (h *AlertingHandler) load(ctx *fasthttp.RequestCtx) (alertingState, error) {
	if h.configStore == nil {
		return alertingState{}, fmt.Errorf("alerting store unavailable")
	}
	row, e := h.configStore.GetConfig(ctx, alertingConfigKey)
	if e != nil {
		return alertingState{}, e
	}
	if row == nil || strings.TrimSpace(row.Value) == "" {
		return alertingState{}, nil
	}
	var s alertingState
	if e = sonic.Unmarshal([]byte(row.Value), &s); e != nil {
		return s, e
	}
	normalizeAlertingState(&s)
	return s, nil
}
func (h *AlertingHandler) save(ctx *fasthttp.RequestCtx, s alertingState) error {
	b, e := sonic.Marshal(s)
	if e != nil {
		return e
	}
	return h.configStore.UpdateConfig(ctx, &tables.TableGovernanceConfig{Key: alertingConfigKey, Value: string(b)})
}
func (h *AlertingHandler) mutate(ctx *fasthttp.RequestCtx, fn func(*alertingState)) {
	h.mu.Lock()
	defer h.mu.Unlock()
	s, e := h.load(ctx)
	if e != nil {
		SendError(ctx, 500, "alerting backend unavailable")
		return
	}
	fn(&s)
	normalizeAlertingState(&s)
	if e = h.save(ctx, s); e != nil {
		SendError(ctx, 500, "failed to persist alerting state")
		return
	}
	if h.onChanged != nil {
		h.onChanged()
	}
	SendJSON(ctx, publicAlertingState(s))
}
func (h *AlertingHandler) listChannels(c *fasthttp.RequestCtx) {
	s, e := h.load(c)
	if e != nil {
		SendError(c, 500, "alerting backend unavailable")
		return
	}
	// Channels do not carry a separate scope field; their effective scope is
	// inherited from the rules that reference them.  Project the same scoped
	// rule set used by /rules and /history before returning channel metadata.
	// Returning every channel here would expose another team's endpoint/name
	// (and non-secret routing metadata) through a scoped dashboard view.
	filtered, ok := alertingScopeQuery(c, s)
	if !ok {
		return
	}
	if scope := strings.TrimSpace(string(c.QueryArgs().Peek("scope"))); scope != "" {
		allowed := make(map[string]struct{})
		for _, rule := range filtered.Rules {
			for _, id := range rule.ChannelIDs {
				allowed[id] = struct{}{}
			}
		}
		channels := filtered.Channels[:0]
		for _, channel := range filtered.Channels {
			if _, exists := allowed[channel.ID]; exists {
				channels = append(channels, channel)
			}
		}
		filtered.Channels = channels
	}
	SendJSON(c, map[string]any{"channels": publicAlertingState(filtered).Channels})
}
func (h *AlertingHandler) listRules(c *fasthttp.RequestCtx) {
	s, e := h.load(c)
	if e != nil {
		SendError(c, 500, "alerting backend unavailable")
		return
	}
	filtered, ok := alertingScopeQuery(c, s)
	if !ok {
		return
	}
	SendJSON(c, map[string]any{"rules": filtered.Rules})
}
func (h *AlertingHandler) history(c *fasthttp.RequestCtx) {
	s, e := h.load(c)
	if e != nil {
		SendError(c, 500, "alerting backend unavailable")
		return
	}
	filtered, ok := alertingScopeQuery(c, s)
	if !ok {
		return
	}
	SendJSON(c, map[string]any{"history": filtered.History})
}

// alertingScopeQuery projects rules and delivery history for a dashboard's
// global, team, or user view.  Delivery rows carry only RuleID, so filtering
// history must first resolve the rule scope; returning the unfiltered durable
// history would leak another team's/user's alert activity to a scoped view.
func alertingScopeQuery(c *fasthttp.RequestCtx, state alertingState) (alertingState, bool) {
	scope := strings.ToLower(strings.TrimSpace(string(c.QueryArgs().Peek("scope"))))
	scopeID := strings.TrimSpace(string(c.QueryArgs().Peek("scope_id")))
	if scope == "" && scopeID == "" {
		return state, true
	}
	if scope != "global" && scope != "team" && scope != "user" {
		SendError(c, 400, "scope must be global, team, or user")
		return alertingState{}, false
	}
	if scope == "global" {
		scopeID = ""
	} else if scopeID == "" {
		SendError(c, 400, "scope_id is required for team and user scopes")
		return alertingState{}, false
	}
	allowed := make(map[string]struct{}, len(state.Rules))
	rules := make([]AlertRule, 0, len(state.Rules))
	for _, rule := range state.Rules {
		ruleScope := strings.ToLower(strings.TrimSpace(rule.Scope))
		matches := ruleScope == "" || ruleScope == "global"
		if scope != "global" {
			matches = matches || (ruleScope == scope && strings.TrimSpace(rule.ScopeID) == scopeID)
		}
		if matches {
			rules = append(rules, rule)
			allowed[rule.ID] = struct{}{}
		}
	}
	history := make([]AlertDelivery, 0, len(state.History))
	for _, delivery := range state.History {
		if _, ok := allowed[delivery.RuleID]; ok {
			history = append(history, delivery)
		}
	}
	state.Rules, state.History = rules, history
	return state, true
}
func (h *AlertingHandler) createChannel(c *fasthttp.RequestCtx) {
	var v AlertChannel
	if sonic.Unmarshal(c.PostBody(), &v) != nil || v.Name == "" || v.Type == "" {
		SendError(c, 400, "name and type are required")
		return
	}
	v.Type = strings.ToLower(strings.TrimSpace(v.Type))
	if !validAlertChannelType(v.Type) {
		SendError(c, 400, "unsupported alert channel type")
		return
	}
	if v.ID == "" {
		v.ID = uuid.NewString()
	}
	h.mutate(c, func(s *alertingState) { s.Channels = append(s.Channels, v) })
}
func (h *AlertingHandler) createRule(c *fasthttp.RequestCtx) {
	var v AlertRule
	if sonic.Unmarshal(c.PostBody(), &v) != nil || v.Name == "" || v.Event == "" {
		SendError(c, 400, "name and event are required")
		return
	}
	if v.ID == "" {
		v.ID = uuid.NewString()
	}
	if v.Scope == "" {
		v.Scope = "global"
	}
	if v.Scope != "global" && v.Scope != "team" && v.Scope != "user" {
		SendError(c, 400, "scope must be global, team, or user")
		return
	}
	if v.Scope == "global" {
		v.ScopeID = ""
	}
	if v.Scope != "global" && strings.TrimSpace(v.ScopeID) == "" {
		SendError(c, 400, "scope_id is required for team or user rules")
		return
	}
	h.mutate(c, func(s *alertingState) { s.Rules = append(s.Rules, v) })
}
func (h *AlertingHandler) updateChannel(c *fasthttp.RequestCtx) {
	id, _ := c.UserValue("id").(string)
	var v AlertChannel
	if sonic.Unmarshal(c.PostBody(), &v) != nil || v.Name == "" || v.Type == "" {
		SendError(c, 400, "name and type are required")
		return
	}
	v.Type = strings.ToLower(strings.TrimSpace(v.Type))
	if !validAlertChannelType(v.Type) {
		SendError(c, 400, "unsupported alert channel type")
		return
	}
	v.ID = id
	h.mutate(c, func(s *alertingState) {
		for i := range s.Channels {
			if s.Channels[i].ID == id {
				s.Channels[i] = preserveAlertChannelSecrets(s.Channels[i], v)
				return
			}
		}
		s.Channels = append(s.Channels, v)
	})
}
func (h *AlertingHandler) updateRule(c *fasthttp.RequestCtx) {
	id, _ := c.UserValue("id").(string)
	var v AlertRule
	if sonic.Unmarshal(c.PostBody(), &v) != nil || v.Name == "" || v.Event == "" {
		SendError(c, 400, "name and event are required")
		return
	}
	if v.Scope == "" {
		v.Scope = "global"
	}
	if v.Scope != "global" && v.Scope != "team" && v.Scope != "user" {
		SendError(c, 400, "scope must be global, team, or user")
		return
	}
	if v.Scope == "global" {
		v.ScopeID = ""
	}
	if v.Scope != "global" && strings.TrimSpace(v.ScopeID) == "" {
		SendError(c, 400, "scope_id is required for team or user rules")
		return
	}
	v.ID = id
	h.mutate(c, func(s *alertingState) {
		for i := range s.Rules {
			if s.Rules[i].ID == id {
				s.Rules[i] = v
				return
			}
		}
		s.Rules = append(s.Rules, v)
	})
}
func (h *AlertingHandler) deleteChannel(c *fasthttp.RequestCtx) {
	id, _ := c.UserValue("id").(string)
	h.mutate(c, func(s *alertingState) {
		for i, v := range s.Channels {
			if v.ID == id {
				s.Channels = append(s.Channels[:i], s.Channels[i+1:]...)
				break
			}
		}
	})
}
func (h *AlertingHandler) deleteRule(c *fasthttp.RequestCtx) {
	id, _ := c.UserValue("id").(string)
	h.mutate(c, func(s *alertingState) {
		for i, v := range s.Rules {
			if v.ID == id {
				s.Rules = append(s.Rules[:i], s.Rules[i+1:]...)
				break
			}
		}
	})
}
