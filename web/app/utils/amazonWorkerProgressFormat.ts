import type { AmazonWorkerProgressPayload } from '~/types/amazonWorkerProgress'

/**
 * Préfixe « [compte i/n] » quand le worker vérifie les comptes l’un après l’autre.
 * @param payload - Raw JSON from `/ws/progress`.
 * @returns Prefix with trailing space, or an empty string.
 */
function accountScopePrefix(payload: AmazonWorkerProgressPayload): string {
  if (payload.account_index == null || payload.account_total == null) {
    return ''
  }
  return `[compte ${payload.account_index}/${payload.account_total}] `
}

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
  const head = `[${ts}] ${accountScopePrefix(payload)}`
  const st = payload.status
  const msg = payload.message?.trim() ?? ''

  if (st === 'starting') {
    return `${head}Démarrage — ${msg}`
  }
  if (st === 'searching') {
    const pg = payload.current_page ?? '?'
    const tot = payload.total_pages ?? '?'
    const found = payload.items_found ?? 0
    return `${head}Page ${pg}/${tot} — ${found} article(s) « invitation » cumulé(s). ${msg}`
  }
  if (st === 'page_done') {
    return `${head}${msg}`
  }
  if (st === 'search_done') {
    return `${head}${msg}`
  }
  if (st === 'item_found') {
    const title = payload.item_title?.trim()
    const asin = payload.asin?.trim()
    const bit = title || asin || 'Article'
    return `${head}${bit}${msg ? ` — ${msg}` : ''}`
  }
  if (st === 'checking_phase') {
    return `${head}Vérification des invitations sur les fiches produit… ${msg}`.trim()
  }
  if (st === 'checking') {
    const pg = payload.current_page ?? '?'
    const tot = payload.total_pages ?? '?'
    const asin = payload.asin?.trim()
    const title = payload.item_title?.trim()
    const detail = title ? `${title}${asin ? ` (${asin})` : ''}` : (asin ?? '')
    return `${head}Vérification ${pg}/${tot}${detail ? ` — ${detail}` : ''}. ${msg}`
  }
  if (st === 'account_done') {
    return `${head}${msg}`
  }
  if (st === 'completed') {
    const n = payload.items_found
    return `${head}Terminé — ${n != null ? `${n} article(s). ` : ''}${msg}`
  }
  if (st === 'error') {
    return `${head}Erreur — ${msg}`
  }

  return `${head}${msg || st}`
}
