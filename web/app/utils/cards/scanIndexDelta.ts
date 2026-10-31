/**
 * URL d'un complément de l'index de scan livré, que l'API calcule chaque nuit pour les cartes qui lui manquent.
 * @param {string} path - Chemin du complément (`phash-delta`, `embed-delta`).
 * @returns {string} URL absolue de `GET /scan-index/<path>`.
 */
function scanIndexDeltaUrl(path: string): string {
  const apiBase: string = String(useRuntimeConfig().public.apiBase || '').replace(/\/$/, '')
  return `${apiBase}/scan-index/${path}`
}

/**
 * URL des empreintes pHash que l'API calcule chaque nuit pour les cartes absentes de l'index de scan livré.
 * @returns {string} URL absolue de `GET /scan-index/phash-delta`.
 */
export function scanPhashDeltaUrl(): string {
  return scanIndexDeltaUrl('phash-delta')
}

/**
 * URL des embeddings que l'API calcule chaque nuit pour les cartes absentes de l'index visuel livré (sets JA récents).
 * @returns {string} URL absolue de `GET /scan-index/embed-delta`.
 */
export function scanEmbedDeltaUrl(): string {
  return scanIndexDeltaUrl('embed-delta')
}
