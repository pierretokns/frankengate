import { Locator, Page } from '@playwright/test'
import { BasePage } from '../../../core/pages/base.page'
import { waitForNetworkIdle } from '../../../core/utils/test-helpers'

export class AgentModelCardsPage extends BasePage {
  readonly heading: Locator
  readonly list: Locator
  readonly detail: Locator
  readonly searchInput: Locator

  constructor(page: Page) {
    super(page)
    this.heading = page.getByTestId('agent-model-cards-heading')
    this.list = page.getByTestId('agent-model-cards-list')
    this.detail = page.getByTestId('agent-model-card-detail')
    this.searchInput = page.getByTestId('agent-model-cards-search-input')
  }

  async goto(): Promise<void> {
    await this.page.goto('/workspace/agent-model-cards')
    await waitForNetworkIdle(this.page)
  }

  row(provider: string, model: string): Locator {
    return this.page.getByTestId(`agent-model-card-row-${slug(provider)}-${slug(model)}`)
  }

  trustBadge(provider: string, model: string): Locator {
    return this.page.getByTestId(`agent-model-card-trust-badge-${slug(provider)}-${slug(model)}`).first()
  }

  freshnessBadge(provider: string, model: string): Locator {
    return this.page.getByTestId(`agent-model-card-freshness-badge-${slug(provider)}-${slug(model)}`).first()
  }
}

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'unknown'
}
