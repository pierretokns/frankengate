# FrankenGate UI

A modern, production-ready web interface for the [FrankenGate AI Gateway](https://github.com/pierretokns/frankengate) - providing real-time monitoring, configuration management, and comprehensive observability for your AI infrastructure.

## Overview

FrankenGate UI is a React + Vite + TanStack Router web dashboard that serves as the control center for your FrankenGate AI Gateway. It provides an intuitive interface to monitor AI requests, configure providers, manage MCP clients, and analyze performance metrics.

### Key Features

- **Real-time Log Monitoring** - Live streaming dashboard with WebSocket integration
- **Provider Management** - Configure providers through the FrankenGate gateway
- **MCP Integration** - Manage Model Context Protocol clients for advanced AI capabilities
- **Plugin System** - Extend functionality with custom plugins
- **Analytics Dashboard** - Request metrics, success rates, latency tracking, and token usage
- **Modern UI** - Dark/light mode, responsive design, and accessible components
- **Documentation Hub** - Built-in documentation browser and quick-start guides

## Quick Start

### Prerequisites

The UI is designed to work with the FrankenGate HTTP transport backend. Get started with the complete setup:

**[Gateway source and setup →](https://github.com/pierretokns/frankengate/tree/dev/docs)**

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The development server runs on `http://localhost:3000` and connects to your FrankenGate HTTP transport backend (default: `http://localhost:8080`).

### Environment Variables

```bash
# Development only - customize the compatibility backend port
BIFROST_PORT=8080
```

## Architecture

### Technology Stack

- **Framework**: React 19 + Vite + TanStack Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Radix UI components
- **State Management**: Redux Toolkit with RTK Query
- **Real-time**: WebSocket integration
- **HTTP Client**: Axios with typed service layer
- **Theme**: Dark/light mode support

### Integration Model

```
┌─────────────────┐    HTTP/WebSocket    ┌──────────────────┐
│ FrankenGate UI  │ ◄─────────────────► │ FrankenGate HTTP  │
│   (React+Vite)  │                     │ Transport (Go)   │
└─────────────────┘                     └──────────────────┘
        │                                        │
        │ Build artifacts                        │
        └────────────────────────────────────────┘
```

- **Development**: UI runs on port 3000, connects to Go backend on port 8080
- **Production**: UI built as static assets served directly by Go HTTP transport
- **Communication**: REST API + WebSocket for real-time features

## Features

### Real-time Log Monitoring

The main dashboard provides comprehensive request monitoring with live updates via WebSocket, advanced filtering, and detailed request/response inspection.

**[Learn More →](https://github.com/pierretokns/frankengate/tree/dev/docs)**

### Provider Configuration

Manage all your AI providers from a unified interface with support for multiple API keys, custom network configuration, and provider-specific settings.

**[View All Providers →](https://github.com/pierretokns/frankengate/tree/dev/docs/providers)**

### MCP Client Management

Model Context Protocol integration for advanced AI capabilities including tool integration and connection monitoring.

**[MCP Documentation →](https://github.com/pierretokns/frankengate/tree/dev/docs/mcp)**

### Plugin Ecosystem

Extend FrankenGate with powerful plugins for observability, testing, caching, and custom functionality.

**Available Plugins:**

- Maxim Logger - Advanced LLM observability
- Response Mocker - Mock responses for testing
- Semantic Cache - Intelligent response caching
- OpenTelemetry - Distributed tracing

**[Plugin Development Guide →](https://github.com/pierretokns/frankengate/tree/dev/plugins)**

## Development

### Project Structure

```
ui/
├── app/                    # TanStack Router pages
│   ├── page.tsx           # Main logs dashboard
│   ├── config/            # Provider & MCP configuration
│   ├── docs/              # Documentation browser
│   └── plugins/           # Plugin management
├── components/            # Reusable UI components
│   ├── logs/             # Log monitoring components
│   ├── config/           # Configuration forms
│   └── ui/               # Base UI components (Radix)
├── hooks/                # Custom React hooks
├── lib/                  # Utilities and services
│   ├── store/            # Redux store and API slices
│   ├── types/            # TypeScript definitions
│   └── utils/            # Helper functions
└── scripts/              # Build and deployment scripts
```

### API Integration

The UI uses Redux Toolkit + RTK Query for state management and API communication with the FrankenGate HTTP transport backend:

```typescript
// Example API usage with RTK Query
import { useGetLogsQuery, useCreateProviderMutation, getErrorMessage } from "@/lib/store";

// Get real-time logs with automatic caching
const { data: logs, error, isLoading } = useGetLogsQuery({ filters, pagination });

// Configure provider with optimistic updates
const [createProvider] = useCreateProviderMutation();

const handleCreate = async () => {
	try {
		await createProvider({
			provider: "openai",
			keys: [{ value: "sk-...", models: ["gpt-4"], weight: 1 }],
			// ... other config
		}).unwrap();
		// Success handling
	} catch (error) {
		console.error(getErrorMessage(error));
	}
};
```

### Component Guidelines

- **Composition**: Use Radix UI primitives for accessibility
- **Styling**: Tailwind CSS with CSS variables for theming
- **Types**: Full TypeScript coverage matching Go backend schemas
- **Error Handling**: Consistent error states and user feedback

### Adding New Features

1. **Backend Integration**: Add API endpoints to RTK Query slices in `lib/store/`
2. **Type Definitions**: Update types in `lib/types/`
3. **UI Components**: Build with Radix UI and Tailwind
4. **State Management**: Use RTK Query for API state, React hooks for local state
5. **Real-time Updates**: Integrate WebSocket events when applicable

## Configuration

### Provider Setup

The UI supports comprehensive provider configuration including API keys with model assignments, network settings, and provider-specific options.

**[Complete Provider Configuration Guide →](https://github.com/pierretokns/frankengate/tree/dev/docs/providers)**

### Governance & Access Control

Configure virtual keys, budget limits, rate limiting, and team-based access control through the UI.

**[Governance Documentation →](https://github.com/pierretokns/frankengate/tree/dev/docs/enterprise)**

### Real-time Features

WebSocket connection provides live log streaming, connection status monitoring, automatic reconnection, and filtered real-time updates.

**[Observability Features →](https://github.com/pierretokns/frankengate/tree/dev/docs/plugins)**

## Monitoring & Analytics

The dashboard provides comprehensive observability including request metrics, token usage tracking, provider performance analysis, error categorization, and historical trend analysis.

**[Performance Benchmarks →](https://github.com/pierretokns/frankengate/tree/dev/docs/benchmarking)**

## Contributing

We welcome contributions! See the [contributing guide](https://github.com/pierretokns/frankengate/blob/dev/CONTRIBUTING.md) for:

- Code conventions and style guide
- Development setup and workflow
- Adding new providers or features
- Plugin development guidelines

## Documentation

**Complete Documentation:** [FrankenGate documentation](https://github.com/pierretokns/frankengate/tree/dev/docs)

### Quick Links

- [Gateway Setup](https://github.com/pierretokns/frankengate/tree/dev/docs) - Get started
- [Provider Configuration](https://github.com/pierretokns/frankengate/tree/dev/docs/providers) - Multi-provider setup
- [MCP Integration](https://github.com/pierretokns/frankengate/tree/dev/docs/mcp) - External tool calling
- [Plugin Development](https://github.com/pierretokns/frankengate/tree/dev/plugins) - Build custom plugins
- [Architecture](https://github.com/pierretokns/frankengate/tree/dev/docs/architecture) - System design and internals

## Need Help?

**[Join our Discord](https://discord.gg/exN5KAydbU)** for community support and discussions.

Get help with:

- Quick setup assistance and troubleshooting
- Best practices and configuration tips
- Community discussions and support
- Real-time help with integrations

## Links

- **Main Repository**: [github.com/pierretokns/frankengate](https://github.com/pierretokns/frankengate)
- **HTTP Transport**: [../transports/bifrost-http](../transports/bifrost-http)
- **Documentation**: [FrankenGate docs](https://github.com/pierretokns/frankengate/tree/dev/docs)
- **Website**: Pending fork-owned documentation site

## License

Licensed under the Apache 2.0 License - see the [LICENSE](../LICENSE) file for details.

---

Built with ❤️ by the FrankenGate contributors, with attribution preserved in [NOTICE](../NOTICE).
