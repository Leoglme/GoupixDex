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
  if (d && typeof d === 'object' && 'code' in d && (d as { code: string }).code === 'invalid_stamp_pdf') {
    const det = d as { message?: string; parcel_index?: number }
    const idx = typeof det.parcel_index === 'number' ? det.parcel_index + 1 : null
    const base = typeof det.message === 'string' ? det.message : 'PDF timbre invalide.'
    return idx != null ? `${base} (parcel ${idx})` : base
  }
  if (typeof d === 'string') {
    return d
  }
  if (d && typeof d === 'object' && 'message' in d && typeof (d as { message: unknown }).message === 'string') {
    return (d as { message: string }).message
  }
  if (Array.isArray(d)) {
    return d
      .map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : JSON.stringify(x)))
      .join(' · ')
  }
  return 'Erreur'
}
