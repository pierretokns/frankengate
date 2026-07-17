package server

import (
	"context"
	"fmt"
	"math"
	"slices"

	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/ses"
	sestypes "github.com/aws/aws-sdk-go-v2/service/ses/types"
	"github.com/aws/aws-sdk-go-v2/service/sns"
	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/plugins/compat"
	"github.com/maximhq/bifrost/plugins/governance"
	"github.com/maximhq/bifrost/plugins/logging"
	"github.com/maximhq/bifrost/plugins/maxim"
	"github.com/maximhq/bifrost/plugins/modelcatalogresolver"
	"github.com/maximhq/bifrost/plugins/otel"
	"github.com/maximhq/bifrost/plugins/prompts"
	"github.com/maximhq/bifrost/plugins/semanticcache"
	"github.com/maximhq/bifrost/plugins/telemetry"
	"github.com/maximhq/bifrost/transports/bifrost-http/handlers"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
)

// InferPluginTypes determines which interface types a plugin implements
func InferPluginTypes(plugin schemas.BasePlugin) []schemas.PluginType {
	var types []schemas.PluginType
	if _, ok := plugin.(schemas.LLMPlugin); ok {
		types = append(types, schemas.PluginTypeLLM)
	}
	if _, ok := plugin.(schemas.MCPPlugin); ok {
		types = append(types, schemas.PluginTypeMCP)
	}
	if _, ok := plugin.(schemas.HTTPTransportPlugin); ok {
		types = append(types, schemas.PluginTypeHTTP)
	}
	return types
}

type awsSNSPublisher struct{ client *sns.Client }

func (p awsSNSPublisher) Publish(ctx context.Context, topicARN, subject, body string) error {
	_, err := p.client.Publish(ctx, &sns.PublishInput{TopicArn: &topicARN, Subject: &subject, Message: &body})
	return err
}

type awsSESEmailSender struct{ client *ses.Client }

func (s awsSESEmailSender) Send(ctx context.Context, from string, recipients []string, subject, body string) error {
	_, err := s.client.SendEmail(ctx, &ses.SendEmailInput{
		Source:      &from,
		Destination: &sestypes.Destination{ToAddresses: recipients},
		Message: &sestypes.Message{
			Subject: &sestypes.Content{Data: &subject},
			Body:    &sestypes.Body{Text: &sestypes.Content{Data: &body}},
		},
	})
	return err
}

// Single-plugin methods used plugin create/update

// InstantiatePlugin creates a plugin instance but does NOT register it
// Registration is done separately via Config.RegisterPlugin()
func InstantiatePlugin(ctx context.Context, name string, path *string, pluginConfig any, bifrostConfig *lib.Config) (schemas.BasePlugin, error) {
	// Custom plugin (has path)
	if path != nil {
		return loadCustomPlugin(ctx, path, pluginConfig, bifrostConfig)
	}

	// Built-in plugin (by name)
	return loadBuiltinPlugin(ctx, name, pluginConfig, bifrostConfig)
}

// loadBuiltinPlugin instantiates a built-in plugin by name
func loadBuiltinPlugin(ctx context.Context, name string, pluginConfig any, bifrostConfig *lib.Config) (schemas.BasePlugin, error) {
	switch name {
	case telemetry.PluginName:
		telConfig := &telemetry.Config{
			CustomLabels: bifrostConfig.ClientConfig.PrometheusLabels,
		}
		// Merge persisted config if provided.
		if pluginConfig != nil {
			extraConfig, err := MarshalPluginConfig[telemetry.Config](pluginConfig)
			if err != nil {
				return nil, fmt.Errorf("failed to marshal telemetry plugin config: %w", err)
			}
			if extraConfig != nil {
				if extraConfig.PushGateway != nil {
					telConfig.PushGateway = extraConfig.PushGateway
				}
				if extraConfig.MetricsEnabled != nil {
					telConfig.MetricsEnabled = extraConfig.MetricsEnabled
				}
			}
		}
		return telemetry.Init(telConfig, bifrostConfig.ModelCatalog, logger)

	case prompts.PluginName:
		return prompts.Init(ctx, bifrostConfig.ConfigStore, logger)

	case logging.PluginName:
		loggingConfig, err := MarshalPluginConfig[logging.Config](pluginConfig)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal logging plugin config: %w", err)
		}
		return logging.Init(ctx, loggingConfig, logger, bifrostConfig.LogsStore,
			bifrostConfig.ModelCatalog, bifrostConfig.MCPCatalog)

	case governance.PluginName:
		governanceConfig, err := MarshalPluginConfig[governance.Config](pluginConfig)
		if err != nil {
			// Persisted governance extensions are optional. Do not make a
			// malformed optional row prevent the gateway from starting; the
			// built-in defaults remain fail-closed for authorization.
			logger.Warn("failed to decode persisted governance plugin config; using defaults: %v", err)
			governanceConfig = &governance.Config{}
		}
		inMemoryStore := &GovernanceInMemoryStore{Config: bifrostConfig}
		plugin, err := governance.Init(ctx, governanceConfig, logger, bifrostConfig.ConfigStore,
			bifrostConfig.GovernanceConfig, bifrostConfig.ModelCatalog,
			bifrostConfig.MCPCatalog, inMemoryStore)
		if err != nil {
			return nil, err
		}
		// Durable admission is enabled only when the deployment explicitly
		// supplies both the transactional reservation store and a conservative
		// estimator. This keeps OSS/legacy deployments compatible without ever
		// reserving guessed zero-cost amounts.
		if reservationStore, ok := bifrostConfig.ConfigStore.(configstore.BudgetReservationStore); ok {
			allowOverdraft := governanceConfig.ReservationAllowOverdraft != nil && *governanceConfig.ReservationAllowOverdraft
			overdraft := reservations.OverdraftPolicy{Allow: allowOverdraft, Reason: governanceConfig.ReservationOverdraftReason}
			configureNotifier := func(coordinator *governance.DurableReservationCoordinator) {
				buffer := 256
				if governanceConfig.ReservationWebhookBuffer != nil && *governanceConfig.ReservationWebhookBuffer > 0 {
					buffer = *governanceConfig.ReservationWebhookBuffer
				}
				var signingKey []byte
				if governanceConfig.ReservationWebhookSigningKey != nil {
					signingKey = []byte(governanceConfig.ReservationWebhookSigningKey.GetValue())
				}
				url := ""
				if governanceConfig.ReservationWebhookURL != nil {
					url = governanceConfig.ReservationWebhookURL.GetValue()
				}
				// Durable dashboard alerting is a startup-time projection. Explicit
				// governance config wins; otherwise use the first enabled webhook
				// channel from the shared alerting state. SNS/email remain fail-closed
				// until their native workers are implemented.
				if url == "" {
					if alert, ok, alertErr := handlers.LoadAlertingWebhookConfig(ctx, bifrostConfig.ConfigStore); alertErr != nil {
						logger.Warn("durable alerting state unavailable; overdraft notifier disabled: %v", alertErr)
						return
					} else if ok {
						url = alert.URL
						buffer = alert.Buffer
						signingKey = []byte(alert.SigningKey)
					}
				}
				if url == "" {
					if alert, ok, alertErr := handlers.LoadAlertingSNSConfig(ctx, bifrostConfig.ConfigStore); alertErr != nil {
						logger.Warn("durable SNS alerting state unavailable; native notifier disabled: %v", alertErr)
						return
					} else if ok {
						loadOptions := make([]func(*awsconfig.LoadOptions) error, 0, 1)
						if alert.Region != "" {
							loadOptions = append(loadOptions, awsconfig.WithRegion(alert.Region))
						}
						awsCfg, cfgErr := awsconfig.LoadDefaultConfig(ctx, loadOptions...)
						if cfgErr != nil {
							logger.Warn("AWS credentials unavailable; SNS notifier disabled: %v", cfgErr)
							return
						}
						coordinator.SetNotifier(governance.NewAsyncOverdraftNotifier(ctx, &governance.SNSOverdraftNotifier{
							Publisher: awsSNSPublisher{client: sns.NewFromConfig(awsCfg)}, TopicARN: alert.TopicARN, Subject: alert.Subject,
						}, alert.Buffer))
						return
					}
				}
				if url == "" {
					if alert, ok, alertErr := handlers.LoadAlertingEmailConfig(ctx, bifrostConfig.ConfigStore); alertErr != nil {
						logger.Warn("durable email alerting state unavailable; native notifier disabled: %v", alertErr)
						return
					} else if ok {
						loadOptions := make([]func(*awsconfig.LoadOptions) error, 0, 1)
						if alert.Region != "" {
							loadOptions = append(loadOptions, awsconfig.WithRegion(alert.Region))
						}
						awsCfg, cfgErr := awsconfig.LoadDefaultConfig(ctx, loadOptions...)
						if cfgErr != nil {
							logger.Warn("AWS credentials unavailable; email notifier disabled: %v", cfgErr)
							return
						}
						coordinator.SetNotifier(governance.NewAsyncOverdraftNotifier(ctx, &governance.EmailOverdraftNotifier{
							Sender: awsSESEmailSender{client: ses.NewFromConfig(awsCfg)}, From: alert.From, Recipients: alert.Recipients, Subject: alert.Subject,
						}, alert.Buffer))
						return
					}
				}
				if url == "" {
					return
				}
				coordinator.SetNotifier(governance.NewAsyncOverdraftNotifier(ctx, &governance.WebhookOverdraftNotifier{
					URL: url, SigningKey: signingKey,
				}, buffer))
			}
			if estimator, ok := bifrostConfig.ConfigStore.(governance.ReservationEstimator); ok {
				coordinator := &governance.DurableReservationCoordinator{
					Store:     reservationStore,
					Estimator: estimator,
					Overdraft: overdraft,
				}
				configureNotifier(coordinator)
				plugin.SetReservationCoordinator(coordinator)
				logger.Info("governance durable admission enabled with config-store reservation estimator")
			} else if governanceConfig.ReservationMaxTokens != nil && governanceConfig.ReservationCostMicrosPerToken != nil {
				coordinator := &governance.DurableReservationCoordinator{
					Store: reservationStore,
					Estimator: governance.ConfiguredReservationEstimator{
						MaxTokens:          *governanceConfig.ReservationMaxTokens,
						CostMicrosPerToken: *governanceConfig.ReservationCostMicrosPerToken,
					},
					Overdraft: overdraft,
				}
				configureNotifier(coordinator)
				plugin.SetReservationCoordinator(coordinator)
				logger.Info("governance durable admission enabled with configured reservation estimator")
			} else if governanceConfig.IsEnterprise {
				return nil, fmt.Errorf("enterprise governance requires a reservation estimator when the config store supports durable reservations")
			}
		} else if governanceConfig.IsEnterprise {
			// Enterprise governance must never silently fall back to the legacy
			// in-memory budget path. Without a transactional reservation store,
			// horizontally scaled pods can each admit the same spend. Fail closed
			// during plugin construction so the deployment cannot advertise
			// enterprise governance while bypassing durable admission.
			return nil, fmt.Errorf("enterprise governance requires a config store with durable budget reservations")
		} else if governanceConfig.ReservationMaxTokens != nil || governanceConfig.ReservationCostMicrosPerToken != nil {
			// Never make configured durable admission look active when the injected
			// store cannot provide the transactional reservation surface.
			logger.Warn("governance durable admission settings are configured but the config store does not implement BudgetReservationStore; requests will not receive durable reservations")
		}
		return plugin, nil

	case maxim.PluginName:
		maximConfig, err := MarshalPluginConfig[maxim.Config](pluginConfig)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal maxim plugin config: %w", err)
		}
		return maxim.Init(maximConfig, logger)

	case semanticcache.PluginName:
		semanticConfig, err := MarshalPluginConfig[semanticcache.Config](pluginConfig)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal semantic cache plugin config: %w", err)
		}
		return semanticcache.Init(ctx, semanticConfig, logger, bifrostConfig.VectorStore)

	case otel.PluginName:
		otelConfig, err := MarshalPluginConfig[otel.Config](pluginConfig)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal otel plugin config: %w", err)
		}
		return otel.Init(ctx, otelConfig, logger, bifrostConfig.ModelCatalog, handlers.GetVersion())

	case compat.PluginName:
		compatConfig, err := MarshalPluginConfig[compat.Config](pluginConfig)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal compat plugin config: %w", err)
		}
		return compat.Init(*compatConfig, logger, bifrostConfig.ModelCatalog)

	case modelcatalogresolver.PluginName:
		return modelcatalogresolver.Init(bifrostConfig.ModelCatalog, logger)

	default:
		return nil, fmt.Errorf("unknown built-in plugin: %s", name)
	}
}

// loadCustomPlugin loads a plugin from a shared object file
func loadCustomPlugin(ctx context.Context, path *string, pluginConfig any, bifrostConfig *lib.Config) (schemas.BasePlugin, error) {
	logger.Info("loading custom plugin from path %s", *path)

	plugin, err := bifrostConfig.PluginLoader.LoadPlugin(*path, pluginConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to load custom plugin: %w", err)
	}
	return plugin, nil
}

// LoadPlugins loads the plugins for the server.
func (s *BifrostHTTPServer) LoadPlugins(ctx context.Context) error {
	// Load built-in plugins first (order matters)
	if err := s.loadBuiltinPlugins(ctx); err != nil {
		return err
	}
	// Load custom plugins from config
	if err := s.loadCustomPlugins(ctx); err != nil {
		return err
	}
	// Sort all plugins by placement group and order
	s.Config.SortAndRebuildPlugins()
	s.wireGovernanceMetrics()
	return nil
}

// wireGovernanceMetrics connects the optional OTEL exporter to durable
// governance admission after all built-ins have been instantiated. The
// governance package remains exporter-neutral and deployments without OTEL
// retain the same behavior.
func (s *BifrostHTTPServer) wireGovernanceMetrics() {
	var governancePlugin *governance.GovernancePlugin
	var otelPlugin *otel.OtelPlugin
	var prometheusPlugin *telemetry.PrometheusPlugin
	if plugins := s.Config.BasePlugins.Load(); plugins != nil {
		for _, plugin := range *plugins {
			switch p := plugin.(type) {
			case *governance.GovernancePlugin:
				governancePlugin = p
			case *otel.OtelPlugin:
				otelPlugin = p
			case *telemetry.PrometheusPlugin:
				prometheusPlugin = p
			}
		}
	}
	if governancePlugin != nil {
		sinks := make([]governance.MetricsSink, 0, 2)
		if otelPlugin != nil {
			sinks = append(sinks, otelPlugin)
		}
		if prometheusPlugin != nil {
			sinks = append(sinks, prometheusPlugin)
		}
		if len(sinks) == 1 {
			governancePlugin.SetMetricsSink(sinks[0])
		} else if len(sinks) > 1 {
			governancePlugin.SetMetricsSink(governanceMetricsFanout(sinks))
		}
	}
}

type governanceMetricsFanout []governance.MetricsSink

func (f governanceMetricsFanout) ReservationObserved(ctx context.Context, outcome string, amount reservations.Amount) {
	for _, sink := range f {
		sink.ReservationObserved(ctx, outcome, amount)
	}
}
func (f governanceMetricsFanout) OverdraftObserved(ctx context.Context, allowed bool, amount reservations.Amount) {
	for _, sink := range f {
		sink.OverdraftObserved(ctx, allowed, amount)
	}
}
func (f governanceMetricsFanout) NotifierObserved(ctx context.Context, outcome string) {
	for _, sink := range f {
		sink.NotifierObserved(ctx, outcome)
	}
}

// getPluginConfig retrieves a plugin's config from PluginConfigs by name
func (s *BifrostHTTPServer) getPluginConfig(name string) *schemas.PluginConfig {
	for _, cfg := range s.Config.PluginConfigs {
		if cfg.Name == name {
			return cfg
		}
	}
	return nil
}

// loadBuiltinPlugins loads required built-in plugins in specific order
func (s *BifrostHTTPServer) loadBuiltinPlugins(ctx context.Context) error {
	builtinPlacement := schemas.Ptr(schemas.PluginPlacementBuiltin)

	// 1. Telemetry (always first - tracks everything).
	// Default-on: absent PluginConfig entry is treated as enabled, matching pre-#3269 behavior
	// so upgraders don't silently lose /metrics. Only an explicit Enabled=false disables it.
	telemetryPluginConfig := s.getPluginConfig(telemetry.PluginName)
	var pluginConfig any
	if telemetryPluginConfig != nil {
		pluginConfig = telemetryPluginConfig.Config
	}
	if telemetryPluginConfig == nil || telemetryPluginConfig.Enabled {
		s.registerPluginWithStatus(ctx, telemetry.PluginName, nil, pluginConfig, false)
	} else {
		s.markPluginDisabled(telemetry.PluginName)
	}
	s.Config.SetPluginOrderInfo(telemetry.PluginName, builtinPlacement, schemas.Ptr(1))

	// 2. Prompts (requires config store for prompt repository; disabled in enterprise)
	if s.Config.ConfigStore != nil && ctx.Value(schemas.BifrostContextKeyIsEnterprise) == nil {
		s.registerPluginWithStatus(ctx, prompts.PluginName, nil, nil, false)
	} else {
		s.markPluginDisabled(prompts.PluginName)
	}
	s.Config.SetPluginOrderInfo(prompts.PluginName, builtinPlacement, schemas.Ptr(2))

	// 3. Logging (if enabled)
	if (s.Config.ClientConfig.EnableLogging == nil || *s.Config.ClientConfig.EnableLogging) && s.Config.LogsStore != nil {
		config := &logging.Config{
			DisableContentLogging: &s.Config.ClientConfig.DisableContentLogging,
			LoggingHeaders:        &s.Config.ClientConfig.LoggingHeaders,
		}
		if s.Config.LogsStoreConfig != nil {
			config.Writer = s.Config.LogsStoreConfig.Writer
		}
		s.registerPluginWithStatus(ctx, logging.PluginName, nil, config, false)
	} else {
		s.markPluginDisabled(logging.PluginName)
	}
	s.Config.SetPluginOrderInfo(logging.PluginName, builtinPlacement, schemas.Ptr(3))

	// 4. Governance (if enabled and not enterprise)
	if ctx.Value(schemas.BifrostContextKeyIsEnterprise) == nil {
		config := &governance.Config{
			IsVkMandatory:         &s.Config.ClientConfig.EnforceAuthOnInference,
			RequiredHeaders:       &s.Config.ClientConfig.RequiredHeaders,
			DisableAutoToolInject: &s.Config.ClientConfig.MCPDisableAutoToolInject,
			RoutingChainMaxDepth:  &s.Config.ClientConfig.RoutingChainMaxDepth,
		}
		// Governance is built in, but durable-admission settings live in the
		// persisted plugin config. Merge those fields into the built-in defaults;
		// otherwise PostgreSQL deployments silently construct a coordinator with
		// no estimator even when reservation settings are configured.
		if persisted := s.getPluginConfig(governance.PluginName); persisted != nil && persisted.Config != nil {
			extra, err := MarshalPluginConfig[governance.Config](persisted.Config)
			if err != nil {
				logger.Warn("failed to decode persisted governance plugin config; using built-in defaults: %v", err)
			} else if extra != nil {
				config.ReservationMaxTokens = extra.ReservationMaxTokens
				config.ReservationCostMicrosPerToken = extra.ReservationCostMicrosPerToken
				config.ReservationAllowOverdraft = extra.ReservationAllowOverdraft
				config.ReservationOverdraftReason = extra.ReservationOverdraftReason
				config.ReservationWebhookURL = extra.ReservationWebhookURL
				config.ReservationWebhookSigningKey = extra.ReservationWebhookSigningKey
				config.ReservationWebhookBuffer = extra.ReservationWebhookBuffer
			}
		}
		s.registerPluginWithStatus(ctx, governance.PluginName, nil, config, false)
	} else {
		s.markPluginDisabled(governance.PluginName)
	}
	s.Config.SetPluginOrderInfo(governance.PluginName, builtinPlacement, schemas.Ptr(4))

	// 5. OTEL (if configured in PluginConfigs)
	otelConfig := s.getPluginConfig(otel.PluginName)
	if otelConfig != nil && otelConfig.Enabled {
		s.registerPluginWithStatus(ctx, otel.PluginName, nil, otelConfig.Config, false)
	} else {
		s.markPluginDisabled(otel.PluginName)
	}
	s.Config.SetPluginOrderInfo(otel.PluginName, builtinPlacement, schemas.Ptr(5))

	// 6. Semantic Cache (if configured in PluginConfigs)
	semanticCacheConfig := s.getPluginConfig(semanticcache.PluginName)
	if semanticCacheConfig != nil && semanticCacheConfig.Enabled {
		s.registerPluginWithStatus(ctx, semanticcache.PluginName, nil, semanticCacheConfig.Config, false)
	} else {
		s.markPluginDisabled(semanticcache.PluginName)
	}
	s.Config.SetPluginOrderInfo(semanticcache.PluginName, builtinPlacement, schemas.Ptr(6))

	// 7. Compat (if any compat feature is enabled in ClientConfig)
	cc := s.Config.ClientConfig.Compat
	compatCfg := &compat.Config{
		ConvertTextToChat:      cc.ConvertTextToChat,
		ConvertChatToResponses: cc.ConvertChatToResponses,
		ShouldDropParams:       cc.ShouldDropParams,
		ShouldConvertParams:    cc.ShouldConvertParams,
	}
	s.registerPluginWithStatus(ctx, compat.PluginName, nil, compatCfg, false)
	s.Config.SetPluginOrderInfo(compat.PluginName, builtinPlacement, schemas.Ptr(7))

	// 8. Maxim (if configured in PluginConfigs)
	maximConfig := s.getPluginConfig(maxim.PluginName)
	if maximConfig != nil && maximConfig.Enabled {
		s.registerPluginWithStatus(ctx, maxim.PluginName, nil, maximConfig.Config, false)
	} else {
		s.markPluginDisabled(maxim.PluginName)
	}
	s.Config.SetPluginOrderInfo(maxim.PluginName, builtinPlacement, schemas.Ptr(8))

	// 9. ModelCatalogResolver (last routing layer — fills req.Provider from catalog only when
	// no earlier routing plugin (governance routing rules, governance VK LB, enterprise LB)
	// already set one. CEL rules can still match on provider == "" because this runs last.
	// Requires a model catalog; only register when one is configured.
	if s.Config.ModelCatalog != nil {
		s.registerPluginWithStatus(ctx, modelcatalogresolver.PluginName, nil, nil, false)
	} else {
		s.markPluginDisabled(modelcatalogresolver.PluginName)
	}
	// Place it in post_builtin with a max order so it runs after every other routing plugin,
	// including post_builtin ones like the enterprise load balancer (which would otherwise run
	// after this builtin and never get a chance to pick the provider first).
	s.Config.SetPluginOrderInfo(modelcatalogresolver.PluginName, schemas.Ptr(schemas.PluginPlacementPostBuiltin), schemas.Ptr(math.MaxInt))

	return nil
}

// loadCustomPlugins loads plugins from PluginConfigs
func (s *BifrostHTTPServer) loadCustomPlugins(ctx context.Context) error {
	for _, cfg := range s.Config.PluginConfigs {
		// Skip built-ins (already loaded)
		if lib.IsBuiltinPlugin(cfg.Name) {
			continue
		}
		// Handle disabled plugins
		if !cfg.Enabled {
			// For custom plugins with a path, verify to get the real plugin name
			if cfg.Path != nil {
				pluginName, err := s.Config.PluginLoader.VerifyBasePlugin(*cfg.Path)
				if err != nil {
					logger.Error("failed to verify disabled plugin %s: %v", cfg.Name, err)
					continue
				}
				// Store plugin status without instantiating (no Init() call, no resource usage)
				// Note: We can't determine types without instantiating, so pass empty slice
				s.Config.UpdatePluginOverallStatus(pluginName, cfg.Name, schemas.PluginStatusDisabled,
					[]string{fmt.Sprintf("plugin %s is disabled", cfg.Name)}, []schemas.PluginType{})
			} else {
				// Built-in plugin - use cfg.Name directly
				s.Config.UpdatePluginOverallStatus(cfg.Name, cfg.Name, schemas.PluginStatusDisabled,
					[]string{fmt.Sprintf("plugin %s is disabled", cfg.Name)}, []schemas.PluginType{})
			}
			continue
		}

		// Plugin is enabled - instantiate it
		plugin, err := InstantiatePlugin(ctx, cfg.Name, cfg.Path, cfg.Config, s.Config)
		if err != nil {
			// Skip enterprise plugins silently
			if slices.Contains(enterprisePlugins, cfg.Name) {
				continue
			}
			logger.Error("failed to load plugin %s: %v", cfg.Name, err)
			// Use cfg.Name since plugin may be nil when InstantiatePlugin returns an error
			s.Config.UpdatePluginOverallStatus(cfg.Name, cfg.Name, schemas.PluginStatusError,
				[]string{fmt.Sprintf("error loading plugin %s: %v", cfg.Name, err)}, []schemas.PluginType{})
			continue
		}

		// Ensure plugin is not nil before using it (defensive check)
		if plugin == nil {
			logger.Error("plugin %s instantiated but returned nil", cfg.Name)
			s.Config.UpdatePluginOverallStatus(cfg.Name, cfg.Name, schemas.PluginStatusError,
				[]string{fmt.Sprintf("plugin %s instantiated but returned nil", cfg.Name)}, []schemas.PluginType{})
			continue
		}

		// Register enabled plugin and mark as active
		s.Config.ReloadPlugin(plugin)
		s.Config.SetPluginOrderInfo(plugin.GetName(), cfg.Placement, cfg.Order)
		s.Config.UpdatePluginOverallStatus(plugin.GetName(), cfg.Name, schemas.PluginStatusActive,
			[]string{fmt.Sprintf("plugin %s initialized successfully", cfg.Name)}, InferPluginTypes(plugin))
	}
	return nil
}
