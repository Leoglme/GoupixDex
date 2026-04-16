<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Articles',
  "Liste de vos annonces et cartes Pokémon TCG dans GoupixDex : recherche, édition, vente et mise en ligne Vinted depuis l'app desktop."
)

const { listArticles, deleteArticle, deleteArticlesBulk, markSold, publishArticleToVinted } = useArticles()
const { lookupMany } = usePricing()
const toast = useToast()
const { isDesktopApp } = useDesktopRuntime()

const articles = ref<Article[]>([])
const pricingById = ref<Map<number, PricingLookup>>(new Map())
const loading = ref(true)
const pricingLoading = ref(false)
/** Si faux (défaut), aucun appel PokéWallet / Cardmarket sur la liste. */
const fetchMarketData = ref(false)

const soldOpen = ref(false)
const soldArticle = ref<Article | null>(null)
const sellPriceInput = ref('')

const deleteOpen = ref(false)
const deleteId = ref<number | null>(null)

const bulkDeleteOpen = ref(false)
const bulkDeleteIds = ref<number[]>([])

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

onMounted(refresh)

watch(fetchMarketData, () => {
  refresh()
})

function openSold(a: Article) {
  soldArticle.value = a
  sellPriceInput.value = a.sell_price != null ? String(a.sell_price) : ''
  soldOpen.value = true
}

async function confirmSold() {
  if (!soldArticle.value) {
    return
  }
  const p = Number(sellPriceInput.value.replace(',', '.'))
  if (Number.isNaN(p) || p < 0) {
    toast.add({ title: 'Prix de vente invalide', color: 'error' })
    return
  }
  try {
    await markSold(soldArticle.value.id, p)
    toast.add({ title: 'Article marqué comme vendu', color: 'success' })
    soldOpen.value = false
    await refresh()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
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
        path: '/articles/vinted-logs',
        query: { article: String(a.id) }
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

        <!-- Table / cartes des articles -->
        <UCard class="ring-1 ring-default/60 shadow-sm" :ui="{ body: 'p-0 sm:p-0' }">
          <div class="p-3 sm:p-4">
            <ArticleList
              :articles="articles"
              :pricing-by-id="pricingById"
              :loading="loading"
              :pricing-loading="pricingLoading"
              @edit="(id: number) => navigateTo(`/articles/${id}`)"
              @delete="(id: number) => { deleteId = id; deleteOpen = true }"
              @sold="openSold"
              @publish-vinted="onPublishVinted"
              @bulk-delete="openBulkDelete"
            />
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>

  <UModal
    v-model:open="soldOpen"
    title="Marquer comme vendu"
    description="Indiquez le prix de vente final (€)."
  >
    <template #body>
      <UInput
        v-model="sellPriceInput"
        type="text"
        inputmode="decimal"
        class="w-full"
      />
      <div class="flex justify-end gap-2 mt-4">
        <UButton color="neutral" variant="subtle" @click="soldOpen = false">
          Annuler
        </UButton>
        <UButton @click="confirmSold">
          Valider
        </UButton>
      </div>
    </template>
  </UModal>

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
