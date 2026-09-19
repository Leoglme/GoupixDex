import type { Ref } from 'vue'
import type { GoupixArticleMutationNotice, GoupixDrawerStackEntry } from '~/types/GoupixDrawerStack'

const DRAWER_STACK_STORAGE_KEY = 'goupix-drawer-stack'

let restoredFromSession = false

/**
 * Persistent right-side drawer stack (survives route changes via `GoupixDexDrawerStackHost` in the layout).
 */
export function useGoupixDrawerStack() {
  const stack: Ref<GoupixDrawerStackEntry[]> = useState<GoupixDrawerStackEntry[]>('goupix-drawer-stack', () => [])
  const articleBrowseIds: Ref<number[]> = useState<number[]>('goupix-drawer-article-browse', () => [])
  const articleMutationCounter = useState<number>('goupix-drawer-article-mutation-counter', () => 0)
  const lastArticleMutation = useState<GoupixArticleMutationNotice | null>('goupix-drawer-article-mutation', () => null)

  /**
   *
   */
  function restoreStackFromSession(): void {
    if (!import.meta.client || restoredFromSession) {
      return
    }
    restoredFromSession = true
    if (stack.value.length > 0) {
      return
    }
    try {
      const raw = sessionStorage.getItem(DRAWER_STACK_STORAGE_KEY)
      if (raw) {
        stack.value = JSON.parse(raw) as GoupixDrawerStackEntry[]
      }
    } catch {
      /* ignore */
    }
  }

  watch(
    stack,
    (value) => {
      if (!import.meta.client) {
        return
      }
      try {
        sessionStorage.setItem(DRAWER_STACK_STORAGE_KEY, JSON.stringify(value))
      } catch {
        /* quota */
      }
    },
    { deep: true },
  )

  const topEntry = computed(() => stack.value[stack.value.length - 1] ?? null)
  const hasPrevious = computed(() => stack.value.length > 1)

  /**
   *
   */
  function push(entry: GoupixDrawerStackEntry): void {
    restoreStackFromSession()
    const top = stack.value[stack.value.length - 1]
    if (top && top.kind === entry.kind) {
      stack.value.splice(stack.value.length - 1, 1, entry)
      return
    }
    stack.value.push(entry)
  }

  /**
   *
   */
  function pushArticle(articleId: number): void {
    push({ kind: 'article', articleId })
  }

  /**
   *
   */
  function back(): void {
    stack.value.pop()
  }

  /**
   *
   */
  function closeAll(): void {
    stack.value = []
    articleBrowseIds.value = []
  }

  /**
   *
   */
  function setArticleBrowseList(ids: number[]): void {
    articleBrowseIds.value = ids
  }

  /**
   *
   */
  function notifyArticleUpdated(articleId: number): void {
    lastArticleMutation.value = { type: 'updated', articleId }
    articleMutationCounter.value += 1
  }

  return {
    stack,
    topEntry,
    hasPrevious,
    articleBrowseIds,
    articleMutationCounter,
    lastArticleMutation,
    push,
    pushArticle,
    back,
    closeAll,
    setArticleBrowseList,
    notifyArticleUpdated,
    restoreStackFromSession,
  }
}
