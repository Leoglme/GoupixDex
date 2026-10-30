/**
 * URL des empreintes que l'API calcule chaque nuit pour les cartes absentes de l'index de scan livré.
 * @returns {string} URL absolue de `GET /scan-index/phash-delta`.
 */
export function scanPhashDeltaUrl(): string {
  const apiBase: string = String(useRuntimeConfig().public.apiBase || '').replace(/\/$/, '')
  return `${apiBase}/scan-index/phash-delta`
}
