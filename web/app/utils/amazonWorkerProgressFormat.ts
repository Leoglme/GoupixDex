import type { AmazonWorkerProgressPayload } from '~/types/amazonWorkerProgress'

/**
 * Format a worker progress payload as one human-readable log line (French UI copy).
 * @param payload - Raw JSON from `/ws/progress`.
 * @returns Single line with a short time prefix.
 */
export function formatAmazonWorkerProgressLine(payload: AmazonWorkerProgressPayload): string {
  const ts = new Date().toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  const st = payload.status
  const msg = payload.message?.trim() ?? ''

  if (st === 'starting') {
    return `[${ts}] Démarrage — ${msg}`
  }
  if (st === 'searching') {
    const pg = payload.current_page ?? '?'
    const tot = payload.total_pages ?? '?'
    const found = payload.items_found ?? 0
    return `[${ts}] Page ${pg}/${tot} — ${found} article(s) « invitation » cumulé(s). ${msg}`
  }
  if (st === 'page_done') {
    return `[${ts}] ${msg}`
  }
  if (st === 'search_done') {
    return `[${ts}] ${msg}`
  }
  if (st === 'item_found') {
    const title = payload.item_title?.trim()
    const asin = payload.asin?.trim()
    const bit = title || asin || 'Article'
    return `[${ts}] ${bit}${msg ? ` — ${msg}` : ''}`
  }
  if (st === 'checking_phase') {
    return `[${ts}] Vérification des invitations sur les fiches produit… ${msg}`.trim()
  }
  if (st === 'checking') {
    const pg = payload.current_page ?? '?'
    const tot = payload.total_pages ?? '?'
    const asin = payload.asin?.trim()
    const title = payload.item_title?.trim()
    const detail = title ? `${title}${asin ? ` (${asin})` : ''}` : (asin ?? '')
    return `[${ts}] Vérification ${pg}/${tot}${detail ? ` — ${detail}` : ''}. ${msg}`
  }
  if (st === 'completed') {
    const n = payload.items_found
    return `[${ts}] Terminé — ${n != null ? `${n} article(s). ` : ''}${msg}`
  }
  if (st === 'error') {
    return `[${ts}] Erreur — ${msg}`
  }

  return `[${ts}] ${msg || st}`
}
