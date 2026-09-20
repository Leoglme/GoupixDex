/** Navigation file d’attente après remise en vente (query `queue=id1,id2`). */

export function parseRelistQueueParam(raw: unknown): number[] {
  if (typeof raw !== 'string' || !raw.trim()) {
    return []
  }
  return raw
    .split(',')
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isFinite(n) && n > 0)
}

export function relistEditLocation(
  firstId: number,
  queueIds: number[],
): { path: string; query: Record<string, string> } {
  const rest = queueIds.filter((id) => id !== firstId)
  const query: Record<string, string> = { relist: '1' }
  if (rest.length) {
    query.queue = rest.join(',')
  }
  return { path: `/articles/${firstId}/edit`, query }
}

export const RELIST_QUEUE_STORAGE_KEY = 'goupix-pending-relist-queue'

export function persistRelistQueue(ids: number[]): void {
  if (typeof sessionStorage === 'undefined' || !ids.length) {
    return
  }
  sessionStorage.setItem(RELIST_QUEUE_STORAGE_KEY, JSON.stringify(ids))
}

export function loadPersistedRelistQueue(): number[] {
  if (typeof sessionStorage === 'undefined') {
    return []
  }
  const raw = sessionStorage.getItem(RELIST_QUEUE_STORAGE_KEY)
  if (!raw) {
    return []
  }
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter((n): n is number => typeof n === 'number' && Number.isFinite(n) && n > 0)
  } catch {
    return []
  }
}

/** Après édition d’un article, passe au suivant dans la file (`queue` = ids restants). */
export function relistSuccessorLocation(queueTail: number[]): { path: string; query: Record<string, string> } | null {
  if (!queueTail.length) {
    return null
  }
  const nextId = queueTail[0]!
  const newTail = queueTail.slice(1)
  const query: Record<string, string> = { relist: '1' }
  if (newTail.length) {
    query.queue = newTail.join(',')
  }
  return { path: `/articles/${nextId}/edit`, query }
}

export async function navigateToRelistEditorFromStorage(): Promise<void> {
  const ids = loadPersistedRelistQueue()
  if (!ids.length) {
    await navigateTo('/articles')
    return
  }
  await navigateTo(relistEditLocation(ids[0]!, ids))
}
