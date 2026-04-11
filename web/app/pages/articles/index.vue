<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'

definePageMeta({ middleware: 'auth' })

const { listArticles, deleteArticle, markSold } = useArticles()
const { lookupMany } = usePricing()
const toast = useToast()

const articles = ref<Article[]>([])
const pricingById = ref<Map<number, PricingLookup>>(new Map())
const loading = ref(true)
const pricingLoading = ref(false)

const soldOpen = ref(false)
const soldArticle = ref<Article | null>(null)
const sellPriceInput = ref('')

const deleteOpen = ref(false)
const deleteId = ref<number | null>(null)

async function refresh() {
  loading.value = true
  try {
    articles.value = await listArticles()
    pricingLoading.value = true
    pricingById.value = await lookupMany(articles.value, 4)
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
    pricingLoading.value = false
  }
}

onMounted(refresh)

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
</script>

<template>
  <UDashboardPanel id="articles">
    <template #header>
      <UDashboardNavbar title="Articles">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/articles/create" icon="i-lucide-plus">
            Nouvel article
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="p-4 sm:p-6 space-y-4">
        <ArticleList
          :articles="articles"
          :pricing-by-id="pricingById"
          :loading="loading"
          :pricing-loading="pricingLoading"
          @edit="(id: number) => navigateTo(`/articles/${id}`)"
          @delete="(id: number) => { deleteId = id; deleteOpen = true }"
          @sold="openSold"
        />
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
