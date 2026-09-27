/** Navigation file d’attente après remise en vente (query `queue=id1,id2`). */

import type { Marketplace } from '~/types/Marketplace'

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

/**
 * Page de modification d'une fiche à vérifier avant publication, suivie des fiches restantes de la série.
 * @param {number} articleId - Fiche à vérifier maintenant.
 * @param {number[]} remainingArticleIds - Fiches à vérifier ensuite, dans l'ordre.
 * @param {Marketplace[]} marketplaces - Marketplaces où publier la série une fois la dernière fiche enregistrée.
 * @param {string} returnPath - Page où revenir une fois la série publiée.
 * @param {number[]} [reviewedArticleIds] - Fiches de la série déjà vérifiées, publiées avec la dernière.
 * @returns {{ path: string; query: Record<string, string> }} La page de modification de la fiche.
 */
export function publishReviewLocation(
  articleId: number,
  remainingArticleIds: number[],
  marketplaces: Marketplace[],
  returnPath: string,
  reviewedArticleIds: number[] = [],
): { path: string; query: Record<string, string> } {
  const query: Record<string, string> = { review: '1', publish: marketplaces.join(','), back: returnPath }
  if (remainingArticleIds.length) {
    query.queue = remainingArticleIds.join(',')
  }
  if (reviewedArticleIds.length) {
    query.reviewed = reviewedArticleIds.join(',')
  }
  return { path: `/articles/${articleId}/edit`, query }
}
