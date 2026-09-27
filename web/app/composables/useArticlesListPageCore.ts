import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { Article } from '~/composables/useArticles'
import type { EbayLeboncoinDelist, EbayLeboncoinDelistFailure } from '~/types/EbayLeboncoinDelist'
import type { Marketplace } from '~/types/Marketplace'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'
import { useEbayLeboncoinDelist } from '~/composables/useEbayLeboncoinDelist'
import { persistRelistQueue, relistEditLocation } from '~/utils/articleRelistQueue'
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
    publishArticleToLeboncoin,
    startVintedBatch,
    startVintedBatchDelist,
    startEbayBatch,
    bulkPrepareForSale,
  } = useArticles()
  const route: RouteLocationNormalizedLoaded = useRoute()
  const toast = useToast()
  const { canUseDesktopWorkers } = useDesktopWorkers()
  const { removeEbayLeboncoinListings } = useEbayLeboncoinDelist()
  const { startJob } = useWardrobeLocalSync()
  const {
    isVintedChannelEnabled: vintedChannelEnabled,
    canPublishOnEbay: ebayPublishAvailable,
    canPublishOnLeboncoin: leboncoinPublishAvailable,
    loadMarketplaceAvailability,
    ensureLeboncoinPublishReady,
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
  const bulkPublishBusy: Ref<boolean> = ref(false)
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
   * eBay bulk publish requires at least one HTTPS-hosted photo URL.
   *
   * @param a - Article with `images[]`.
   * @returns {boolean} `true` when any image URL starts with `https://`.
   */
  function hasHttpsImage(a: Article) {
    return a.images?.some((img) => (img.image_url || '').startsWith('https://')) ?? false
  }

  /**
   * Filter selection ids to rows that can be published on Vinted (unsold + has photos).
   *
   * @param ids - Selected article ids from the table.
   * @returns {number[]} Eligible subset.
   */
  function eligibleIdsForVintedBulk(ids: number[]) {
    return ids.filter((id) => {
      const a = articleById(id)
      return a && !a.is_sold && (a.images?.length ?? 0) > 0
    })
  }

  /**
   * Filter ids for eBay bulk (HTTPS images, not yet on eBay, unsold).
   *
   * @param ids - Selected article ids.
   * @returns {number[]} Eligible subset.
   */
  function eligibleIdsForEbayBulk(ids: number[]) {
    return ids.filter((id) => {
      const a = articleById(id)
      return a && !a.is_sold && !(a.published_on_ebay ?? false) && hasHttpsImage(a)
    })
  }

  /**
   * Intersection of Vinted + eBay eligibility for dual-channel bulk.
   *
   * @param ids - Selected article ids.
   * @returns {number[]} Eligible subset for both channels.
   */
  function eligibleIdsForDualBulk(ids: number[]) {
    const v = new Set(eligibleIdsForVintedBulk(ids))
    return eligibleIdsForEbayBulk(ids).filter((id) => v.has(id))
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
   * Prévient que l'action attend le PC : GoupixDex doit y être ouvert pour l'exécuter.
   * @param {string} actionLabel - Action concernée (« La mise en ligne groupée Vinted »…).
   * @returns {void}
   */
  function notifyPcUnreachable(actionLabel: string): void {
    toast.add({
      title: 'Ouvrez GoupixDex sur votre PC',
      description: `${actionLabel} s’exécute sur votre PC : lancez GoupixDex sur votre ordinateur, puis réessayez.`,
      color: 'warning',
    })
  }

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
   *
   */
  function triggerDesktopVintedUnlistIfNeeded(article: Article) {
    if (!import.meta.client || !canUseDesktopWorkers.value) {
      return
    }
    if (!article.pending_vinted_unlist) {
      return
    }
    void vintedUnlistAfterEbaySale(article.id)
      .then(() => {
        toast.add({
          title: 'Vinted',
          description: 'Suppression de l’annonce lancée sur votre PC (quelques secondes).',
          color: 'neutral',
        })
        setTimeout(() => void refresh(), 7000)
      })
      .catch((e) => {
        toast.add({ title: 'Suppression Vinted', description: apiErrorMessage(e), color: 'error' })
      })
  }

  /**
   * @param payload - Vente unitaire ou lot avec répartition calculée côté modale.
   */
  async function confirmSold(
    payload:
      | { mode: 'single'; soldPrice: number; saleSource: 'vinted' | 'ebay' }
      | {
          mode: 'bundle'
          saleSource: 'vinted' | 'ebay'
          allocations: { id: number; soldPrice: number }[]
        },
  ) {
    const rows = soldArticles.value
    if (!rows?.length) {
      return
    }
    soldSubmitting.value = true
    try {
      if (payload.mode === 'single') {
        const id = rows[0]?.id
        if (id == null) {
          return
        }
        const updated = await markSold(id, {
          sold_price: payload.soldPrice,
          sale_source: payload.saleSource,
        })
        triggerDesktopVintedUnlistIfNeeded(updated)
        toast.add({ title: 'Article marqué comme vendu', color: 'success' })
        if (payload.saleSource === 'ebay' && rows[0]?.published_on_vinted && !canUseDesktopWorkers.value) {
          toast.add({
            title: 'Vinted',
            description:
              'Pour retirer l’annonce encore en ligne sur Vinted, ouvrez GoupixDex sur votre PC puis « Réessayer suppression Vinted » dans le menu ⋯.',
            color: 'warning',
          })
        }
      } else {
        for (const a of payload.allocations) {
          const updated = await markSold(a.id, {
            sold_price: a.soldPrice,
            sale_source: payload.saleSource,
          })
          triggerDesktopVintedUnlistIfNeeded(updated)
        }
        toast.add({
          title:
            payload.allocations.length > 1
              ? `${payload.allocations.length} articles marqués comme vendus`
              : 'Article marqué comme vendu',
          color: 'success',
        })
        if (payload.saleSource === 'ebay' && rows.some((r) => r.published_on_vinted) && !canUseDesktopWorkers.value) {
          toast.add({
            title: 'Vinted',
            description:
              'Pour retirer les annonces Vinted restantes, ouvrez GoupixDex sur votre PC puis « Réessayer suppression Vinted » dans le menu ⋯.',
            color: 'warning',
          })
        }
      }
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
   * Lance la publication groupée selon les canaux cochés dans la modale.
   */
  async function confirmBulkPublish(payload: {
    vinted: boolean
    ebay: boolean
    leboncoin: boolean
    refreshVinted?: boolean
  }) {
    const ids = bulkPublishIds.value
    if (!ids.length) {
      return
    }
    bulkPublishOpen.value = false
    if (payload.leboncoin && !payload.vinted && !payload.ebay) {
      await onBulkPublishLeboncoin(ids)
      return
    }
    if (payload.vinted && payload.ebay) {
      await onBulkPublishBoth(ids)
      return
    }
    if (payload.vinted) {
      await onBulkPublishVinted(ids)
      return
    }
    if (payload.ebay) {
      await onBulkPublishEbay(ids)
    }
    if (payload.leboncoin) {
      toast.add({
        title: 'Leboncoin + autre canal',
        description: 'Lancez d’abord Vinted/eBay, puis republiez sur Leboncoin article par article.',
        color: 'warning',
      })
    }
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
      const ebayLeboncoinArticles: Article[] = selectedArticles.filter(
        (row: Article) => (payload.ebay && row.published_on_ebay) || (payload.leboncoin && row.published_on_leboncoin),
      )
      if (vintedDelistIds.length && canUseDesktopWorkers.value) {
        const { job_id } = await startVintedBatchDelist(vintedDelistIds)
        if (ebayLeboncoinArticles.length) {
          // Pas d'attente : le journal suit ce retrait pendant le lot Vinted.
          removeEbayLeboncoinListings(ebayLeboncoinArticles, payload, job_id)
        }
        articleListSelectionReset.value += 1
        await navigateTo({ path: '/articles/listing-logs', query: { job: job_id, after: 'delist', back: route.path } })
        return
      }

      if (vintedDelistIds.length) {
        notifyPcUnreachable('Le retrait Vinted')
      }
      if (ebayLeboncoinArticles.length) {
        announceEbayLeboncoinDelist(await removeEbayLeboncoinListings(ebayLeboncoinArticles, payload, null))
      } else if (!vintedDelistIds.length) {
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
   *
   */
  async function onBulkPublishVinted(ids: number[]) {
    const eligible = eligibleIdsForVintedBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description: 'Choisissez des articles non vendus avec au moins une photo.',
        color: 'warning',
      })
      return
    }
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La mise en ligne groupée Vinted')
      return
    }
    if (eligible.length < ids.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles non vendus avec photos sont inclus dans le lot.',
        color: 'warning',
      })
    }
    bulkPublishBusy.value = true
    try {
      const { job_id, stream_path } = await startVintedBatch(eligible)
      if (job_id && stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { job: job_id },
        })
        return
      }
      toast.add({ title: 'Lot Vinted', description: 'Réponse inattendue (pas de job).', color: 'warning' })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Impossible de lancer le lot Vinted',
        description: apiErrorMessage(e),
        color: 'error',
      })
    } finally {
      bulkPublishBusy.value = false
    }
  }

  /**
   *
   * @param ids
   */
  async function onBulkPublishEbay(ids: number[]) {
    const eligible = eligibleIdsForEbayBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description: 'Choisissez des articles non vendus, pas déjà sur eBay, avec au moins une image en HTTPS.',
        color: 'warning',
      })
      return
    }
    if (eligible.length < ids.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles éligibles pour eBay (image HTTPS, pas déjà publié) sont inclus.',
        color: 'warning',
      })
    }
    bulkPublishBusy.value = true
    try {
      const { queued } = await startEbayBatch(eligible)
      toast.add({
        title: 'Mise en ligne eBay',
        description: `${queued} publication(s) mise(s) en file d’attente (traitement séquentiel).`,
        color: 'success',
      })
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(eligible[0]) },
      })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Impossible de lancer le lot eBay',
        description: apiErrorMessage(e),
        color: 'error',
      })
    } finally {
      bulkPublishBusy.value = false
    }
  }

  /**
   *
   * @param ids
   */
  async function onBulkPublishBoth(ids: number[]) {
    const eligible = eligibleIdsForDualBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description:
          'Pour les deux canaux : articles non vendus, avec photos (Vinted) et au moins une image HTTPS pour eBay, sans annonce eBay déjà créée.',
        color: 'warning',
      })
      return
    }
    if (!canUseDesktopWorkers.value) {
      toast.add({
        title: 'Ouvrez GoupixDex sur votre PC',
        description:
          'Vinted s’exécute sur votre PC : lancez GoupixDex sur votre ordinateur, ou publiez seulement sur eBay.',
        color: 'warning',
      })
      return
    }
    if (eligible.length < ids.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles éligibles pour eBay et Vinted sont inclus.',
        color: 'warning',
      })
    }
    bulkPublishBusy.value = true
    try {
      const [vintedR, ebayR] = await Promise.allSettled([startVintedBatch(eligible), startEbayBatch(eligible)])

      if (vintedR.status === 'fulfilled' && vintedR.value.job_id) {
        if (ebayR.status === 'fulfilled') {
          toast.add({
            title: 'Lots lancés',
            description: `Vinted : suivi du lot. eBay : ${ebayR.value.queued} article(s) en file (API).`,
            color: 'success',
          })
        } else {
          toast.add({
            title: 'Lot Vinted lancé',
            description: `eBay : ${apiErrorMessage(ebayR.reason)}`,
            color: 'warning',
          })
        }
        await navigateTo({
          path: '/articles/listing-logs',
          query: { job: vintedR.value.job_id },
        })
        await refresh()
        return
      }

      if (ebayR.status === 'fulfilled') {
        toast.add({
          title: 'Lot eBay lancé',
          description:
            vintedR.status === 'rejected'
              ? `Vinted : ${apiErrorMessage(vintedR.reason)}`
              : `${ebayR.value.queued} article(s) en file.`,
          color: vintedR.status === 'rejected' ? 'warning' : 'success',
        })
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(eligible[0]) },
        })
        await refresh()
        return
      }

      const parts: string[] = []
      if (vintedR.status === 'rejected') {
        parts.push(`Vinted : ${apiErrorMessage(vintedR.reason)}`)
      }
      if (ebayR.status === 'rejected') {
        parts.push(`eBay : ${apiErrorMessage(ebayR.reason)}`)
      }
      toast.add({
        title: 'Impossible de lancer les lots',
        description: parts.length ? parts.join(' · ') : 'Erreur inconnue',
        color: 'error',
      })
    } finally {
      bulkPublishBusy.value = false
    }
  }

  /**
   *
   * @param a
   */
  async function onBulkPublishLeboncoin(ids: number[]) {
    if (!(await ensureLeboncoinPublishReady())) {
      return
    }
    const eligible = eligibleIdsForVintedBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description: 'Articles non vendus avec au moins une photo requis.',
        color: 'warning',
      })
      return
    }
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La publication Leboncoin')
      return
    }
    bulkPublishBusy.value = true
    try {
      const first = eligible[0]!
      const { leboncoin } = await publishArticleToLeboncoin(first)
      if (leboncoin?.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(first), progress: 'local', worker: 'leboncoin' },
        })
        if (eligible.length > 1) {
          toast.add({
            title: 'Publication Leboncoin',
            description: `${eligible.length} article(s) sélectionné(s) — traitez-les un par un pour l’instant.`,
            color: 'neutral',
          })
        }
        return
      }
      toast.add({ title: 'Leboncoin', description: 'Réponse inattendue du worker.', color: 'warning' })
    } catch (e) {
      toast.add({
        title: 'Publication Leboncoin impossible',
        description: apiErrorMessage(e),
        color: 'error',
      })
    } finally {
      bulkPublishBusy.value = false
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
    onBulkPublishVinted,
    onBulkPublishEbay,
    onBulkPublishBoth,
    onPublishVinted,
    onPublishLeboncoin,
    onBulkPublishLeboncoin,
    onRetryCrossEbay,
    onRetryCrossVinted,
  }
}
