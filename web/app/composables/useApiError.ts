/**
 * Turn an Axios-style or unknown error into a short user-facing French message.
 *
 * @param e - Caught rejection (typically Axios error with `response.data.detail`).
 * @returns {string} Single-line message suitable for toasts / inline alerts.
 */
export function apiErrorMessage(e: unknown): string {
  if (!e || typeof e !== 'object' || !('response' in e)) {
    return 'Erreur réseau'
  }
  const data = (e as { response?: { data?: { detail?: unknown } } }).response?.data
  const d = data?.detail
  if (typeof d === 'string') {
    return d
  }
  if (Array.isArray(d)) {
    return d
      .map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : JSON.stringify(x)))
      .join(' · ')
  }
  return 'Erreur'
}
