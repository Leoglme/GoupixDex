<template>
  <UDashboardPanel id="add-sealed-page">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-box" class="h-3 w-3 text-(--app-accent)" />
            Ajouter un produit
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full">
        <GoupixDexBackLink to="/collection/produits" />

        <GoupixDexPageHeader
          title="Ajouter un produit scellé"
          description="Choisis une extension ou recherche un produit, puis clique pour l'ajouter."
        />

        <UInput
          v-model="query"
          icon="i-lucide-search"
          :placeholder="
            openExpansion ? `Filtrer dans ${openExpansion.name}…` : 'Rechercher un produit (ex. surging sparks etb)…'
          "
          size="lg"
          class="w-full"
          autofocus
        />

        <div v-if="loading" class="flex items-center justify-center py-24">
          <UIcon name="i-lucide-loader-2" class="text-primary size-9 animate-spin" />
        </div>

        <!-- Produits d'une extension ouverte, ou recherche globale -->
        <template v-else-if="openExpansion || query.trim().length >= 2">
          <div class="flex items-center gap-2">
            <UButton
              v-if="openExpansion"
              color="neutral"
              variant="ghost"
              size="xs"
              icon="i-lucide-arrow-left"
              @click="closeExpansion"
            >
              Extensions
            </UButton>
            <p class="text-muted text-sm tabular-nums">
              <span v-if="openExpansion" class="text-highlighted font-medium">{{ openExpansion.name }} · </span>
              {{ visibleProducts.length }} produit(s)
            </p>
          </div>

          <UCard v-if="visibleProducts.length === 0" :ui="{ body: 'p-8 text-center space-y-2' }">
            <UIcon name="i-lucide-search-x" class="text-muted mx-auto size-8" />
            <p class="text-highlighted text-sm font-medium">Aucun produit pour « {{ query.trim() }} ».</p>
            <p class="text-muted text-sm">Essaie le nom de l'extension (ex. « Surging Sparks ») ou un autre terme.</p>
          </UCard>

          <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            <div
              v-for="hit in visibleProducts"
              :key="hit.product.tp"
              role="button"
              tabindex="0"
              class="border-default bg-elevated/30 focus-visible:ring-primary group flex cursor-pointer flex-col overflow-hidden rounded-xl border text-left transition-all hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
              :class="
                ownedOf(hit.product.p) > 0
                  ? 'border-(--app-green) ring-2 ring-(--app-green)'
                  : 'hover:border-(--app-accent)'
              "
              @click="openCatalogPreview(hit)"
              @keydown.enter.prevent="openCatalogPreview(hit)"
            >
              <div
                class="relative flex aspect-[3/4] w-full items-center justify-center overflow-hidden bg-[var(--app-surface-2)] p-2"
              >
                <img
                  v-if="hit.product.img"
                  :src="hit.product.img"
                  :alt="hit.product.full"
                  class="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105"
                  referrerpolicy="no-referrer"
                  loading="lazy"
                  decoding="async"
                />
                <UIcon v-else :name="sealedProductTypeIcon(hit.product.c)" class="text-muted size-8" />
                <span
                  v-if="ownedOf(hit.product.p) > 0"
                  class="absolute top-1.5 left-1.5 flex items-center gap-0.5 rounded-full bg-(--app-green) px-1.5 py-0.5 text-[11px] font-bold text-white shadow-sm"
                >
                  <UIcon name="i-lucide-check" class="size-3" />{{ ownedOf(hit.product.p) }}
                </span>
                <button
                  type="button"
                  class="bg-elevated/95 text-highlighted focus-visible:ring-primary absolute right-1.5 bottom-1.5 flex size-6 items-center justify-center rounded-full backdrop-blur-sm transition-colors hover:bg-(--app-accent) hover:text-white focus-visible:ring-2 focus-visible:outline-none"
                  :disabled="pendingTp === hit.product.tp"
                  :aria-label="`Ajouter ${hit.product.n} directement`"
                  @click.stop="addProduct(hit.product, hit.expansionName)"
                >
                  <UIcon
                    :name="pendingTp === hit.product.tp ? 'i-lucide-loader-2' : 'i-lucide-plus'"
                    class="size-3.5"
                    :class="pendingTp === hit.product.tp ? 'animate-spin' : ''"
                  />
                </button>
              </div>
              <div class="min-w-0 space-y-0.5 p-2">
                <p class="text-highlighted truncate text-xs leading-snug font-medium">{{ hit.product.n }}</p>
                <p class="text-muted flex items-center justify-between gap-1 text-[10px]">
                  <span class="truncate">{{ sealedProductTypeLabel(hit.product.c) }}</span>
                  <span v-if="displayPriceEur(hit.product) != null" class="text-highlighted shrink-0 tabular-nums">
                    {{ eur.format(displayPriceEur(hit.product)!) }}
                  </span>
                </p>
              </div>
            </div>
          </div>
        </template>

        <!-- Séries vers extensions (par défaut) -->
        <template v-else>
          <section v-for="serie in series" :key="serie.name" class="space-y-3">
            <div class="flex items-center gap-2.5">
              <h2 class="text-highlighted text-sm font-semibold">{{ serie.name }}</h2>
              <span class="text-muted text-xs tabular-nums">{{ serie.expansions.length }} extensions</span>
            </div>
            <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              <button
                v-for="expansion in serie.expansions"
                :key="expansion.id"
                type="button"
                class="border-default bg-elevated/30 focus-visible:ring-primary group flex flex-col items-center gap-2 rounded-xl border p-3 text-center transition-all hover:border-(--app-accent) hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
                @click="openExp(expansion)"
              >
                <div class="flex h-14 w-full items-center justify-center">
                  <GoupixDexCatalogSetLogo :logo="expansion.logo ?? undefined" :name="expansion.name" large />
                </div>
                <div class="min-w-0">
                  <p class="text-highlighted truncate text-xs font-medium">{{ expansion.name }}</p>
                  <p class="text-muted text-[10px] tabular-nums">{{ expansion.count }} produit(s)</p>
                </div>
              </button>
            </div>
          </section>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { SealedProductType } from '~/composables/useSealed'
import type {
  SealedCatalogExpansion,
  SealedCatalogProduct,
  SealedCatalogSearchHit,
  SealedCatalogSerie,
} from '~/composables/useSealedCatalog'
import { sealedProductTypeIcon, sealedProductTypeLabel } from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Ajouter un produit scellé',
  'Parcourez le catalogue des produits scellés (vraies images) et ajoutez-les en un clic.',
)

const { loadSeries } = useSealedCatalog()
const { catalogAdd, listSealed, quoteCatalogPrices } = useSealed()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const series = ref<SealedCatalogSerie[]>([])
const openExpansion = ref<SealedCatalogExpansion | null>(null)
const query = ref('')
const loading = ref(true)
const pendingTp = ref<number | null>(null)
const ownedMap = ref<Map<number, number>>(new Map())
const marketPriceCache = ref<Map<number, number | null>>(new Map())

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const SEARCH_LIMIT = 80

const visibleProducts = computed<SealedCatalogSearchHit[]>(() => {
  const q = query.value.trim().toLowerCase()
  if (openExpansion.value) {
    const name = openExpansion.value.name
    const products = q
      ? openExpansion.value.products.filter((p) => p.full.toLowerCase().includes(q))
      : openExpansion.value.products
    return products.map((product) => ({ product, expansionName: name }))
  }
  if (q.length < 2) {
    return []
  }
  const hits: SealedCatalogSearchHit[] = []
  for (const serie of series.value) {
    for (const expansion of serie.expansions) {
      for (const product of expansion.products) {
        if (product.full.toLowerCase().includes(q)) {
          hits.push({ product, expansionName: expansion.name })
          if (hits.length >= SEARCH_LIMIT) {
            return hits
          }
        }
      }
    }
  }
  return hits
})

/**
 * Quantité déjà possédée pour un idProduct Cardmarket.
 * @param idProduct - idProduct Cardmarket du produit catalogue (peut être null).
 * @returns La quantité possédée (0 si aucune ou non apparié).
 */
function ownedOf(idProduct: number | null): number {
  return idProduct != null ? (ownedMap.value.get(idProduct) ?? 0) : 0
}

/**
 * Prix marché à afficher : Cardmarket réel si résolu, sinon repli catalogue (TCGplayer).
 * @param product - Produit catalogue.
 * @returns Le prix € à afficher, ou null si inconnu.
 */
function displayPriceEur(product: SealedCatalogProduct): number | null {
  if (product.p != null && marketPriceCache.value.has(product.p)) {
    return marketPriceCache.value.get(product.p) ?? product.price
  }
  return product.price
}

/**
 * Cote au prix marché Cardmarket (en lot) les produits visibles pas encore en cache.
 * @param hits - Produits actuellement affichés.
 * @returns Résolue après mise à jour du cache (best-effort).
 */
async function ensureMarketPrices(hits: SealedCatalogSearchHit[]): Promise<void> {
  const missing = new Set<number>()
  for (const { product } of hits) {
    if (product.p != null && !marketPriceCache.value.has(product.p)) {
      missing.add(product.p)
    }
  }
  if (missing.size === 0) {
    return
  }
  try {
    const prices = await quoteCatalogPrices([...missing])
    const next = new Map(marketPriceCache.value)
    for (const [idProduct, value] of Object.entries(prices)) {
      next.set(Number(idProduct), value)
    }
    marketPriceCache.value = next
  } catch {
    /* best-effort : on garde le prix catalogue */
  }
}

/**
 * Ouvre l'aperçu d'un produit (prix, courbe, ajout) dans le drawer, sans l'ajouter directement.
 * @param hit - Produit catalogue + nom d'extension.
 */
function openCatalogPreview(hit: SealedCatalogSearchHit): void {
  drawerStack.pushSealedCatalog(hit.product, hit.expansionName)
}

/**
 * Ouvre une extension pour lister ses produits.
 * @param expansion - Extension choisie.
 */
function openExp(expansion: SealedCatalogExpansion): void {
  openExpansion.value = expansion
  query.value = ''
}

/**
 * Referme l'extension ouverte (retour aux séries).
 */
function closeExpansion(): void {
  openExpansion.value = null
  query.value = ''
}

/**
 * Ajoute un produit du catalogue à la collection (idempotent si apparié à Cardmarket).
 * @param product - Produit catalogue cliqué.
 * @param expansionName - Nom de l'extension (stocké comme set).
 * @returns Résolue après ajout.
 */
async function addProduct(product: SealedCatalogProduct, expansionName: string): Promise<void> {
  if (pendingTp.value) {
    return
  }
  pendingTp.value = product.tp
  try {
    const res = await catalogAdd({
      name: product.n,
      product_type: product.c as SealedProductType,
      set_name: expansionName,
      cardmarket_id_product: product.p,
      image_url: product.img,
      market_price_eur: product.price,
    })
    if (product.p != null) {
      const next = new Map(ownedMap.value)
      next.set(product.p, res.product.quantity)
      ownedMap.value = next
    }
    toast.add({
      title: res.created ? 'Ajouté à ta collection' : `Quantité ×${res.product.quantity}`,
      description: product.full,
      color: 'success',
    })
  } catch (e) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    pendingTp.value = null
  }
}

/**
 * Charge l'index des produits déjà possédés (badge « déjà en collection »).
 * @returns Résolue après chargement (best-effort).
 */
async function loadOwned(): Promise<void> {
  try {
    const res = await listSealed()
    const map = new Map<number, number>()
    for (const item of res.items) {
      if (item.cardmarket_id_product != null) {
        map.set(item.cardmarket_id_product, item.quantity)
      }
    }
    ownedMap.value = map
  } catch {
    /* best-effort */
  }
}

watch(
  () => drawerStack.sealedMutationCounter.value,
  () => {
    void loadOwned()
  },
)

watch(
  visibleProducts,
  (hits) => {
    void ensureMarketPrices(hits)
  },
  { immediate: true },
)

onMounted(async () => {
  loading.value = true
  try {
    series.value = await loadSeries()
  } finally {
    loading.value = false
  }
  void loadOwned()
})
</script>
