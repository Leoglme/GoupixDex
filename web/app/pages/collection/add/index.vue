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
        <NuxtLink
          to="/collection"
          class="inline-flex w-fit items-center gap-1 text-sm font-medium text-(--app-accent) underline-offset-4 transition hover:text-(--app-accent) hover:underline"
        >
          <UIcon name="i-lucide-arrow-left" class="size-4 shrink-0" aria-hidden />
          Retour
        </NuxtLink>

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
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
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
          <ul class="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            <li v-for="card in searchHits" :key="card.id">
              <button
                type="button"
                class="group w-full text-left"
                :disabled="pendingCardId === card.id"
                @click="onPickSearchCard(card)"
              >
                <div class="border-default bg-elevated/30 relative aspect-[63/88] overflow-hidden rounded-xl border">
                  <img
                    v-if="cardThumb(card)"
                    :src="cardThumb(card)"
                    :alt="cardLabel(card)"
                    class="h-full w-full object-contain transition group-hover:scale-[1.03]"
                    referrerpolicy="no-referrer"
                    loading="lazy"
                  />
                  <div v-else class="flex h-full items-center justify-center">
                    <UIcon name="i-lucide-image-off" class="text-muted size-8" />
                  </div>
                  <span
                    v-if="ownedCount(card.id) > 0"
                    class="bg-success/90 text-inverted absolute top-1.5 right-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  >
                    ×{{ ownedCount(card.id) }}
                  </span>
                </div>
                <p class="text-highlighted group-hover:text-primary mt-2 truncate text-sm font-medium">
                  {{ cardLabel(card) }}
                </p>
                <p class="text-muted truncate text-xs">{{ card.set_name }} · #{{ card.localId }}</p>
              </button>
            </li>
          </ul>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { CatalogSearchCardHit, TcgdexSeriesWithSets } from '~/composables/useCardCatalog'
import { cardThumbFromImage } from '~/utils/catalogAssets'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo('Catalogue Pokémon', 'Navigateur d’extensions TCGdex pour alimenter votre collection GoupixDex.')

const route = useRoute()
const toast = useToast()
const { browseCatalog, searchCatalogCards } = useCardCatalog()
const { addToCollection, listCollection } = useCollection()
const { catalogLanguage, catalogLanguageItems } = useCatalogLanguage()
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

function onPickSearchCard(card: CatalogSearchCardHit): void {
  void addCard(card.id, cardLabel(card))
}

async function refreshOwnedIndex(): Promise<void> {
  try {
    const res = await listCollection({ language: catalogLanguage.value })
    const map = new Map<string, number>()
    res.items.forEach((c) => map.set(c.tcgdex_card_id, c.quantity))
    ownedCards.value = map
  } catch {
    /* best-effort */
  }
}

onMounted(() => {
  const qLoc = route.query.locale
  if (qLoc === 'ja' || qLoc === 'en' || qLoc === 'fr') {
    catalogLanguage.value = qLoc
  }
  void loadBrowse()
  void refreshOwnedIndex()
})
</script>
