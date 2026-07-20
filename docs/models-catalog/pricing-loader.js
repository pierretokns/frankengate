/*
 * Site-side pricing loader. The scheduled pricing-sync job publishes the
 * generated envelope at /data/pricing/latest.json. The validated upstream
 * snapshot is also published locally, so the site never calls the upstream
 * product directly at runtime.
 */
(function (root) {
  const defaultPaths = ['/data/pricing/latest.json', 'data/pricing/latest.json', '/data/pricing/latest-upstream.json', 'data/pricing/latest-upstream.json']

  function normalize (payload) {
    const document = payload && payload.models ? payload.models : payload
    if (!document || typeof document !== 'object') throw new Error('Invalid pricing document')
    const models = Array.isArray(document)
      ? document
      : Object.entries(document).map(([model, config]) => ({ model, ...config }))
    if (!models.length || models.some((model) => !model || typeof model !== 'object')) throw new Error('Pricing document contains no models')
    return { models, source: payload.source || null, retrievedAt: payload.retrieved_at || null, cached: Boolean(payload.models) }
  }

  async function load (options) {
    const fetchImpl = (options && options.fetchImpl) || root.fetch.bind(root)
    const paths = (options && options.paths) || defaultPaths
    let lastError
    for (const path of paths) {
      try {
        const response = await fetchImpl(path, { headers: { Accept: 'application/json' } })
        if (!response.ok) throw new Error(`Pricing request failed: ${response.status}`)
        return normalize(await response.json())
      } catch (error) { lastError = error }
    }
    throw lastError || new Error('Pricing catalog unavailable')
  }

  root.FrankenGatePricing = { load, normalize }
})(typeof window !== 'undefined' ? window : globalThis)
