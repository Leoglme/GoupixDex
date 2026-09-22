import type { Ref } from 'vue'
import type { SealedCatalogProduct } from '~/composables/useSealedCatalog'
import type {
  GoupixArticleMutationNotice,
  GoupixCardMutationNotice,
  GoupixCatalogCardRef,
  GoupixDrawerStackEntry,
  GoupixSealedMutationNotice,
} from '~/types/GoupixDrawerStack'

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
  const sealedMutationCounter = useState<number>('goupix-drawer-sealed-mutation-counter', () => 0)
  const lastSealedMutation = useState<GoupixSealedMutationNotice | null>('goupix-drawer-sealed-mutation', () => null)
  const cardMutationCounter = useState<number>('goupix-drawer-card-mutation-counter', () => 0)
  const lastCardMutation = useState<GoupixCardMutationNotice | null>('goupix-drawer-card-mutation', () => null)

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
   * Ouvre (ou remplace le sommet par) la fiche d'un produit scellé.
   * @param sealedId - Identifiant du produit scellé.
   */
  function pushSealed(sealedId: number): void {
    push({ kind: 'sealed', sealedId })
  }

  /**
   * Ouvre (ou remplace le sommet par) la fiche d'une carte de collection.
   * @param cardId - Identifiant de la carte de collection.
   */
  function pushCard(cardId: number): void {
    push({ kind: 'card', cardId })
  }

  /**
   * Ouvre l'aperçu d'un produit du catalogue scellé (avant ajout à la collection).
   * @param product - Produit du catalogue scellé.
   * @param expansionName - Nom de l'extension d'origine.
   */
  function pushSealedCatalog(product: SealedCatalogProduct, expansionName: string): void {
    push({ kind: 'catalog-sealed', product, expansionName })
  }

  /**
   * Ouvre l'aperçu d'une carte du catalogue TCGdex (avant ajout à la collection).
   * @param card - Carte du catalogue (id TCGdex, nom, set, langue).
   */
  function pushCatalogCard(card: GoupixCatalogCardRef): void {
    push({ kind: 'catalog-card', card })
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

  /**
   * Signale qu'un produit scellé a été modifié (les listes ouvertes se resynchronisent).
   * @param sealedId - Identifiant du produit scellé.
   */
  function notifySealedUpdated(sealedId: number): void {
    lastSealedMutation.value = { type: 'updated', sealedId }
    sealedMutationCounter.value += 1
  }

  /**
   * Signale qu'un produit scellé a été supprimé.
   * @param sealedId - Identifiant du produit scellé.
   */
  function notifySealedDeleted(sealedId: number): void {
    lastSealedMutation.value = { type: 'deleted', sealedId }
    sealedMutationCounter.value += 1
  }

  /**
   * Signale qu'une carte de collection a été modifiée (les listes ouvertes se resynchronisent).
   * @param cardId - Identifiant de la carte de collection.
   */
  function notifyCardUpdated(cardId: number): void {
    lastCardMutation.value = { type: 'updated', cardId }
    cardMutationCounter.value += 1
  }

  /**
   * Signale qu'une carte de collection a été supprimée.
   * @param cardId - Identifiant de la carte de collection.
   */
  function notifyCardDeleted(cardId: number): void {
    lastCardMutation.value = { type: 'deleted', cardId }
    cardMutationCounter.value += 1
  }

  return {
    stack,
    topEntry,
    hasPrevious,
    articleBrowseIds,
    articleMutationCounter,
    lastArticleMutation,
    sealedMutationCounter,
    lastSealedMutation,
    cardMutationCounter,
    lastCardMutation,
    push,
    pushArticle,
    pushSealed,
    pushCard,
    pushSealedCatalog,
    pushCatalogCard,
    back,
    closeAll,
    setArticleBrowseList,
    notifyArticleUpdated,
    notifySealedUpdated,
    notifySealedDeleted,
    notifyCardUpdated,
    notifyCardDeleted,
    restoreStackFromSession,
  }
}
