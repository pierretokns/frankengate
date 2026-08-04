import { expect, test } from '../../core/fixtures/base.fixture'
import { AgentModelCardsPage } from './pages/agent-model-cards.page'

const coreConfig = {
  is_db_connected: true,
  is_logs_connected: true,
  env_label: 'e2e',
  auth_config: { is_enabled: false },
}

const listResponse = {
  schema_version: 'bifrost.agent_model_cards.api.v1',
  card_schema_version: 'bifrost.agent_model_card.v1alpha1',
  revision: { id: 'rev-agent-cards-e2e', card_count: 2 },
  source_precedence: ['key_config', 'live_list_models', 'datasheet_pricing', 'model_parameters'],
  sources: [
    { kind: 'key_config', revision: 'keys-rev', freshness: 'local_cache_no_timestamp', details: { timestamp: 'not_tracked' } },
    { kind: 'live_list_models', revision: 'live-rev', freshness: 'local_cache_no_timestamp', details: { entry_count: '2' } },
    { kind: 'datasheet_pricing', revision: '2026-08-04T12:00:00Z', freshness: 'fresh', details: { last_synced_at: '2026-08-04T12:00:00Z' } },
    { kind: 'model_parameters', revision: 'co_loaded_with_modelcatalog', freshness: 'shared_with_datasheet' },
  ],
  unknown_behavior: {
    capability_state: 'models without an authoritative datasheet/provider capability row compile as unknown, never unsupported',
    admission: 'unknown capabilities preserve existing ModelCatalog behavior and remain provider-owned at request time',
    pricing: 'unknown pricing compiles as nil',
  },
  deprecated_behavior: {
    visibility: 'deprecated datasheet rows remain visible',
    admission: 'deprecated is metadata only',
  },
  cards: [
    {
      provider: 'openai',
      model: 'gpt-4o',
      base_model: 'gpt-4o',
      capability_state: 'known',
      is_deprecated: false,
      sources: ['key_config', 'live_list_models', 'datasheet_pricing', 'model_parameters'],
      provider_mapping: {
        provider: 'openai',
        requested_model: 'gpt-4o',
        wire_model: 'gpt-4o',
        canonical_model: 'gpt-4o',
      },
      supported_request_types: ['chat_completion', 'responses'],
      supported_parameters: ['temperature', 'max_tokens'],
      limits: { context_length: 128000, max_input_tokens: 128000, max_output_tokens: 16384 },
      pricing: { input_cost_per_token: 0.0000025, output_cost_per_token: 0.00001 },
      routable_key_ids: ['key-openai'],
      live_key_ids: ['key-openai'],
    },
    {
      provider: 'anthropic',
      model: 'claude-sonnet-4',
      base_model: 'claude-sonnet-4',
      capability_state: 'unknown',
      sources: ['key_config'],
      provider_mapping: {
        provider: 'anthropic',
        requested_model: 'claude-sonnet-4',
        wire_model: 'claude-sonnet-4',
      },
      supported_request_types: [],
      limits: {},
    },
  ],
  total: 2,
  limit: 25,
  offset: 0,
  has_more: false,
}

async function installMocks(page: import('@playwright/test').Page) {
  await page.route('**/api/config**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(coreConfig) }))
  await page.route('**/api/version', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify('v0.0.0-e2e') }))
  await page.route('**/api/session/ws-ticket', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ticket: 'e2e-ticket' }) }))
  await page.route('https://api.github.com/repos/pierretokns/frankengate/releases/latest', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tag_name: 'v0.0.0-e2e', html_url: 'https://example.test/release' }) })
  )
  await page.route('**/api/v1/agent-model-cards**', route => {
    const url = new URL(route.request().url())
    if (!url.pathname.endsWith('/api/v1/agent-model-cards/detail')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(listResponse) })
    }

    const provider = url.searchParams.get('provider')
    const model = url.searchParams.get('model')
    const card = listResponse.cards.find(item => item.provider === provider && item.model === model)
    if (!card) {
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: { message: 'agent model card not found' } }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        schema_version: listResponse.schema_version,
        card_schema_version: listResponse.card_schema_version,
        revision: listResponse.revision,
        card,
      }),
    })
  })
}

test.describe('Agent Model Cards', () => {
  test('renders list, detail, trust and freshness badges', async ({ page }) => {
    await installMocks(page)
    const agentModelCardsPage = new AgentModelCardsPage(page)

    await agentModelCardsPage.goto()

    await expect(agentModelCardsPage.heading).toContainText('Agent Model Cards')
    await expect(page.getByTestId('agent-model-cards-page').getByText('FrankenGate')).toBeVisible()
    await expect(agentModelCardsPage.row('openai', 'gpt-4o')).toBeVisible()
    await expect(agentModelCardsPage.trustBadge('openai', 'gpt-4o')).toContainText('Verified')
    await expect(agentModelCardsPage.freshnessBadge('openai', 'gpt-4o')).toContainText(/Fresh|Local Cache/)
    await expect(agentModelCardsPage.detail).toBeVisible()
    await expect(page.getByTestId('agent-model-card-detail-title')).toContainText('gpt-4o')
    await expect(page.getByTestId('agent-model-card-detail-wire-model')).toContainText('gpt-4o')

    await agentModelCardsPage.row('anthropic', 'claude-sonnet-4').click()
    await expect(page.getByTestId('agent-model-card-detail-title')).toContainText('claude-sonnet-4')
    await expect(agentModelCardsPage.trustBadge('anthropic', 'claude-sonnet-4')).toContainText('Capability Unknown')
  })
})
