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

// AlertingWebhookConfig is the small, startup-time projection consumed by the
// governance admission notifier.  Alerting CRUD remains durable and
// asynchronous; changing a channel takes effect on the next plugin reload.
// Only webhook channels are projected until native SNS/email workers exist.
type AlertingWebhookConfig struct {
	URL        string
	SigningKey string
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

// LoadAlertingWebhookConfig reads the durable alerting contract and returns the
// first enabled webhook channel. Unsupported channel types are deliberately
// ignored rather than silently routed through a webhook implementation.
func LoadAlertingWebhookConfig(ctx context.Context, store configstore.ConfigStore) (AlertingWebhookConfig, bool, error) {
	if store == nil {
		return AlertingWebhookConfig{}, false, nil
	}
	row, err := store.GetConfig(ctx, alertingConfigKey)
	if err != nil {
		return AlertingWebhookConfig{}, false, err
	}
	if row == nil || strings.TrimSpace(row.Value) == "" {
		return AlertingWebhookConfig{}, false, nil
	}
	var state alertingState
	if err := sonic.Unmarshal([]byte(row.Value), &state); err != nil {
		return AlertingWebhookConfig{}, false, fmt.Errorf("decode alerting state: %w", err)
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

type AlertingHandler struct {
	configStore configstore.ConfigStore
	mu          sync.Mutex
	onChanged   func()
}

func validAlertChannelType(kind string) bool {
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case "webhook", "sns", "email":
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
	if e = h.save(ctx, s); e != nil {
		SendError(ctx, 500, "failed to persist alerting state")
		return
	}
	if h.onChanged != nil {
		h.onChanged()
	}
	SendJSON(ctx, s)
}
func (h *AlertingHandler) listChannels(c *fasthttp.RequestCtx) {
	s, e := h.load(c)
	if e != nil {
		SendError(c, 500, "alerting backend unavailable")
		return
	}
	SendJSON(c, map[string]any{"channels": s.Channels})
}
func (h *AlertingHandler) listRules(c *fasthttp.RequestCtx) {
	s, e := h.load(c)
	if e != nil {
		SendError(c, 500, "alerting backend unavailable")
		return
	}
	SendJSON(c, map[string]any{"rules": s.Rules})
}
func (h *AlertingHandler) history(c *fasthttp.RequestCtx) {
	s, e := h.load(c)
	if e != nil {
		SendError(c, 500, "alerting backend unavailable")
		return
	}
	SendJSON(c, map[string]any{"history": s.History})
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
				s.Channels[i] = v
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
