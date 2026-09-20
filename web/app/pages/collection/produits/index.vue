<template>
  <UDashboardPanel id="my-sealed-page">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-box" class="h-3 w-3 text-(--app-accent)" />
            Produits scellés
          </span>
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full">
        <GoupixDexPageHeader
          title="Produits scellés"
          description="ETB, UPC, coffrets, displays, tripacks… suivis à la valeur Cardmarket."
        >
          <template #actions>
            <UButton color="primary" variant="solid" icon="i-lucide-plus" size="md" to="/collection/produits/add">
              Ajouter un produit
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <GoupixDexCollectionSectionTabs active="produits" />

        <div class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
          <GoupixDexStatsCard
            title="Valeur estimée"
            :value="eur.format(stats.estimated_market_eur)"
            :description="`Prix marché Cardmarket · ${stats.priced_products} produit(s) coté(s)`"
            icon="i-lucide-euro"
          />
          <GoupixDexStatsCard
            title="Plus-value"
            :value="gainLabel"
            :description="gainDescription"
            icon="i-lucide-trending-up"
          />
          <GoupixDexStatsCard
            title="Produits"
            :value="stats.unique_products"
            description="Références distinctes"
            icon="i-lucide-box"
          />
          <GoupixDexStatsCard
            title="Exemplaires"
            :value="stats.total_quantity"
            description="Quantité totale possédée"
            icon="i-lucide-package"
          />
          <GoupixDexStatsCard
            title="En vente"
            :value="stats.with_article"
            description="Produits liés à un article"
            icon="i-lucide-tag"
          />
        </div>

        <UCard :ui="{ body: 'p-4 sm:p-5' }">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between lg:gap-4">
            <UFormField label="Recherche" class="min-w-0 flex-1">
              <UInput v-model="search" icon="i-lucide-search" placeholder="Nom, set…" class="w-full" />
            </UFormField>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:gap-3 lg:shrink-0">
              <UFormField label="Type" class="w-full sm:w-48">
                <USelect
                  v-model="typeFilter"
                  :items="typeFilterItems"
                  value-key="value"
                  label-key="label"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Langue" class="w-full sm:w-44">
                <USelect
                  v-model="languageFilter"
                  :items="languageItems"
                  value-key="value"
                  label-key="label"
                  class="w-full"
                />
              </UFormField>
            </div>
          </div>
        </UCard>

        <div class="flex w-full flex-wrap items-center justify-between gap-y-2">
          <GoupixDexCollectionViewTabs v-model="viewMode" :items="viewItems" />
          <span class="text-muted shrink-0 text-sm tabular-nums">
            {{ filteredItems.length }} produit(s) affiché(s)
          </span>
        </div>

        <div v-if="loading && !payload" class="flex items-center justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
        </div>

        <UCard v-else-if="!loading && filteredItems.length === 0" :ui="{ body: 'p-10 text-center space-y-4' }">
          <UIcon name="i-lucide-box" class="text-muted mx-auto size-14" />
          <div class="space-y-1">
            <p class="text-highlighted text-lg font-semibold">Aucun produit scellé</p>
            <p class="text-muted text-sm">Ajoutez un ETB, un coffret ou un display pour suivre sa valeur.</p>
          </div>
          <UButton color="primary" icon="i-lucide-plus" to="/collection/produits/add">
            Ajouter mon premier produit
          </UButton>
        </UCard>

        <div
          v-else-if="viewMode === 'grid'"
          class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
        >
          <button
            v-for="product in filteredItems"
            :key="product.id"
            type="button"
            class="border-default bg-elevated/30 group focus-visible:ring-primary block overflow-hidden rounded-xl border text-left transition-all hover:border-(--app-accent) hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
            @click="onProductClick(product.id, $event)"
            @keydown.enter.prevent="openSealed(product.id)"
          >
            <div class="bg-muted/20 relative aspect-[3/4] w-full overflow-hidden">
              <img
                v-if="product.image_url"
                :src="product.image_url"
                :alt="product.name"
                class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                referrerpolicy="no-referrer"
                decoding="async"
                loading="lazy"
              />
              <div v-else class="flex h-full items-center justify-center">
                <UIcon name="i-lucide-box" class="text-muted size-8" />
              </div>
              <span
                class="bg-primary/90 text-inverted absolute top-1.5 left-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase backdrop-blur-sm"
              >
                {{ sealedProductTypeLabel(product.product_type) }}
              </span>
              <span
                v-if="product.quantity > 1"
                class="bg-elevated/95 text-highlighted absolute top-1.5 right-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
              >
                ×{{ product.quantity }}
              </span>
              <span
                v-if="product.market_price_eur != null"
                class="bg-elevated/95 text-highlighted absolute bottom-1.5 left-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
              >
                {{ eur.format(product.market_price_eur) }}
              </span>
              <span
                v-if="product.gain_percent != null"
                class="absolute right-1.5 bottom-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
                :class="product.gain_percent >= 0 ? 'bg-success/90 text-inverted' : 'bg-error/90 text-inverted'"
              >
                {{ formatSignedPercent(product.gain_percent) }}
              </span>
            </div>
            <div class="p-2">
              <p class="text-highlighted truncate text-xs leading-snug font-medium">{{ product.name }}</p>
              <p class="text-muted truncate text-[10px]">{{ product.set_name || '—' }}</p>
            </div>
          </button>
        </div>

        <div v-else class="app-card overflow-hidden">
          <GoupixDexBaseTable min-width="720px">
            <template #head>
              <GoupixDexBaseTableTh class="goupix-card-table__name-col">Produit</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh>Type</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="right">Qté</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="right">Prix marché</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="right">Achat</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="right">Plus-value</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="center" sr-only>Ouvrir</GoupixDexBaseTableTh>
            </template>

            <GoupixDexBaseTableTr
              v-for="row in filteredItems"
              :key="row.id"
              class="cursor-pointer"
              @click="onProductClick(row.id, $event)"
            >
              <GoupixDexBaseTableTd class="goupix-card-table__lead">
                <div class="flex min-w-0 items-center gap-3">
                  <div class="size-11 shrink-0 overflow-hidden rounded-md bg-[var(--app-surface-2)]">
                    <img
                      v-if="row.image_url"
                      :src="row.image_url"
                      :alt="row.name"
                      class="h-full w-full object-cover"
                      referrerpolicy="no-referrer"
                      decoding="async"
                      loading="lazy"
                    />
                  </div>
                  <div class="min-w-0">
                    <p class="min-w-0 truncate text-sm font-medium text-[var(--app-ink)]">{{ row.name }}</p>
                    <p class="truncate text-xs text-[var(--app-ink-soft)]">{{ row.set_name || '—' }}</p>
                  </div>
                </div>
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd label="Type">
                <UBadge color="neutral" variant="subtle" size="sm">{{
                  sealedProductTypeLabel(row.product_type)
                }}</UBadge>
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd label="Qté" align="right" class="tabular-nums"
                >×{{ row.quantity }}</GoupixDexBaseTableTd
              >
              <GoupixDexBaseTableTd label="Prix marché" align="right" class="tabular-nums">
                <span v-if="row.market_price_eur != null" class="font-medium text-[var(--app-ink)]">
                  {{ eur.format(row.market_price_eur) }}
                </span>
                <span v-else class="text-xs text-[var(--app-faint)]">—</span>
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd label="Achat" align="right" class="tabular-nums">
                <span v-if="row.purchase_price_eur != null" class="text-[var(--app-ink-soft)]">
                  {{ eur.format(row.purchase_price_eur) }}
                </span>
                <span v-else class="text-xs text-[var(--app-faint)]">—</span>
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd label="Plus-value" align="right" class="tabular-nums">
                <span
                  v-if="row.gain_percent != null"
                  class="font-medium"
                  :class="row.gain_percent >= 0 ? 'text-success' : 'text-error'"
                >
                  {{ formatSignedPercent(row.gain_percent) }}
                </span>
                <span v-else class="text-xs text-[var(--app-faint)]">—</span>
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd class="goupix-card-table__actions" align="center">
                <UIcon name="i-lucide-chevron-right" class="size-4 text-[var(--app-faint)]" aria-hidden="true" />
              </GoupixDexBaseTableTd>
            </GoupixDexBaseTableTr>
          </GoupixDexBaseTable>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { SealedListResponse, SealedProduct, SealedStats } from '~/composables/useSealed'
import { SEALED_TYPE_LABELS, formatSignedPercent, sealedProductTypeLabel } from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Produits scellés',
  'Suivez la valeur Cardmarket de vos ETB, coffrets et displays scellés, et leur plus-value.',
)

const { listSealed } = useSealed()
const { openSealed, openSealedFromClick } = useOpenSealedDrawer()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const payload = ref<SealedListResponse | null>(null)
const loading = ref(false)
const search = ref('')
const typeFilter = ref<string>('any')
const languageFilter = ref<string>('any')
const viewMode = ref<'grid' | 'list'>('grid')

const languageItems = [
  { label: 'Toutes les langues', value: 'any' },
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const typeFilterItems = [
  { label: 'Tous les types', value: 'any' },
  ...Object.entries(SEALED_TYPE_LABELS).map(([value, label]) => ({ value, label })),
]

const viewItems = [
  { label: 'Grille', value: 'grid', icon: 'i-lucide-grid-2x2' },
  { label: 'Liste', value: 'list', icon: 'i-lucide-list' },
]

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const stats = computed<SealedStats>(() => {
  return (
    payload.value?.stats ?? {
      unique_products: 0,
      total_quantity: 0,
      estimated_market_eur: 0,
      purchase_value_eur: 0,
      gain_eur: 0,
      gain_percent: null,
      priced_products: 0,
      with_article: 0,
      by_type: {},
    }
  )
})

const gainLabel = computed<string>(() => {
  const sign = stats.value.gain_eur >= 0 ? '+' : ''
  return `${sign}${eur.format(stats.value.gain_eur)}`
})

const gainDescription = computed<string>(() => {
  if (stats.value.gain_percent == null) {
    return 'Renseignez un prix d’achat'
  }
  return `${formatSignedPercent(stats.value.gain_percent)} vs prix d’achat`
})

const filteredItems = computed<SealedProduct[]>(() => {
  const items = payload.value?.items ?? []
  const q = search.value.trim().toLowerCase()
  return items.filter((product) => {
    if (typeFilter.value !== 'any' && product.product_type !== typeFilter.value) {
      return false
    }
    if (languageFilter.value !== 'any' && product.language !== languageFilter.value) {
      return false
    }
    if (!q) {
      return true
    }
    return product.name.toLowerCase().includes(q) || (product.set_name?.toLowerCase().includes(q) ?? false)
  })
})

async function load(): Promise<void> {
  loading.value = true
  try {
    payload.value = await listSealed()
  } catch (e) {
    toast.add({ title: 'Produits scellés', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

/**
 * Ouvre la fiche produit dans le drawer (clic modifié = navigation normale).
 * @param id - Identifiant du produit scellé.
 * @param event - Événement souris du clic.
 */
function onProductClick(id: number, event: MouseEvent): void {
  openSealedFromClick(id, event)
}

// Resynchronise la liste quand le drawer modifie ou supprime un produit.
watch(
  () => drawerStack.sealedMutationCounter.value,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
})
</script>
