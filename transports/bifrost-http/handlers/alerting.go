package handlers

// AlertingHandler provides the durable dashboard contract for alert channels,
// rules, and delivery history.  State is kept in ConfigStore's transactional
// governance_config table so every replica observes the same configuration;
// delivery workers remain asynchronous and are deliberately outside this
// request path.
import (
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

type AlertingHandler struct {
	configStore configstore.ConfigStore
	mu          sync.Mutex
}

func NewAlertingHandler(s configstore.ConfigStore) *AlertingHandler {
	return &AlertingHandler{configStore: s}
}
func (h *AlertingHandler) RegisterRoutes(r *router.Router, m ...schemas.BifrostHTTPMiddleware) {
	r.GET("/api/alerting/channels", lib.ChainMiddlewares(h.listChannels, m...))
	r.POST("/api/alerting/channels", lib.ChainMiddlewares(h.createChannel, m...))
	r.DELETE("/api/alerting/channels/{id}", lib.ChainMiddlewares(h.deleteChannel, m...))
	r.GET("/api/alerting/rules", lib.ChainMiddlewares(h.listRules, m...))
	r.POST("/api/alerting/rules", lib.ChainMiddlewares(h.createRule, m...))
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
