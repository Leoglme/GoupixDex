/**
 * Turn an Axios-style or unknown error into a short user-facing French message.
 *
 * @param e - Caught rejection (typically Axios error with `response.data.detail`).
 * @returns {string} Single-line message suitable for toasts / inline alerts.
 */
export function apiErrorMessage(e: unknown): string {
  if (!e || typeof e !== 'object') {
    return 'Erreur inconnue'
  }
  const err = e as {
    message?: string
    code?: string
    response?: { status?: number; data?: { detail?: unknown } }
  }

  const data = err.response?.data
  const d = data?.detail
  if (typeof d === 'string') {
    return d
  }
  if (Array.isArray(d)) {
    return d
      .map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : JSON.stringify(x)))
      .join(' · ')
  }

  if (!err.response) {
    const msg = typeof err.message === 'string' ? err.message.trim() : ''
    if (msg) {
      const head =
        err.code === 'ECONNREFUSED' || err.code === 'ERR_NETWORK' || err.code === 'ECONNABORTED'
          ? 'Impossible de joindre l’API'
          : err.code === 'ERR_CANCELED'
            ? 'Requête annulée'
            : 'Erreur réseau'
      return `${head} — ${msg}`
    }
    return 'Erreur réseau (aucune réponse du serveur). Vérifiez que l’API tourne et que NUXT_PUBLIC_API_BASE est correct.'
  }

  const status = err.response.status
  if (typeof status === 'number') {
    return `Erreur HTTP ${status}`
  }
  return 'Erreur'
}
