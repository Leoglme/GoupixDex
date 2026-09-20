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
        <GoupixDexPageHeader
          title="Ajouter un produit scellé"
          description="Parcourez une extension ou recherchez un produit, puis cliquez pour l'ajouter."
        >
          <template #actions>
            <UButton color="neutral" variant="ghost" icon="i-lucide-arrow-left" to="/collection/produits">
              Retour
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <UInput
          v-model="query"
          icon="i-lucide-search"
          :placeholder="
            openExpansion ? `Filtrer dans ${openExpansion.label}…` : 'Rechercher un produit (ex. surging sparks etb)…'
          "
          size="lg"
          class="w-full"
          autofocus
        />

        <div v-if="loading" class="flex items-center justify-center py-24">
          <UIcon name="i-lucide-loader-2" class="text-primary size-9 animate-spin" />
        </div>

        <!-- Produits d'une extension ouverte, ou résultats de recherche globale -->
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
              <span v-if="openExpansion" class="text-highlighted font-medium">{{ openExpansion.label }} · </span>
              {{ visibleProducts.length }} produit(s)
            </p>
          </div>

          <UCard v-if="visibleProducts.length === 0" :ui="{ body: 'p-8 text-center space-y-2' }">
            <UIcon name="i-lucide-search-x" class="text-muted mx-auto size-8" />
            <p class="text-highlighted text-sm font-medium">Aucun produit pour « {{ query.trim() }} ».</p>
            <p class="text-muted text-sm">Essayez le nom de l'extension (ex. « Cosmic Eclipse ») ou un autre terme.</p>
          </UCard>

          <div v-else class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            <button
              v-for="product in visibleProducts"
              :key="product.p"
              type="button"
              class="border-default bg-elevated/30 focus-visible:ring-primary group flex items-center gap-3 rounded-xl border p-2.5 text-left transition-colors hover:border-(--app-accent) focus-visible:ring-2 focus-visible:outline-none"
              :disabled="pendingId === product.p"
              @click="addProduct(product)"
            >
              <span
                class="flex size-11 shrink-0 items-center justify-center rounded-lg bg-(--app-accent-soft) text-(--app-accent-ink)"
              >
                <UIcon
                  :name="pendingId === product.p ? 'i-lucide-loader-2' : sealedProductTypeIcon(product.c)"
                  class="size-5"
                  :class="pendingId === product.p ? 'animate-spin' : ''"
                />
              </span>
              <span class="min-w-0 flex-1">
                <span class="text-highlighted block truncate text-sm font-medium">{{ product.n }}</span>
                <span class="text-muted flex items-center gap-1.5 text-xs">
                  {{ sealedProductTypeLabel(product.c) }}
                  <span v-if="priceOf(product.p) != null" class="text-highlighted tabular-nums">
                    · {{ eur.format(priceOf(product.p) as number) }}
                  </span>
                </span>
              </span>
              <span
                v-if="ownedOf(product.p) > 0"
                class="bg-success/90 text-inverted shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums"
                title="Déjà dans ta collection"
              >
                ×{{ ownedOf(product.p) }}
              </span>
              <UIcon
                v-else
                name="i-lucide-plus"
                class="text-muted size-4 shrink-0 group-hover:text-(--app-accent)"
                aria-hidden="true"
              />
            </button>
          </div>
        </template>

        <!-- Liste des extensions (par défaut) -->
        <template v-else>
          <p class="text-muted text-sm tabular-nums">{{ expansions.length }} extensions</p>
          <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            <button
              v-for="expansion in expansions"
              :key="expansion.id"
              type="button"
              class="border-default bg-elevated/30 focus-visible:ring-primary group flex items-center justify-between gap-2 rounded-xl border px-3 py-3 text-left transition-colors hover:border-(--app-accent) focus-visible:ring-2 focus-visible:outline-none"
              @click="openExp(expansion)"
            >
              <span class="min-w-0">
                <span class="text-highlighted block truncate text-sm font-medium">{{ expansion.label }}</span>
                <span class="text-muted text-xs tabular-nums">{{ expansion.count }} produit(s)</span>
              </span>
              <UIcon name="i-lucide-chevron-right" class="text-muted size-4 shrink-0 group-hover:text-(--app-accent)" />
            </button>
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { SealedProductType } from '~/composables/useSealed'
import type { SealedCatalogExpansion, SealedCatalogProduct } from '~/composables/useSealedCatalog'
import { sealedProductTypeIcon, sealedProductTypeLabel } from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Ajouter un produit scellé',
  'Parcourez le catalogue Cardmarket des produits scellés et ajoutez-les en un clic.',
)

const { loadExpansions, quotePrices } = useSealedCatalog()
const { catalogAdd, listSealed } = useSealed()
const toast = useToast()

const expansions = ref<SealedCatalogExpansion[]>([])
const openExpansion = ref<SealedCatalogExpansion | null>(null)
const query = ref('')
const loading = ref(true)
const pendingId = ref<number | null>(null)
const priceMap = ref<Map<number, number | null>>(new Map())
const ownedMap = ref<Map<number, number>>(new Map())

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const SEARCH_LIMIT = 80

const visibleProducts = computed<SealedCatalogProduct[]>(() => {
  const q = query.value.trim().toLowerCase()
  if (openExpansion.value) {
    const products = openExpansion.value.products
    return q ? products.filter((p) => p.n.toLowerCase().includes(q)) : products
  }
  if (q.length < 2) {
    return []
  }
  const hits: SealedCatalogProduct[] = []
  for (const expansion of expansions.value) {
    for (const product of expansion.products) {
      if (product.n.toLowerCase().includes(q)) {
        hits.push(product)
        if (hits.length >= SEARCH_LIMIT) {
          return hits
        }
      }
    }
  }
  return hits
})

/**
 * Prix marché connu pour un idProduct (ou `null`/`undefined` si non coté / non chargé).
 * @param idProduct - idProduct Cardmarket.
 * @returns Le prix, ou null/undefined.
 */
function priceOf(idProduct: number): number | null | undefined {
  return priceMap.value.get(idProduct)
}

/**
 * Quantité déjà possédée pour un idProduct.
 * @param idProduct - idProduct Cardmarket.
 * @returns La quantité possédée (0 si aucune).
 */
function ownedOf(idProduct: number): number {
  return ownedMap.value.get(idProduct) ?? 0
}

/**
 * Récupère les prix marché manquants pour les produits affichés (cotation en lot).
 * @param products - Produits actuellement visibles.
 * @returns Résolue après mise à jour du cache de prix.
 */
async function ensurePrices(products: SealedCatalogProduct[]): Promise<void> {
  const missing = products.map((p) => p.p).filter((id) => !priceMap.value.has(id))
  if (!missing.length) {
    return
  }
  try {
    const prices = await quotePrices(missing)
    const next = new Map(priceMap.value)
    for (const id of missing) {
      next.set(id, prices[String(id)] ?? null)
    }
    priceMap.value = next
  } catch {
    /* best-effort : la fiche reste ajoutable sans prix affiché */
  }
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
 * Referme l'extension ouverte (retour à la liste des extensions).
 */
function closeExpansion(): void {
  openExpansion.value = null
  query.value = ''
}

/**
 * Ajoute un produit du catalogue à la collection (idempotent : incrémente si déjà possédé).
 * @param product - Produit catalogue cliqué.
 * @returns Résolue après ajout.
 */
async function addProduct(product: SealedCatalogProduct): Promise<void> {
  if (pendingId.value) {
    return
  }
  pendingId.value = product.p
  try {
    const res = await catalogAdd({
      cardmarket_id_product: product.p,
      name: product.n,
      product_type: product.c as SealedProductType,
      set_name: openExpansion.value?.label ?? null,
    })
    const next = new Map(ownedMap.value)
    next.set(product.p, res.product.quantity)
    ownedMap.value = next
    toast.add({
      title: res.created ? 'Ajouté à ta collection' : `Quantité ×${res.product.quantity}`,
      description: product.n,
      color: 'success',
    })
  } catch (e) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    pendingId.value = null
  }
}

/**
 * Charge l'index des produits déjà possédés (pour le badge « déjà en collection »).
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

watch(visibleProducts, (products) => {
  void ensurePrices(products)
})

onMounted(async () => {
  loading.value = true
  try {
    const list = await loadExpansions()
    // Extensions récentes d'abord (idExpansion croissant avec le temps chez Cardmarket).
    expansions.value = [...list].sort((a, b) => b.id - a.id)
  } finally {
    loading.value = false
  }
  void loadOwned()
})
</script>
