import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { Article } from '~/composables/useArticles'
import type {
  EbayLeboncoinChannels,
  EbayLeboncoinDelist,
  EbayLeboncoinDelistFailure,
} from '~/types/EbayLeboncoinDelist'
import type { ArticleSaleConfirmation } from '~/types/GoupixDexArticleMarkSoldDrawer'
import type { Marketplace } from '~/types/Marketplace'
import type { PublishReviewChoice } from '~/types/PublishReviewPrompt'
import { useBulkMarketplacePublication } from '~/composables/useBulkMarketplacePublication'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'
import { useEbayLeboncoinDelist } from '~/composables/useEbayLeboncoinDelist'
import { usePublishReviewPrompt } from '~/composables/usePublishReviewPrompt'
import { useSoldArticleListingsRemoval } from '~/composables/useSoldArticleListingsRemoval'
import { persistRelistQueue, publishReviewLocation, relistEditLocation } from '~/utils/articleRelistQueue'
import { MARKETPLACES } from '~/utils/marketplaces'
import {
  articleEligibleForBulkRelist,
  articleEligibleForVintedRelist,
  articleWithdrawnFromSale,
  type BulkRelistModalMode,
} from '~/utils/articleSaleState'

export type ArticlesListPageVariant = 'listed'

/**
 * Shared list-page logic for “Mes articles” (unsold rows linked to the selling workflow).
 *
 * @param variant - `'listed'` shows all articles not yet marked sold.
 * @returns Reactive state, computed lists, modals, and CRUD/publish helpers for both pages.
 */
export function useArticlesListPageCore(variant: ArticlesListPageVariant) {
  const {
    listArticles,
    deleteArticle,
    deleteArticlesBulk,
    markSold,
    retryCrossEbayRemoval,
    vintedUnlistAfterEbaySale,
    startVintedBatchDelist,
    bulkPrepareForSale,
  } = useArticles()
  const route: RouteLocationNormalizedLoaded = useRoute()
  const toast = useToast()
  const { canUseDesktopWorkers, notifyPcUnreachable } = useDesktopWorkers()
  const { removeEbayLeboncoinListings } = useEbayLeboncoinDelist()
  const { removeListingsLeftOnline } = useSoldArticleListingsRemoval()
  const { askWhetherToReviewBeforePublishing } = usePublishReviewPrompt()
  const { startJob } = useWardrobeLocalSync()
  const {
    isVintedChannelEnabled: vintedChannelEnabled,
    canPublishOnEbay: ebayPublishAvailable,
    canPublishOnLeboncoin: leboncoinPublishAvailable,
    loadMarketplaceAvailability,
    startArticlePublish,
  } = useMarketplacePublishing()

  const wardrobeSyncing: Ref<boolean> = ref(false)

  const allArticles = useState<Article[]>('goupix-articles-listed-cache', () => [])
  const loading: Ref<boolean> = ref(allArticles.value.length === 0)

  const soldOpen: Ref<boolean> = ref(false)
  /** Fiches en cours de vente (1 = unitaire, plusieurs = lot). */
  const soldArticles: Ref<Article[] | null> = ref(null)
  const soldSubmitting: Ref<boolean> = ref(false)
  /** Incrémenté après une vente enregistrée pour vider la sélection dans la liste. */
  const articleListSelectionReset: Ref<number> = ref(0)

  const deleteOpen: Ref<boolean> = ref(false)
  const deleteId: Ref<number | null> = ref(null)

  const bulkDeleteOpen: Ref<boolean> = ref(false)
  const bulkDeleteIds: Ref<number[]> = ref([])
  const bulkPublishOpen: Ref<boolean> = ref(false)
  const bulkPublishIds: Ref<number[]> = ref([])
  const { isPublishingInBulk: bulkPublishBusy, publishArticlesInBulk } = useBulkMarketplacePublication(
    articleById,
    refresh,
  )
  const bulkDelistOpen: Ref<boolean> = ref(false)
  const bulkDelistIds: Ref<number[]> = ref([])
  const bulkDelistBusy: Ref<boolean> = ref(false)
  const bulkRelistOpen: Ref<boolean> = ref(false)
  const bulkRelistIds: Ref<number[]> = ref([])
  const bulkRelistBusy: Ref<boolean> = ref(false)

  const displayedArticles = computed(() => allArticles.value.filter((a) => !a.is_sold && (a.offers_for_sale ?? true)))

  const withdrawnFromSaleArticles = computed(() => allArticles.value.filter((a) => articleWithdrawnFromSale(a)))

  const hasAnyArticles = computed(() => allArticles.value.length > 0)

  /**
   * Lookup by primary key in the loaded `allArticles` cache.
   *
   * @param id - Article id.
   * @returns {Article | undefined} Row when present.
   */
  function articleById(id: number): Article | undefined {
    return allArticles.value.find((a) => a.id === id)
  }

  /**
   *
   */
  async function refresh(options?: { background?: boolean }) {
    const background = options?.background ?? allArticles.value.length > 0
    if (!background) {
      loading.value = true
    }
    try {
      allArticles.value = await listArticles()
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    } finally {
      loading.value = false
    }
  }

  const drawerStack = useGoupixDrawerStack()

  watch(
    () => drawerStack.articleMutationCounter.value,
    () => {
      void refresh({ background: true })
    },
  )

  onMounted(async () => {
    const listRefresh = allArticles.value.length === 0 ? refresh() : refresh({ background: true })
    await Promise.all([listRefresh, loadMarketplaceAvailability()])
  })

  /**
   * Ouvre la modale « vendu » pour un ou plusieurs articles (lot : parts égales).
   *
   * @param articles - Liste non vide ; les lignes déjà vendues devraient être exclues par l’appelant.
   */
  function openSold(articles: Article[]) {
    if (!articles.length) {
      return
    }
    soldArticles.value = articles
    soldOpen.value = true
  }

  /**
   * Enregistre la vente puis fait retirer par le PC les annonces restées en ligne ailleurs (Vinted, Leboncoin).
   * @param payload - Vente unitaire ou lot avec répartition calculée côté drawer.
   */
  async function confirmSold(payload: ArticleSaleConfirmation) {
    const rows = soldArticles.value
    if (!rows?.length) {
      return
    }
    soldSubmitting.value = true
    try {
      const soldArticlesAfterSale: Article[] = []
      if (payload.mode === 'single') {
        const id = rows[0]?.id
        if (id == null) {
          return
        }
        soldArticlesAfterSale.push(
          await markSold(id, {
            sold_price: payload.soldPrice,
            sale_source: payload.saleSource,
          }),
        )
        toast.add({ title: 'Article marqué comme vendu', color: 'success' })
      } else {
        for (const a of payload.allocations) {
          soldArticlesAfterSale.push(
            await markSold(a.id, {
              sold_price: a.soldPrice,
              sale_source: payload.saleSource,
            }),
          )
        }
        toast.add({
          title:
            payload.allocations.length > 1
              ? `${payload.allocations.length} articles marqués comme vendus`
              : 'Article marqué comme vendu',
          color: 'success',
        })
      }
      removeListingsLeftOnline(soldArticlesAfterSale)
      soldOpen.value = false
      soldArticles.value = null
      articleListSelectionReset.value += 1
      await refresh()
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    } finally {
      soldSubmitting.value = false
    }
  }

  /**
   *
   */
  async function onRetryCrossEbay(id: number) {
    try {
      await retryCrossEbayRemoval(id)
      toast.add({ title: 'eBay', description: 'Suppression relancée.', color: 'success' })
      await refresh()
    } catch (e) {
      toast.add({ title: 'Erreur eBay', description: apiErrorMessage(e), color: 'error' })
    }
  }

  /**
   *
   */
  async function onRetryCrossVinted(id: number) {
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La suppression Vinted')
      return
    }
    try {
      await vintedUnlistAfterEbaySale(id)
      toast.add({
        title: 'Vinted',
        description: 'Suppression relancée sur ce poste. Actualisation dans quelques secondes…',
        color: 'neutral',
      })
      setTimeout(() => void refresh(), 7000)
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    }
  }

  /**
   *
   */
  async function confirmDelete() {
    if (deleteId.value == null) {
      return
    }
    try {
      await deleteArticle(deleteId.value)
      toast.add({ title: 'Article supprimé', color: 'success' })
      deleteId.value = null
      deleteOpen.value = false
      await refresh()
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    }
  }

  /**
   *
   * @param ids
   */
  function openBulkDelete(ids: number[]) {
    bulkDeleteIds.value = ids
    bulkDeleteOpen.value = true
  }

  /**
   *
   */
  function openBulkPublish(ids: number[]) {
    bulkPublishIds.value = ids
    bulkPublishOpen.value = true
  }

  const bulkPublishChannelDefaults = computed(() => {
    const rows = bulkPublishIds.value.map((id) => articleById(id)).filter((a): a is Article => Boolean(a))
    const wantVinted = rows.some((r) => !r.published_on_vinted)
    const wantEbay = rows.some((r) => !r.published_on_ebay)
    const wantLeboncoin = rows.some((r) => !r.published_on_leboncoin)
    return { vinted: wantVinted, ebay: wantEbay, leboncoin: wantLeboncoin }
  })

  /**
   *
   */
  function openBulkDelist(ids: number[]) {
    bulkDelistIds.value = ids
    bulkDelistOpen.value = true
  }

  /**
   *
   */
  function openBulkRelist(ids: number[]) {
    const eligible = ids.filter((id) => {
      const a = articleById(id)
      return a && articleEligibleForBulkRelist(a)
    })
    if (!eligible.length) {
      toast.add({
        title: 'Relister',
        description:
          'Sélectionnez des articles déjà en ligne sur Vinted, ou des fiches retirées de la vente après un retrait total.',
        color: 'neutral',
      })
      return
    }
    bulkRelistIds.value = eligible
    bulkRelistOpen.value = true
  }

  /**
   *
   */
  function articlesForIds(ids: number[]): Article[] {
    const out: Article[] = []
    for (const id of ids) {
      const a = allArticles.value.find((x) => x.id === id)
      if (a) {
        out.push(a)
      }
    }
    return out
  }

  const bulkDelistChannelState = computed(() => {
    const rows = articlesForIds(bulkDelistIds.value)
    return {
      anyVinted: rows.some((r) => r.published_on_vinted),
      anyEbay: rows.some((r) => r.published_on_ebay),
      anyLeboncoin: rows.some((r) => r.published_on_leboncoin),
    }
  })

  const bulkRelistChannelState = computed(() => {
    const rows = articlesForIds(bulkRelistIds.value)
    const anyVintedListed = rows.some((r) => r.published_on_vinted)
    const anyWithdrawn = rows.some((r) => articleWithdrawnFromSale(r))
    const anyVintedRenew = rows.some((r) => articleEligibleForVintedRelist(r))
    const mode: BulkRelistModalMode = anyVintedRenew ? 'vinted-renew' : 'restore-sale'
    return {
      anyVintedListed,
      anyWithdrawn,
      mode,
    }
  })

  /**
   * Demande s’il faut d’abord modifier les fiches, puis lance la publication groupée sur les canaux cochés ou ouvre la première fiche à vérifier.
   * @param {{ vinted: boolean; ebay: boolean; leboncoin: boolean; refreshVinted?: boolean }} payload - Canaux cochés dans la modale.
   * @returns {Promise<void>} Résolue une fois la publication lancée, la première fiche ouverte, ou la question fermée.
   */
  async function confirmBulkPublish(payload: {
    vinted: boolean
    ebay: boolean
    leboncoin: boolean
    refreshVinted?: boolean
  }): Promise<void> {
    const ids = bulkPublishIds.value
    const [firstId, ...remainingIds]: number[] = ids
    if (firstId === undefined) {
      return
    }
    bulkPublishOpen.value = false
    const marketplaces: Marketplace[] = MARKETPLACES.filter((marketplace: Marketplace): boolean => payload[marketplace])
    const choice: PublishReviewChoice | null = await askWhetherToReviewBeforePublishing({
      subjectLabel: ids.length > 1 ? `${ids.length} articles` : articleById(firstId)?.title || '1 article',
      marketplaces,
    })
    if (choice === 'review') {
      await navigateTo(publishReviewLocation(firstId, remainingIds, marketplaces, route.path))
      return
    }
    if (choice !== 'publish') {
      return
    }
    await publishArticlesInBulk(ids, marketplaces)
  }

  /**
   *
   */
  async function confirmBulkDelete() {
    if (!bulkDeleteIds.value.length) {
      return
    }
    try {
      const r = await deleteArticlesBulk(bulkDeleteIds.value)
      toast.add({
        title:
          r.deleted === r.requested
            ? `${r.deleted} article(s) supprimé(s)`
            : `${r.deleted} supprimé(s) sur ${r.requested} demandé(s)`,
        color: 'success',
      })
      bulkDeleteOpen.value = false
      bulkDeleteIds.value = []
      await refresh()
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    }
  }

  /**
   *
   */
  async function onWardrobeImportFromVinted() {
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La synchronisation Vinted')
      return
    }
    wardrobeSyncing.value = true
    try {
      const jobId = await startJob()
      await navigateTo({
        path: '/articles/listing-logs',
        query: { wardrobe_job: jobId },
      })
    } catch (e) {
      toast.add({
        title: 'Synchronisation Vinted',
        description: apiErrorMessage(e),
        color: 'error',
      })
    } finally {
      wardrobeSyncing.value = false
    }
  }

  /**
   * Publie un article depuis la liste puis ouvre le journal de sa publication.
   *
   * @param a - Article à publier.
   * @param marketplace - Marketplace visée.
   * @returns {Promise<void>} Résolue après la navigation vers le journal (ou l’échec annoncé).
   */
  async function publishArticleAndOpenJournal(a: Article, marketplace: Marketplace): Promise<void> {
    const listingPublish = await startArticlePublish(a, marketplace)
    if (listingPublish) {
      await navigateTo(listingPublish.journalLocation)
    }
  }

  /**
   * Publie un article sur eBay depuis la liste.
   *
   * @param a - Article à publier.
   * @returns {Promise<void>} Résolue après l’ouverture du journal.
   */
  async function onPublishEbay(a: Article): Promise<void> {
    await publishArticleAndOpenJournal(a, 'ebay')
  }

  /**
   * Annonce par un toast le bilan d’un retrait eBay / Leboncoin terminé hors du journal.
   * @param {EbayLeboncoinDelist} delist - Bilan du retrait.
   * @returns {void}
   */
  function announceEbayLeboncoinDelist(delist: EbayLeboncoinDelist): void {
    const removedParts: string[] = []
    if (delist.removedFromEbayCount) {
      removedParts.push(`${delist.removedFromEbayCount} retrait(s) eBay`)
    }
    if (delist.removedFromLeboncoinCount) {
      removedParts.push(`${delist.removedFromLeboncoinCount} retrait(s) Leboncoin`)
    }
    if (removedParts.length) {
      toast.add({ title: 'Retrait enregistré', description: removedParts.join(' · '), color: 'success' })
    }
    const firstFailure: EbayLeboncoinDelistFailure | undefined = delist.failures[0]
    if (firstFailure) {
      toast.add({
        title: `${delist.failures.length} retrait(s) impossible(s)`,
        description: `${firstFailure.articleTitle} : ${firstFailure.reason}`,
        color: 'error',
      })
    }
  }

  /**
   * Retire la sélection des marketplaces cochées : sur desktop, le lot Vinted part d’abord et le journal suit aussi eBay / Leboncoin.
   *
   * @param payload - Marketplaces à retirer.
   * @returns {Promise<void>} Résolue une fois le retrait lancé (ou terminé hors Vinted).
   */
  async function confirmBulkDelist(payload: { vinted: boolean; ebay: boolean; leboncoin: boolean }): Promise<void> {
    const ids = bulkDelistIds.value
    if (!ids.length) {
      return
    }
    bulkDelistOpen.value = false
    bulkDelistBusy.value = true
    try {
      const selectedArticles: Article[] = articlesForIds(ids)
      const vintedDelistIds: number[] = payload.vinted
        ? selectedArticles.filter((row: Article) => row.published_on_vinted).map((row: Article) => row.id)
        : []
      const hasLeboncoinListingToRemove: boolean =
        payload.leboncoin && selectedArticles.some((row: Article): boolean => Boolean(row.published_on_leboncoin))
      const ebayLeboncoinChannels: EbayLeboncoinChannels = {
        ebay: payload.ebay,
        leboncoin: payload.leboncoin && canUseDesktopWorkers.value,
      }
      const ebayLeboncoinArticles: Article[] = selectedArticles.filter(
        (row: Article) =>
          (ebayLeboncoinChannels.ebay && row.published_on_ebay) ||
          (ebayLeboncoinChannels.leboncoin && row.published_on_leboncoin),
      )
      if (vintedDelistIds.length && canUseDesktopWorkers.value) {
        const { job_id } = await startVintedBatchDelist(vintedDelistIds)
        if (ebayLeboncoinArticles.length) {
          // Pas d'attente : le journal suit ce retrait pendant le lot Vinted.
          removeEbayLeboncoinListings(ebayLeboncoinArticles, ebayLeboncoinChannels, job_id)
        }
        articleListSelectionReset.value += 1
        await navigateTo({ path: '/articles/listing-logs', query: { job: job_id, after: 'delist', back: route.path } })
        return
      }

      const unreachableMarketplaceLabels: string[] = [
        ...(vintedDelistIds.length ? ['Vinted'] : []),
        ...(hasLeboncoinListingToRemove && !canUseDesktopWorkers.value ? ['Leboncoin'] : []),
      ]
      if (unreachableMarketplaceLabels.length) {
        notifyPcUnreachable(`Le retrait ${unreachableMarketplaceLabels.join(' et ')}`)
      }
      if (ebayLeboncoinArticles.length) {
        announceEbayLeboncoinDelist(
          await removeEbayLeboncoinListings(ebayLeboncoinArticles, ebayLeboncoinChannels, null),
        )
      } else if (!unreachableMarketplaceLabels.length) {
        toast.add({
          title: 'Aucun retrait',
          description: 'Aucune annonce active sur les canaux choisis pour cette sélection.',
          color: 'neutral',
        })
      }
      articleListSelectionReset.value += 1
      await refresh()
    } catch (e) {
      toast.add({ title: 'Retrait impossible', description: apiErrorMessage(e), color: 'error' })
    } finally {
      bulkDelistBusy.value = false
    }
  }

  /**
   *
   */
  async function confirmBulkRelist(payload: { renewVinted: boolean; mode: BulkRelistModalMode }) {
    const ids = [...bulkRelistIds.value]
    if (!ids.length) {
      return
    }
    bulkRelistOpen.value = false
    bulkRelistBusy.value = true
    try {
      const withdrawnIds = ids.filter((id) => {
        const a = articleById(id)
        return a && articleWithdrawnFromSale(a)
      })
      if (withdrawnIds.length) {
        await bulkPrepareForSale(withdrawnIds)
      }
      persistRelistQueue(ids)
      const rows = articlesForIds(ids)
      const vintedDelistIds = rows.filter((r) => r.published_on_vinted).map((r) => r.id)
      const renewVinted =
        payload.mode === 'vinted-renew' ? vintedDelistIds.length > 0 : payload.renewVinted && vintedDelistIds.length > 0

      if (renewVinted) {
        if (!canUseDesktopWorkers.value) {
          notifyPcUnreachable('Le retrait Vinted avant republication')
          return
        }
        const { job_id } = await startVintedBatchDelist(vintedDelistIds)
        if (job_id) {
          articleListSelectionReset.value += 1
          await navigateTo({
            path: '/articles/listing-logs',
            query: { job: job_id, after: 'relist' },
          })
          return
        }
      }

      articleListSelectionReset.value += 1
      await refresh()
      await navigateTo(relistEditLocation(ids[0]!, ids))
    } catch (e) {
      toast.add({ title: 'Remise en vente', description: apiErrorMessage(e), color: 'error' })
    } finally {
      bulkRelistBusy.value = false
    }
  }

  /**
   * Publie un article sur Leboncoin depuis la liste.
   *
   * @param a - Article à publier.
   * @returns {Promise<void>} Résolue après l’ouverture du journal.
   */
  async function onPublishLeboncoin(a: Article): Promise<void> {
    await publishArticleAndOpenJournal(a, 'leboncoin')
  }

  /**
   * Publie un article sur Vinted depuis la liste.
   *
   * @param a - Article à publier.
   * @returns {Promise<void>} Résolue après l’ouverture du journal.
   */
  async function onPublishVinted(a: Article): Promise<void> {
    await publishArticleAndOpenJournal(a, 'vinted')
  }

  return {
    variant,
    allArticles,
    displayedArticles,
    withdrawnFromSaleArticles,
    hasAnyArticles,
    loading,
    wardrobeSyncing,
    ebayPublishAvailable,
    vintedChannelEnabled,
    leboncoinPublishAvailable,
    soldOpen,
    soldArticles,
    soldSubmitting,
    articleListSelectionReset,
    deleteOpen,
    deleteId,
    bulkDeleteOpen,
    bulkDeleteIds,
    bulkPublishOpen,
    bulkPublishIds,
    bulkPublishChannelDefaults,
    bulkPublishBusy,
    bulkDelistOpen,
    bulkDelistIds,
    bulkDelistBusy,
    bulkDelistChannelState,
    bulkRelistOpen,
    bulkRelistIds,
    bulkRelistBusy,
    bulkRelistChannelState,
    refresh,
    openSold,
    confirmSold,
    confirmDelete,
    openBulkDelete,
    confirmBulkDelete,
    openBulkPublish,
    openBulkDelist,
    openBulkRelist,
    confirmBulkPublish,
    confirmBulkDelist,
    confirmBulkRelist,
    onWardrobeImportFromVinted,
    onPublishEbay,
    onPublishVinted,
    onPublishLeboncoin,
    onRetryCrossEbay,
    onRetryCrossVinted,
  }
}
