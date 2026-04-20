<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Articles',
  "Liste de vos annonces et cartes Pokémon TCG dans GoupixDex : recherche, édition, vente et mise en ligne Vinted depuis l'app desktop."
)

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
/** Show “Publish on eBay” when the channel is enabled and the account is ready in settings. */
const ebayPublishAvailable = ref(false)
/** Vinted activé dans les réglages marché (l’API refuse sinon). */
const vintedChannelEnabled = ref(false)

const articles = ref<Article[]>([])
const pricingById = ref<Map<number, PricingLookup>>(new Map())
const loading = ref(true)
const pricingLoading = ref(false)
/** When false (default), no PokéWallet / Cardmarket calls for the list. */
const fetchMarketData = ref(false)

const soldOpen = ref(false)
const soldArticle = ref<Article | null>(null)
const soldSubmitting = ref(false)

const deleteOpen = ref(false)
const deleteId = ref<number | null>(null)

const bulkDeleteOpen = ref(false)
const bulkDeleteIds = ref<number[]>([])
const bulkPublishBusy = ref(false)

function articleById(id: number): Article | undefined {
  return articles.value.find(a => a.id === id)
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
    articles.value = await listArticles()
    if (fetchMarketData.value) {
      pricingLoading.value = true
      pricingById.value = await lookupMany(articles.value, 4)
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
  await Promise.all([refresh(), loadMarketplaceAvailability()])
})

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
</script>

<template>
  <UDashboardPanel id="articles">
    <template #header>
      <UDashboardNavbar title="Articles">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              to="/articles/batch-create"
              color="neutral"
              variant="subtle"
              icon="i-lucide-layers"
            >
              Création groupée
            </UButton>
            <UButton to="/articles/create" icon="i-lucide-plus">
              Nouvel article
            </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-4 sm:space-y-6">

        <!-- Options de liste -->
        <UCard class="ring-1 ring-default/60 shadow-sm" :ui="{ body: 'p-4 sm:p-5' }">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-3">
              <USwitch v-model="fetchMarketData" />
              <div class="space-y-0.5">
                <p class="text-sm text-highlighted">
                  Afficher les prix marché
                </p>
                <p class="text-xs text-muted">
                  Récupération des prix Cardmarket / PokéWallet pour chaque carte (plus lent mais plus précis).
                </p>
              </div>
            </div>
            <p class="text-xs text-muted max-w-sm">
              Désactivez cette option si vous voulez simplement mettre à jour vos fiches sans attendre les prix externes.
            </p>
          </div>
        </UCard>

        <UCard
          v-if="!loading && articles.length === 0"
          class="ring-1 ring-primary/25 shadow-sm border-primary/20"
          :ui="{ body: 'p-5 sm:p-6 space-y-4' }"
        >
          <div class="space-y-2">
            <p class="text-sm font-medium text-highlighted">
              Aucun article pour l'instant
            </p>
            <p class="text-sm text-muted leading-relaxed">
              Si vous vendez déjà sur Vinted, vous pouvez importer vos annonces actives et vendues dans GoupixDex.
              Une fenêtre Chrome s'ouvre pour vous connecter ; le catalogue est ensuite récupéré automatiquement.
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <UButton
              icon="i-lucide-cloud-download"
              :loading="wardrobeSyncing"
              :disabled="!isDesktopApp"
              @click="onWardrobeImportFromVinted"
            >
              Importer depuis Vinted
            </UButton>
            <UButton to="/articles/create" color="neutral" variant="subtle" icon="i-lucide-plus">
              Créer un article manuellement
            </UButton>
          </div>
          <p v-if="!isDesktopApp" class="text-xs text-muted">
            L'import Vinted n'est disponible que dans
            <NuxtLink to="/downloads" class="underline underline-offset-2">l'application desktop</NuxtLink>
            (worker local sur ce poste).
          </p>
        </UCard>

        <!-- Table / cartes des articles -->
        <UCard class="ring-1 ring-default/60 shadow-sm" :ui="{ body: 'p-0 sm:p-0' }">
          <div class="p-3 sm:p-4">
            <ArticleList
              :articles="articles"
              :pricing-by-id="pricingById"
              :loading="loading"
              :pricing-loading="pricingLoading"
              :show-ebay-column="ebayPublishAvailable"
              :ebay-publish-available="ebayPublishAvailable"
              :vinted-channel-enabled="vintedChannelEnabled"
              :bulk-publishing="bulkPublishBusy"
              @edit="(id: number) => navigateTo(`/articles/${id}`)"
              @delete="(id: number) => { deleteId = id; deleteOpen = true }"
              @sold="openSold"
              @publish-vinted="onPublishVinted"
              @publish-ebay="onPublishEbay"
              @bulk-delete="openBulkDelete"
              @bulk-publish-vinted="onBulkPublishVinted"
              @bulk-publish-ebay="onBulkPublishEbay"
              @bulk-publish-both="onBulkPublishBoth"
            />
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>

  <ArticleMarkSoldModal
    v-model:open="soldOpen"
    :article="soldArticle"
    :ebay-enabled="ebayPublishAvailable"
    :loading="soldSubmitting"
    @confirm="confirmSold"
  />

  <UModal
    v-model:open="bulkDeleteOpen"
    title="Supprimer plusieurs articles ?"
    :description="`Vous allez supprimer ${bulkDeleteIds.length} article(s). Cette action est irréversible.`"
  >
    <template #body>
      <div class="flex justify-end gap-2">
        <UButton color="neutral" variant="subtle" @click="bulkDeleteOpen = false">
          Annuler
        </UButton>
        <UButton color="error" @click="confirmBulkDelete">
          Supprimer {{ bulkDeleteIds.length }} article(s)
        </UButton>
      </div>
    </template>
  </UModal>

  <UModal
    v-model:open="deleteOpen"
    title="Supprimer cet article ?"
    description="Cette action est irréversible."
  >
    <template #body>
      <div class="flex justify-end gap-2">
        <UButton color="neutral" variant="subtle" @click="deleteOpen = false">
          Annuler
        </UButton>
        <UButton color="error" @click="confirmDelete">
          Supprimer
        </UButton>
      </div>
    </template>
  </UModal>

</template>
