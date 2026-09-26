<template>
  <UDashboardPanel id="collection-catalog-page">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Collection
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full space-y-4 sm:space-y-5">
        <GoupixDexBackLink to="/collection" />

        <GoupixDexPageHeader
          title="Catalogue Pokémon"
          description="Parcourez les extensions TCGdex et ajoutez des cartes à votre collection."
        >
          <template #actions>
            <UButton
              v-if="!isDesktopApp"
              to="/collection/scan"
              color="neutral"
              variant="subtle"
              icon="i-lucide-scan-line"
            >
              Scanner
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
          <UFormField label="Recherche" class="min-w-0 flex-1">
            <UInput
              v-model="query"
              icon="i-lucide-search"
              placeholder="Carte (ex. pikachu 27) ou extension (ex. 151, sv04)…"
              class="w-full"
              autofocus
            />
          </UFormField>
          <UFormField label="Langue" class="w-full shrink-0 sm:w-44">
            <USelect
              v-model="catalogLanguage"
              :items="catalogLanguageItems"
              value-key="value"
              label-key="label"
              class="w-full"
            />
          </UFormField>
        </div>

        <div v-if="browseLoading && !seriesTree.length" class="flex items-center justify-center py-24">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="searchMode === 'idle'">
          <GoupixDexCatalogExtensionsBrowser
            :series="seriesTree"
            :catalog-locale="catalogLanguage"
            :extension-filter="query"
          />
        </template>

        <template v-else-if="searchMode === 'loading'">
          <div class="app-pokemon-card-grid">
            <div v-for="i in 10" :key="i" class="bg-muted/20 aspect-[63/88] animate-pulse rounded-xl" />
          </div>
        </template>

        <template v-else-if="searchMode === 'error'">
          <UAlert
            color="error"
            title="Recherche indisponible"
            description="TCGdex est injoignable, réessayez dans un instant."
          />
        </template>

        <template v-else-if="searchMode === 'done' && searchHits.length === 0">
          <UCard :ui="{ body: 'p-5 space-y-2' }">
            <p class="text-highlighted text-sm font-medium">Aucune carte trouvée pour « {{ query.trim() }} ».</p>
            <p class="text-muted text-sm">
              Essayez un autre nom ou filtrez les extensions sans lancer la recherche carte.
            </p>
          </UCard>
        </template>

        <template v-else-if="searchMode === 'done'">
          <p class="text-muted text-sm tabular-nums">
            {{ searchHits.length }} carte{{ searchHits.length > 1 ? 's' : '' }} trouvée{{
              searchHits.length > 1 ? 's' : ''
            }}
          </p>
          <div class="app-pokemon-card-grid">
            <GoupixDexPokemonCardTile
              v-for="card in searchHits"
              :key="card.id"
              :name="cardLabel(card)"
              :image-url="cardThumb(card) ?? null"
              :tcgdex-card-id="card.id"
              :set-number-label="`${card.set_name} · #${card.localId}`"
              :owned-quantity="ownedCount(card.id)"
              is-addable
              :is-adding="pendingCardId === card.id"
              @select="openCardPreview(card)"
              @add="addCard(card.id, cardLabel(card))"
            />
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { CatalogLocale, CatalogSearchCardHit, TcgdexSeriesWithSets } from '~/composables/useCardCatalog'
import { cardThumbFromImage } from '~/utils/catalogAssets'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo('Catalogue Pokémon', 'Navigateur d’extensions TCGdex pour alimenter votre collection GoupixDex.')

const route = useRoute()
const toast = useToast()
const { browseCatalog, browseCatalogFromApi, searchCatalogCards } = useCardCatalog()
const { addToCollection, listCollection } = useCollection()
const { catalogLanguage, catalogLanguageItems } = useCatalogLanguage()
const drawerStack = useGoupixDrawerStack()
const { read: readBrowseCache, write: writeBrowseCache } = useCatalogBrowseCache()
const { isDesktopApp } = useDesktopRuntime()

const seriesTree = ref<TcgdexSeriesWithSets[]>([])
const browseLoading = ref(false)
const query = ref('')
const searchHits = ref<CatalogSearchCardHit[]>([])
const searchMode = ref<'idle' | 'loading' | 'done' | 'error'>('idle')
const pendingCardId = ref<string | null>(null)
const ownedCards = ref<Map<string, number>>(new Map())

let searchTimer: ReturnType<typeof setTimeout> | null = null
let searchAbort: AbortController | null = null

watch(catalogLanguage, () => {
  query.value = ''
  searchMode.value = 'idle'
  void loadBrowse(false)
  void refreshOwnedIndex()
})

watch(query, (q) => {
  const trimmed = q.trim()
  if (trimmed.length < 2) {
    searchMode.value = 'idle'
    searchHits.value = []
    searchAbort?.abort()
    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }
    return
  }
  searchMode.value = 'loading'
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    searchTimer = null
    void runSearch(trimmed)
  }, 300)
})

async function loadBrowse(force = false): Promise<void> {
  const locale = catalogLanguage.value
  if (!force) {
    const cached = readBrowseCache(locale)
    if (cached?.length) {
      seriesTree.value = cached
      return
    }
  }
  browseLoading.value = true
  try {
    const res = await browseCatalog(locale)
    const next = res.series.map((s) => ({
      ...s,
      sets: [...(s.sets ?? [])],
    }))
    seriesTree.value = next
    writeBrowseCache(locale, next)
  } catch (e) {
    toast.add({ title: 'Catalogue', description: apiErrorMessage(e), color: 'error' })
    seriesTree.value = []
  } finally {
    browseLoading.value = false
  }
  refreshBrowseFromApi(locale)
}

/**
 * Remplace l'index statique, généré sur GitHub où TCGdex répond parfois en retard, par l'arborescence de l'API dès qu'elle arrive.
 * @param locale - Langue affichée au moment du chargement.
 * @returns {Promise<void>}
 */
async function refreshBrowseFromApi(locale: CatalogLocale): Promise<void> {
  try {
    const res = await browseCatalogFromApi(locale)
    if (catalogLanguage.value !== locale || !res.series.length) {
      return
    }
    const next: TcgdexSeriesWithSets[] = res.series.map(
      (serie: TcgdexSeriesWithSets): TcgdexSeriesWithSets => ({ ...serie, sets: [...(serie.sets ?? [])] }),
    )
    seriesTree.value = next
    writeBrowseCache(locale, next)
  } catch {
    // L'index statique reste affiché.
  }
}

async function runSearch(q: string): Promise<void> {
  searchAbort?.abort()
  const controller = new AbortController()
  searchAbort = controller
  try {
    const res = await searchCatalogCards(catalogLanguage.value, q)
    if (controller.signal.aborted) {
      return
    }
    searchHits.value = res.cards
    searchMode.value = 'done'
  } catch (e) {
    if (controller.signal.aborted) {
      return
    }
    searchHits.value = []
    searchMode.value = 'error'
    toast.add({ title: 'Recherche', description: apiErrorMessage(e), color: 'error' })
  }
}

function cardLabel(card: CatalogSearchCardHit): string {
  return card.display_name?.trim() || card.name
}

function cardThumb(card: CatalogSearchCardHit): string | undefined {
  return cardThumbFromImage(card.image, card.image_low)
}

function ownedCount(cardId: string): number {
  return ownedCards.value.get(cardId) ?? 0
}

async function addCard(cardId: string, displayName: string): Promise<void> {
  if (pendingCardId.value) {
    return
  }
  pendingCardId.value = cardId
  try {
    const res = await addToCollection({
      tcgdex_card_id: cardId,
      language: catalogLanguage.value,
      quantity: 1,
    })
    ownedCards.value.set(cardId, res.card.quantity)
    toast.add({
      title: res.created ? 'Ajoutée à la collection' : `Quantité ×${res.card.quantity}`,
      description: `${displayName} · ${languageLabel(catalogLanguage.value)}`,
      color: 'success',
    })
  } catch (e) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    pendingCardId.value = null
  }
}

function languageLabel(code: string): string {
  switch (code) {
    case 'fr':
      return 'Français'
    case 'en':
      return 'Anglais'
    case 'ja':
      return 'Japonais'
    default:
      return code
  }
}

/**
 * Ouvre l'aperçu (drawer) d'une carte du catalogue : image, prix, ajout.
 * @param card - Carte trouvée en recherche.
 * @returns {void}
 */
function openCardPreview(card: CatalogSearchCardHit): void {
  drawerStack.pushCatalogCard({
    id: card.id,
    name: cardLabel(card),
    setName: card.set_name,
    localId: card.localId,
    image: cardThumb(card) ?? null,
    locale: catalogLanguage.value,
  })
}

async function refreshOwnedIndex(): Promise<void> {
  try {
    const res = await listCollection({ language: catalogLanguage.value })
    const map = new Map<string, number>()
    // Une même carte peut occuper plusieurs lignes (exemplaire gardé + exemplaire en vente) : on additionne.
    res.items.forEach((c) => map.set(c.tcgdex_card_id, (map.get(c.tcgdex_card_id) ?? 0) + c.quantity))
    ownedCards.value = map
  } catch {
    /* best-effort */
  }
}

watch(
  () => drawerStack.cardMutationCounter.value,
  () => {
    void refreshOwnedIndex()
  },
)

onMounted(() => {
  const qLoc = route.query.locale
  if (qLoc === 'ja' || qLoc === 'en' || qLoc === 'fr') {
    catalogLanguage.value = qLoc
  }
  void loadBrowse()
  void refreshOwnedIndex()
})
</script>
