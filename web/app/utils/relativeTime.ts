/**
 * Format a delta in hours as a human-readable French relative time
 * (« il y a 2 min », « il y a 3 h », « il y a 5 j », « il y a 2 sem »…).
 *
 * Returns an empty string when the input is null / undefined / non-finite,
 * so templates can safely render the result with a ``v-if`` on truthiness.
 *
 * @param hours - Number of hours since the event (>= 0).
 * @returns A non-empty French label, or `''` if the input is unusable.
 */
export function formatRelativeHours(hours: number | null | undefined): string {
  if (hours == null || !Number.isFinite(hours) || hours < 0) {
    return ''
  }
  if (hours < 1 / 60) {
    return 'à l\'instant'
  }
  if (hours < 1) {
    const mins = Math.max(1, Math.round(hours * 60))
    return `il y a ${mins} min`
  }
  if (hours < 24) {
    const h = Math.max(1, Math.round(hours))
    return `il y a ${h} h`
  }
  const days = Math.round(hours / 24)
  if (days < 7) {
    return `il y a ${days} j`
  }
  if (days < 31) {
    const weeks = Math.round(days / 7)
    return `il y a ${weeks} sem`
  }
  const months = Math.round(days / 30)
  if (months < 12) {
    return `il y a ${months} mois`
  }
  const years = Math.round(days / 365)
  return `il y a ${years} an${years > 1 ? 's' : ''}`
}
