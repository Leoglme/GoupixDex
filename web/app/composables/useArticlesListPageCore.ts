import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
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
    publishArticleToVinted,
    publishArticleToEbay,
    publishArticleToLeboncoin,
    startVintedBatch,
    startVintedBatchDelist,
    startEbayBatch,
    bulkDelistChannels,
    bulkPrepareForSale,
  } = useArticles()
  const { getSettings } = useSettings()
  const toast = useToast()
  const { isDesktopApp } = useDesktopRuntime()
  const { startJob } = useWardrobeLocalSync()

  const wardrobeSyncing: Ref<boolean> = ref(false)
  const ebayPublishAvailable: Ref<boolean> = ref(false)
  const vintedChannelEnabled: Ref<boolean> = ref(false)
  const leboncoinPublishAvailable: Ref<boolean> = ref(false)

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

  /**
   *
   */
  async function loadMarketplaceAvailability() {
    try {
      const s = await getSettings()
      vintedChannelEnabled.value = s.vinted_enabled === true
      ebayPublishAvailable.value =
        s.ebay_enabled === true &&
        s.ebay_oauth_configured === true &&
        s.ebay_connected === true &&
        s.ebay_listing_config_complete === true
      leboncoinPublishAvailable.value = s.leboncoin_enabled === true && s.sender_address_complete === true
    } catch {
      vintedChannelEnabled.value = false
      ebayPublishAvailable.value = false
      leboncoinPublishAvailable.value = false
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
   *
   */
  function triggerDesktopVintedUnlistIfNeeded(article: Article) {
    if (!import.meta.client || !isDesktopApp.value) {
      return
    }
    if (!article.pending_vinted_unlist) {
      return
    }
    void vintedUnlistAfterEbaySale(article.id)
      .then(() => {
        toast.add({
          title: 'Vinted',
          description: 'Suppression de l’annonce lancée sur ce poste (quelques secondes).',
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
        if (payload.saleSource === 'ebay' && rows[0]?.published_on_vinted && !isDesktopApp.value) {
          toast.add({
            title: 'Vinted',
            description:
              'Pour retirer l’annonce encore en ligne sur Vinted, ouvrez l’application desktop puis « Réessayer suppression Vinted » dans le menu ⋯.',
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
        if (payload.saleSource === 'ebay' && rows.some((r) => r.published_on_vinted) && !isDesktopApp.value) {
          toast.add({
            title: 'Vinted',
            description:
              'Pour retirer les annonces Vinted restantes, ouvrez l’application desktop puis « Réessayer suppression Vinted » dans le menu ⋯.',
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
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop',
        description: 'La suppression Vinted s’exécute sur le worker local (app GoupixDex).',
        color: 'warning',
      })
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

  /** @returns true si l’adresse expéditeur permet une publication Leboncoin. */
  async function ensureLeboncoinPublishReady(): Promise<boolean> {
    try {
      const settings = await getSettings()
      if (settings.sender_address_complete) {
        return true
      }
    } catch {
      /* fall through */
    }
    toast.add({
      title: 'Adresse expéditeur requise',
      description: 'Complétez votre adresse dans Mon profil (menu compte) avant de publier sur Leboncoin.',
      color: 'warning',
    })
    const { openProfileDrawer } = useProfileDrawer()
    openProfileDrawer()
    return false
  }

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
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description:
          "La synchronisation Vinted utilise le worker local (Chrome). Installez l'app pour Windows ou macOS.",
        color: 'warning',
      })
      await navigateTo('/downloads')
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
   *
   * @param a
   */
  async function onPublishEbay(a: Article) {
    try {
      const { ebay } = await publishArticleToEbay(a.id)
      if (ebay?.status === 'running' && ebay?.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(a.id) },
        })
        return
      }
      toast.add({
        title: 'Mise en ligne sur eBay',
        description: 'La publication est lancée. La liste se mettra à jour dans quelques instants.',
        color: 'success',
      })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Impossible de publier sur eBay',
        description: apiErrorMessage(e),
        color: 'error',
      })
    }
  }

  /**
   *
   * @param ids
   */
  async function confirmBulkDelist(payload: { vinted: boolean; ebay: boolean; leboncoin: boolean }) {
    const ids = bulkDelistIds.value
    if (!ids.length) {
      return
    }
    bulkDelistOpen.value = false
    bulkDelistBusy.value = true
    try {
      const res = await bulkDelistChannels({
        article_ids: ids,
        vinted: payload.vinted,
        ebay: payload.ebay,
        leboncoin: payload.leboncoin,
      })
      const parts: string[] = []
      if (res.ebay_removed) {
        parts.push(`${res.ebay_removed} retrait(s) eBay`)
      }
      if (res.leboncoin_cleared) {
        parts.push(`${res.leboncoin_cleared} retrait(s) Leboncoin`)
      }
      if (payload.vinted && res.vinted_article_ids.length) {
        if (!isDesktopApp.value) {
          toast.add({
            title: 'Application desktop requise',
            description: 'Le retrait Vinted s’exécute sur votre machine.',
            color: 'warning',
          })
          await navigateTo('/downloads')
        } else {
          const { job_id } = await startVintedBatchDelist(res.vinted_article_ids)
          if (job_id) {
            await navigateTo({ path: '/articles/listing-logs', query: { job: job_id } })
            return
          }
        }
      }
      if (parts.length) {
        toast.add({ title: 'Retrait enregistré', description: parts.join(' · '), color: 'success' })
      } else if (!payload.vinted || !res.vinted_article_ids.length) {
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
        if (!isDesktopApp.value) {
          toast.add({
            title: 'Application desktop requise',
            description: 'Le retrait Vinted avant republication s’exécute sur votre machine.',
            color: 'warning',
          })
          await navigateTo('/downloads')
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
        description:
          'Choisissez des articles non vendus avec au moins une photo, et utilisez l’application desktop pour Vinted.',
        color: 'warning',
      })
      return
    }
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description: 'La mise en ligne groupée Vinted s’exécute sur votre machine.',
        color: 'warning',
      })
      await navigateTo('/downloads')
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
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description: 'Vinted nécessite l’application desktop ; eBay peut être lancé seul depuis la liste.',
        color: 'warning',
      })
      await navigateTo('/downloads')
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
        description: 'Articles non vendus avec au moins une photo requis (app desktop).',
        color: 'warning',
      })
      return
    }
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description: 'Leboncoin s’exécute sur votre machine via Chrome.',
        color: 'warning',
      })
      await navigateTo('/downloads')
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
   *
   */
  async function onPublishLeboncoin(a: Article) {
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description: 'La mise en ligne Leboncoin utilise Chrome sur ce poste.',
        color: 'warning',
      })
      await navigateTo('/downloads')
      return
    }
    if (!(await ensureLeboncoinPublishReady())) {
      return
    }
    try {
      const { leboncoin } = await publishArticleToLeboncoin(a.id)
      if (leboncoin?.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(a.id), progress: 'local', worker: 'leboncoin' },
        })
        return
      }
      toast.add({
        title: 'Publication Leboncoin',
        description: 'Réponse inattendue du worker local.',
        color: 'warning',
      })
    } catch (e) {
      toast.add({
        title: 'Publication Leboncoin impossible',
        description: apiErrorMessage(e),
        color: 'error',
      })
    }
  }

  /**
   *
   */
  async function onPublishVinted(a: Article) {
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Version web',
        description: "La mise en ligne Vinted est disponible uniquement dans l'application desktop.",
        color: 'warning',
      })
      await navigateTo('/downloads')
      return
    }
    try {
      const { vinted } = await publishArticleToVinted(a.id)
      if (vinted.status === 'running' && vinted.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(a.id), progress: 'local' },
        })
        return
      }
      toast.add({
        title: 'Publication Vinted',
        description: 'Réponse inattendue du serveur (pas de flux SSE).',
        color: 'warning',
      })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Publication Vinted impossible',
        description: apiErrorMessage(e),
        color: 'error',
      })
    }
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
