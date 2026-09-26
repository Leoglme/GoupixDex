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
        <GoupixDexBackLink :to="openExpansion ? '/collection/produits/add' : '/collection/produits'" />

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

        <!-- Produits de l'extension ouverte -->
        <template v-else-if="openExpansion">
          <div class="flex flex-wrap items-center gap-4">
            <div class="flex h-14 w-32 shrink-0 items-center justify-center">
              <GoupixDexCatalogSetLogo
                :logo="openExpansion.logo ?? undefined"
                :set-id="openExpansion.tcgdex_id ?? undefined"
                locale="fr"
                :fallback-image="expansionPreviewImage(openExpansion)"
                :name="openExpansion.name"
                large
              />
            </div>
            <div class="min-w-0">
              <h2 class="text-highlighted text-xl font-semibold tracking-tight">{{ openExpansion.name }}</h2>
              <p class="text-muted text-sm tabular-nums">{{ openExpansionSummary }}</p>
            </div>
          </div>

          <div v-if="openExpansionProductTypes.length > 1" class="flex flex-wrap gap-1.5">
            <UButton
              size="xs"
              :color="productTypeFilter === null ? 'primary' : 'neutral'"
              :variant="productTypeFilter === null ? 'solid' : 'subtle'"
              @click="productTypeFilter = null"
            >
              Tous
            </UButton>
            <UButton
              v-for="productType in openExpansionProductTypes"
              :key="productType"
              size="xs"
              :color="productTypeFilter === productType ? 'primary' : 'neutral'"
              :variant="productTypeFilter === productType ? 'solid' : 'subtle'"
              @click="productTypeFilter = productTypeFilter === productType ? null : productType"
            >
              {{ sealedProductTypeLabel(productType) }}
            </UButton>
          </div>

          <UCard v-if="openExpansionHits.length === 0" :ui="{ body: 'p-8 text-center space-y-2' }">
            <UIcon name="i-lucide-search-x" class="text-muted mx-auto size-8" />
            <p class="text-highlighted text-sm font-medium">Aucun produit ne correspond.</p>
            <p class="text-muted text-sm">Change de type ou efface le filtre.</p>
          </UCard>

          <div v-else class="app-tile-grid">
            <GoupixDexSealedProductTile
              v-for="hit in openExpansionHits"
              :key="hit.product.tp"
              :name="hit.product.n"
              :image-url="hit.product.img"
              :product-type="hit.product.c"
              :price-label="formattedPrice(hit.product)"
              :owned-quantity="ownedOf(hit.product.p)"
              is-addable
              :is-adding="pendingTp === hit.product.tp"
              @select="openCatalogPreview(hit)"
              @add="addProduct(hit.product, hit.expansionName)"
            />
          </div>
        </template>

        <!-- Recherche globale, regroupée par extension -->
        <template v-else-if="query.trim().length >= 2">
          <p class="text-muted text-sm tabular-nums">
            {{ searchHitCount }} produit{{ searchHitCount > 1 ? 's' : ''
            }}{{ searchHitCount > SEARCH_LIMIT ? `, les ${SEARCH_LIMIT} premiers affichés` : '' }}
          </p>

          <UCard v-if="searchGroups.length === 0" :ui="{ body: 'p-8 text-center space-y-2' }">
            <UIcon name="i-lucide-search-x" class="text-muted mx-auto size-8" />
            <p class="text-highlighted text-sm font-medium">Aucun produit pour « {{ query.trim() }} ».</p>
            <p class="text-muted text-sm">Essaie le nom de l'extension (ex. « Surging Sparks ») ou un autre terme.</p>
          </UCard>

          <section v-for="group in searchGroups" :key="group.expansionName" class="space-y-3">
            <h2 class="text-highlighted text-sm font-semibold">{{ group.expansionName }}</h2>
            <div class="app-tile-grid">
              <GoupixDexSealedProductTile
                v-for="hit in group.hits"
                :key="hit.product.tp"
                :name="hit.product.n"
                :image-url="hit.product.img"
                :product-type="hit.product.c"
                :price-label="formattedPrice(hit.product)"
                :owned-quantity="ownedOf(hit.product.p)"
                is-addable
                :is-adding="pendingTp === hit.product.tp"
                @select="openCatalogPreview(hit)"
                @add="addProduct(hit.product, hit.expansionName)"
              />
            </div>
          </section>
        </template>

        <!-- Séries vers extensions (par défaut) -->
        <template v-else>
          <section v-for="serie in series" :key="serie.name" class="space-y-3">
            <div class="flex items-center gap-2.5">
              <h2 class="text-highlighted text-sm font-semibold">{{ serie.name }}</h2>
              <span class="text-muted text-xs tabular-nums">{{ serie.expansions.length }} extensions</span>
            </div>
            <div class="app-tile-grid">
              <GoupixDexExtensionTile
                v-for="expansion in serie.expansions"
                :key="`${expansion.id}-${expansion.name}`"
                :to="expansionLink(expansion)"
                :name="expansion.name"
                :summary-label="expansionSummary(expansion)"
              >
                <template #logo>
                  <GoupixDexCatalogSetLogo
                    :logo="expansion.logo ?? undefined"
                    :set-id="expansion.tcgdex_id ?? undefined"
                    locale="fr"
                    :fallback-image="expansionPreviewImage(expansion)"
                    :name="expansion.name"
                    large
                  />
                </template>
              </GoupixDexExtensionTile>
            </div>
          </section>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { SealedCreateResponse, SealedListResponse, SealedProductType } from '~/composables/useSealed'
import type {
  SealedCatalogExpansion,
  SealedCatalogProduct,
  SealedCatalogSearchGroup,
  SealedCatalogSearchHit,
  SealedCatalogSerie,
} from '~/composables/useSealedCatalog'
import { SEALED_TYPE_LABELS, sealedProductTypeLabel } from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Ajouter un produit scellé',
  'Parcourez le catalogue des produits scellés (vraies images) et ajoutez-les en un clic.',
)

const route = useRoute()
const { loadSeries } = useSealedCatalog()
const { catalogAdd, listSealed, quoteCatalogPrices } = useSealed()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const SEARCH_LIMIT: number = 80
const PRODUCT_TYPE_ORDER: string[] = Object.keys(SEALED_TYPE_LABELS)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const series: Ref<SealedCatalogSerie[]> = ref([])
const query: Ref<string> = ref('')
const productTypeFilter: Ref<string | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const pendingTp: Ref<number | null> = ref(null)
const ownedMap: Ref<Map<number, number>> = ref(new Map())
const marketPriceCache: Ref<Map<number, number | null>> = ref(new Map())

const openExpansionSlug: ComputedRef<string | null> = computed((): string | null => {
  const raw: unknown = route.query.extension
  return typeof raw === 'string' && raw ? raw : null
})

const openExpansionSerie: ComputedRef<SealedCatalogSerie | null> = computed(
  (): SealedCatalogSerie | null =>
    series.value.find((serie: SealedCatalogSerie): boolean =>
      serie.expansions.some(
        (expansion: SealedCatalogExpansion): boolean => expansionSlug(expansion) === openExpansionSlug.value,
      ),
    ) ?? null,
)

const openExpansion: ComputedRef<SealedCatalogExpansion | null> = computed(
  (): SealedCatalogExpansion | null =>
    openExpansionSerie.value?.expansions.find(
      (expansion: SealedCatalogExpansion): boolean => expansionSlug(expansion) === openExpansionSlug.value,
    ) ?? null,
)

const openExpansionSummary: ComputedRef<string> = computed((): string => {
  if (!openExpansion.value) {
    return ''
  }
  return [openExpansionSerie.value?.name, expansionSummary(openExpansion.value)].filter(Boolean).join(' · ')
})

const openExpansionProductTypes: ComputedRef<string[]> = computed((): string[] => {
  const present: Set<string> = new Set(
    (openExpansion.value?.products ?? []).map((product: SealedCatalogProduct): string => product.c),
  )
  return PRODUCT_TYPE_ORDER.filter((productType: string): boolean => present.has(productType))
})

const openExpansionHits: ComputedRef<SealedCatalogSearchHit[]> = computed((): SealedCatalogSearchHit[] => {
  const expansion: SealedCatalogExpansion | null = openExpansion.value
  if (!expansion) {
    return []
  }
  const needle: string = query.value.trim().toLowerCase()
  return expansion.products
    .filter(
      (product: SealedCatalogProduct): boolean =>
        (!productTypeFilter.value || product.c === productTypeFilter.value) &&
        (!needle || product.full.toLowerCase().includes(needle)),
    )
    .map((product: SealedCatalogProduct): SealedCatalogSearchHit => ({ product, expansionName: expansion.name }))
})

const searchMatches: ComputedRef<SealedCatalogSearchHit[]> = computed((): SealedCatalogSearchHit[] => {
  const needle: string = query.value.trim().toLowerCase()
  if (openExpansion.value || needle.length < 2) {
    return []
  }
  const matches: SealedCatalogSearchHit[] = []
  for (const serie of series.value) {
    for (const expansion of serie.expansions) {
      for (const product of expansion.products) {
        if (product.full.toLowerCase().includes(needle)) {
          matches.push({ product, expansionName: expansion.name })
        }
      }
    }
  }
  return matches
})

const searchHits: ComputedRef<SealedCatalogSearchHit[]> = computed((): SealedCatalogSearchHit[] =>
  searchMatches.value.slice(0, SEARCH_LIMIT),
)

const searchHitCount: ComputedRef<number> = computed((): number => searchMatches.value.length)

const searchGroups: ComputedRef<SealedCatalogSearchGroup[]> = computed((): SealedCatalogSearchGroup[] => {
  const groups: Map<string, SealedCatalogSearchGroup> = new Map()
  for (const hit of searchHits.value) {
    const group: SealedCatalogSearchGroup = groups.get(hit.expansionName) ?? {
      expansionName: hit.expansionName,
      hits: [],
    }
    group.hits.push(hit)
    groups.set(hit.expansionName, group)
  }
  return [...groups.values()]
})

const displayedHits: ComputedRef<SealedCatalogSearchHit[]> = computed((): SealedCatalogSearchHit[] =>
  openExpansion.value ? openExpansionHits.value : searchHits.value,
)

/**
 * Identifiant d'URL d'une extension : son nom en minuscules sans accents (les codes TCGplayer ne sont pas uniques).
 * @param expansion - Extension du catalogue.
 * @returns Le slug utilisé dans `?extension=`.
 */
function expansionSlug(expansion: SealedCatalogExpansion): string {
  return expansion.name
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

/**
 * Lien qui ouvre une extension dans la page (entrée d'historique, donc « Retour » ramène aux extensions).
 * @param expansion - Extension à ouvrir.
 * @returns La route de la page avec l'extension en paramètre.
 */
function expansionLink(expansion: SealedCatalogExpansion): string {
  return `/collection/produits/add?extension=${encodeURIComponent(expansionSlug(expansion))}`
}

/**
 * Nombre de produits et année de sortie d'une extension.
 * @param expansion - Extension du catalogue.
 * @returns Le libellé (ex. « 17 produits · 2026 »).
 */
function expansionSummary(expansion: SealedCatalogExpansion): string {
  const productCount: number = expansion.products.length
  const year: string = expansion.published_on?.slice(0, 4) ?? ''
  const countLabel: string = `${productCount} produit${productCount > 1 ? 's' : ''}`
  return year ? `${countLabel} · ${year}` : countLabel
}

/**
 * Image d'un produit de l'extension, montrée à la place du logo quand l'extension n'en a pas.
 * @param expansion - Extension du catalogue.
 * @returns L'URL de la première image produit, ou `undefined` sans produit illustré.
 */
function expansionPreviewImage(expansion: SealedCatalogExpansion): string | undefined {
  return expansion.products.find((product: SealedCatalogProduct): boolean => Boolean(product.img))?.img ?? undefined
}

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
 * Prix marché formaté en euros pour la tuile.
 * @param product - Produit catalogue.
 * @returns Le prix formaté, ou null si inconnu.
 */
function formattedPrice(product: SealedCatalogProduct): string | null {
  const price: number | null = displayPriceEur(product)
  return price != null ? eur.format(price) : null
}

/**
 * Cote au prix marché Cardmarket (en lot) les produits visibles pas encore en cache.
 * @param hits - Produits actuellement affichés.
 * @returns Résolue après mise à jour du cache (best-effort).
 */
async function ensureMarketPrices(hits: SealedCatalogSearchHit[]): Promise<void> {
  const missing: Set<number> = new Set()
  for (const { product } of hits) {
    if (product.p != null && !marketPriceCache.value.has(product.p)) {
      missing.add(product.p)
    }
  }
  if (missing.size === 0) {
    return
  }
  try {
    const prices: Record<string, number | null> = await quoteCatalogPrices([...missing])
    const next: Map<number, number | null> = new Map(marketPriceCache.value)
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
 * @returns {void}
 */
function openCatalogPreview(hit: SealedCatalogSearchHit): void {
  drawerStack.pushSealedCatalog(hit.product, hit.expansionName)
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
    const addResult: SealedCreateResponse = await catalogAdd({
      name: product.n,
      product_type: product.c as SealedProductType,
      set_name: expansionName,
      cardmarket_id_product: product.p,
      image_url: product.img,
      market_price_eur: product.price,
    })
    if (product.p != null) {
      const next: Map<number, number> = new Map(ownedMap.value)
      next.set(product.p, addResult.product.quantity)
      ownedMap.value = next
    }
    toast.add({
      title: addResult.created ? 'Ajouté à ta collection' : `Quantité ×${addResult.product.quantity}`,
      description: product.full,
      color: 'success',
    })
  } catch (error) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(error), color: 'error' })
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
    const ownedList: SealedListResponse = await listSealed()
    const map: Map<number, number> = new Map()
    for (const item of ownedList.items) {
      if (item.cardmarket_id_product != null) {
        map.set(item.cardmarket_id_product, item.quantity)
      }
    }
    ownedMap.value = map
  } catch {
    /* best-effort */
  }
}

watch(openExpansionSlug, (): void => {
  query.value = ''
  productTypeFilter.value = null
})

watch(
  (): number => drawerStack.sealedMutationCounter.value,
  (): void => {
    loadOwned()
  },
)

watch(
  displayedHits,
  (hits: SealedCatalogSearchHit[]): void => {
    ensureMarketPrices(hits)
  },
  { immediate: true },
)

onMounted(async (): Promise<void> => {
  loading.value = true
  try {
    series.value = await loadSeries()
  } finally {
    loading.value = false
  }
  loadOwned()
})
</script>
