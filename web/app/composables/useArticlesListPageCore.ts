import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'
import { loadArticleListPrefs, saveArticleListPrefs } from '~/composables/useUiPrefsLocalStorage'

export type ArticlesListPageVariant = 'listed' | 'stock'

function isOnMarketplace(a: Article) {
  return Boolean(a.published_on_vinted ?? false) || Boolean(a.published_on_ebay ?? false)
}

/**
 * État partagé entre « Articles » (déjà en vente) et « Mon stock » (inventaire à publier).
 */
export function useArticlesListPageCore(variant: ArticlesListPageVariant) {
  const {
    listArticles,
    deleteArticle,
    deleteArticlesBulk,
    markSold,
    publishArticleToVinted,
    publishArticleToEbay,
    startVintedBatch,
    startEbayBatch
  } = useArticles()
  const { getSettings } = useSettings()
  const { lookupMany } = usePricing()
  const toast = useToast()
  const { isDesktopApp } = useDesktopRuntime()
  const { startJob } = useWardrobeLocalSync()

  const wardrobeSyncing = ref(false)
  const ebayPublishAvailable = ref(false)
  const vintedChannelEnabled = ref(false)

  const allArticles = ref<Article[]>([])
  const pricingById = ref<Map<number, PricingLookup>>(new Map())
  const loading = ref(true)
  const pricingLoading = ref(false)
  const fetchMarketData = ref(false)

  /** Mon stock : inclure les annonces déjà en ligne (persisté, coché par défaut). */
  const stockIncludeListed = variant === 'stock' ? ref(true) : ref(false)

  const soldOpen = ref(false)
  const soldArticle = ref<Article | null>(null)
  const soldSubmitting = ref(false)

  const deleteOpen = ref(false)
  const deleteId = ref<number | null>(null)

  const bulkDeleteOpen = ref(false)
  const bulkDeleteIds = ref<number[]>([])
  const bulkPublishBusy = ref(false)

  const displayedArticles = computed(() => {
    const rows = allArticles.value
    if (variant === 'listed') {
      return rows.filter(isOnMarketplace)
    }
    if (stockIncludeListed.value) {
      return rows
    }
    return rows.filter(a => !isOnMarketplace(a))
  })

  const hasAnyArticles = computed(() => allArticles.value.length > 0)

  const stockAllListed = computed(
    () =>
      variant === 'stock'
      && hasAnyArticles.value
      && !stockIncludeListed.value
      && displayedArticles.value.length === 0
  )

  function articleById(id: number): Article | undefined {
    return allArticles.value.find(a => a.id === id)
  }

  function hasHttpsImage(a: Article) {
    return a.images?.some(img => (img.image_url || '').startsWith('https://')) ?? false
  }

  function eligibleIdsForVintedBulk(ids: number[]) {
    return ids.filter((id) => {
      const a = articleById(id)
      return a && !a.is_sold && (a.images?.length ?? 0) > 0
    })
  }

  function eligibleIdsForEbayBulk(ids: number[]) {
    return ids.filter((id) => {
      const a = articleById(id)
      return a && !a.is_sold && !(a.published_on_ebay ?? false) && hasHttpsImage(a)
    })
  }

  function eligibleIdsForDualBulk(ids: number[]) {
    const v = new Set(eligibleIdsForVintedBulk(ids))
    return eligibleIdsForEbayBulk(ids).filter(id => v.has(id))
  }

  async function refresh() {
    loading.value = true
    try {
      allArticles.value = await listArticles()
      if (fetchMarketData.value) {
        pricingLoading.value = true
        pricingById.value = await lookupMany(allArticles.value, 4)
      } else {
        pricingById.value = new Map()
      }
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    } finally {
      loading.value = false
      pricingLoading.value = false
    }
  }

  async function loadMarketplaceAvailability() {
    try {
      const s = await getSettings()
      vintedChannelEnabled.value = s.vinted_enabled === true
      ebayPublishAvailable.value =
        s.ebay_enabled === true
        && s.ebay_oauth_configured === true
        && s.ebay_connected === true
        && s.ebay_listing_config_complete === true
    } catch {
      vintedChannelEnabled.value = false
      ebayPublishAvailable.value = false
    }
  }

  onMounted(async () => {
    if (variant === 'stock' && import.meta.client) {
      const s = loadArticleListPrefs()
      if (typeof s?.stockIncludeListed === 'boolean') {
        stockIncludeListed.value = s.stockIncludeListed
      }
    }
    await Promise.all([refresh(), loadMarketplaceAvailability()])
  })

  if (variant === 'stock') {
    watch(stockIncludeListed, (v) => {
      saveArticleListPrefs({ stockIncludeListed: v })
    })
  }

  watch(fetchMarketData, () => {
    refresh()
  })

  function openSold(a: Article) {
    soldArticle.value = a
    soldOpen.value = true
  }

  async function confirmSold(payload: { soldPrice: number, saleSource: 'vinted' | 'ebay' }) {
    if (!soldArticle.value) {
      return
    }
    soldSubmitting.value = true
    try {
      await markSold(soldArticle.value.id, {
        sold_price: payload.soldPrice,
        sale_source: payload.saleSource
      })
      toast.add({ title: 'Article marqué comme vendu', color: 'success' })
      soldOpen.value = false
      await refresh()
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    } finally {
      soldSubmitting.value = false
    }
  }

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

  function openBulkDelete(ids: number[]) {
    bulkDeleteIds.value = ids
    bulkDeleteOpen.value = true
  }

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
        color: 'success'
      })
      bulkDeleteOpen.value = false
      bulkDeleteIds.value = []
      await refresh()
    } catch (e) {
      toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
    }
  }

  async function onWardrobeImportFromVinted() {
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description:
          "La synchronisation Vinted utilise le worker local (Chrome). Installez l'app pour Windows ou macOS.",
        color: 'warning'
      })
      await navigateTo('/downloads')
      return
    }
    wardrobeSyncing.value = true
    try {
      const jobId = await startJob()
      await navigateTo({
        path: '/articles/listing-logs',
        query: { wardrobe_job: jobId }
      })
    } catch (e) {
      toast.add({
        title: 'Synchronisation Vinted',
        description: apiErrorMessage(e),
        color: 'error'
      })
    } finally {
      wardrobeSyncing.value = false
    }
  }

  async function onPublishEbay(a: Article) {
    try {
      const { ebay } = await publishArticleToEbay(a.id)
      if (ebay?.status === 'running' && ebay?.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(a.id) }
        })
        return
      }
      toast.add({
        title: 'Mise en ligne sur eBay',
        description: 'La publication est lancée. La liste se mettra à jour dans quelques instants.',
        color: 'success'
      })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Impossible de publier sur eBay',
        description: apiErrorMessage(e),
        color: 'error'
      })
    }
  }

  async function onBulkPublishVinted(ids: number[]) {
    const eligible = eligibleIdsForVintedBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description:
          'Choisissez des articles non vendus avec au moins une photo, et utilisez l’application desktop pour Vinted.',
        color: 'warning'
      })
      return
    }
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description: 'La mise en ligne groupée Vinted s’exécute sur votre machine.',
        color: 'warning'
      })
      await navigateTo('/downloads')
      return
    }
    if (eligible.length < ids.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles non vendus avec photos sont inclus dans le lot.',
        color: 'warning'
      })
    }
    bulkPublishBusy.value = true
    try {
      const { job_id, stream_path } = await startVintedBatch(eligible)
      if (job_id && stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { job: job_id }
        })
        return
      }
      toast.add({ title: 'Lot Vinted', description: 'Réponse inattendue (pas de job).', color: 'warning' })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Impossible de lancer le lot Vinted',
        description: apiErrorMessage(e),
        color: 'error'
      })
    } finally {
      bulkPublishBusy.value = false
    }
  }

  async function onBulkPublishEbay(ids: number[]) {
    const eligible = eligibleIdsForEbayBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description:
          'Choisissez des articles non vendus, pas déjà sur eBay, avec au moins une image en HTTPS.',
        color: 'warning'
      })
      return
    }
    if (eligible.length < ids.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles éligibles pour eBay (image HTTPS, pas déjà publié) sont inclus.',
        color: 'warning'
      })
    }
    bulkPublishBusy.value = true
    try {
      const { queued } = await startEbayBatch(eligible)
      toast.add({
        title: 'Mise en ligne eBay',
        description: `${queued} publication(s) mise(s) en file d’attente (traitement séquentiel).`,
        color: 'success'
      })
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(eligible[0]) }
      })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Impossible de lancer le lot eBay',
        description: apiErrorMessage(e),
        color: 'error'
      })
    } finally {
      bulkPublishBusy.value = false
    }
  }

  async function onBulkPublishBoth(ids: number[]) {
    const eligible = eligibleIdsForDualBulk(ids)
    if (!eligible.length) {
      toast.add({
        title: 'Sélection invalide',
        description:
          'Pour les deux canaux : articles non vendus, avec photos (Vinted) et au moins une image HTTPS pour eBay, sans annonce eBay déjà créée.',
        color: 'warning'
      })
      return
    }
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Application desktop requise',
        description: 'Vinted nécessite l’application desktop ; eBay peut être lancé seul depuis la liste.',
        color: 'warning'
      })
      await navigateTo('/downloads')
      return
    }
    if (eligible.length < ids.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles éligibles pour eBay et Vinted sont inclus.',
        color: 'warning'
      })
    }
    bulkPublishBusy.value = true
    try {
      const [vintedR, ebayR] = await Promise.allSettled([
        startVintedBatch(eligible),
        startEbayBatch(eligible)
      ])

      if (vintedR.status === 'fulfilled' && vintedR.value.job_id) {
        if (ebayR.status === 'fulfilled') {
          toast.add({
            title: 'Lots lancés',
            description: `Vinted : suivi du lot. eBay : ${ebayR.value.queued} article(s) en file (API).`,
            color: 'success'
          })
        } else {
          toast.add({
            title: 'Lot Vinted lancé',
            description: `eBay : ${apiErrorMessage(ebayR.reason)}`,
            color: 'warning'
          })
        }
        await navigateTo({
          path: '/articles/listing-logs',
          query: { job: vintedR.value.job_id }
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
          color: vintedR.status === 'rejected' ? 'warning' : 'success'
        })
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(eligible[0]) }
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
        color: 'error'
      })
    } finally {
      bulkPublishBusy.value = false
    }
  }

  async function onPublishVinted(a: Article) {
    if (!isDesktopApp.value) {
      toast.add({
        title: 'Version web',
        description: "La mise en ligne Vinted est disponible uniquement dans l'application desktop.",
        color: 'warning'
      })
      await navigateTo('/downloads')
      return
    }
    try {
      const { vinted } = await publishArticleToVinted(a.id)
      if (vinted.status === 'running' && vinted.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(a.id), progress: 'local' }
        })
        return
      }
      toast.add({
        title: 'Publication Vinted',
        description: 'Réponse inattendue du serveur (pas de flux SSE).',
        color: 'warning'
      })
      await refresh()
    } catch (e) {
      toast.add({
        title: 'Publication Vinted impossible',
        description: apiErrorMessage(e),
        color: 'error'
      })
    }
  }

  return {
    variant,
    stockIncludeListed,
    allArticles,
    displayedArticles,
    hasAnyArticles,
    stockAllListed,
    pricingById,
    loading,
    pricingLoading,
    fetchMarketData,
    wardrobeSyncing,
    ebayPublishAvailable,
    vintedChannelEnabled,
    soldOpen,
    soldArticle,
    soldSubmitting,
    deleteOpen,
    deleteId,
    bulkDeleteOpen,
    bulkDeleteIds,
    bulkPublishBusy,
    refresh,
    openSold,
    confirmSold,
    confirmDelete,
    openBulkDelete,
    confirmBulkDelete,
    onWardrobeImportFromVinted,
    onPublishEbay,
    onBulkPublishVinted,
    onBulkPublishEbay,
    onBulkPublishBoth,
    onPublishVinted
  }
}
