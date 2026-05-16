<template>
  <UDashboardPanel id="collection-add-page">
    <template #header>
      <UDashboardNavbar title="Catalogue Pokémon">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/collection" color="neutral" variant="ghost" icon="i-lucide-album"> Ma collection </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-4 px-4 py-5 sm:space-y-5 sm:px-6 sm:py-6">
        <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4 sm:p-5 space-y-4' }">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end">
            <UFormField label="Langue du catalogue" class="w-full lg:w-56">
              <USelect
                v-model="catalogLocale"
                :items="catalogLocaleItems"
                value-key="value"
                label-key="label"
                class="w-full"
              />
            </UFormField>
            <UFormField label="Langue de mes cartes" class="w-full lg:w-56">
              <USelect
                v-model="physicalLanguage"
                :items="physicalLanguageItems"
                value-key="value"
                label-key="label"
                class="w-full"
              />
            </UFormField>
            <UFormField label="Recherche série ou extension" class="w-full lg:flex-1">
              <UInput
                v-model="search"
                placeholder="Ex. Écarlate, 151, sv04…"
                icon="i-lucide-search"
                class="w-full"
                @update:model-value="scheduleSearch"
              />
            </UFormField>
            <UButton
              :loading="seriesLoading || setsLoading"
              color="neutral"
              variant="soft"
              icon="i-lucide-refresh-cw"
              @click="loadBrowse(true)"
            >
              Actualiser
            </UButton>
          </div>

          <UBreadcrumb :items="breadcrumbItems" :ui="{ list: 'flex-wrap' }" />
        </UCard>

        <div v-if="initialLoading" class="flex items-center justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else>
          <div v-if="selectedSet" class="space-y-4">
            <div class="flex flex-wrap items-end justify-between gap-3">
              <div class="flex items-center gap-3">
                <div class="bg-primary/10 flex size-12 shrink-0 items-center justify-center rounded-xl">
                  <img
                    v-if="selectedSet.logo"
                    :src="selectedSet.logo"
                    :alt="selectedSetDisplayName"
                    class="size-10 object-contain"
                    referrerpolicy="no-referrer"
                    decoding="async"
                  />
                  <UIcon v-else name="i-lucide-package" class="text-muted size-6" />
                </div>
                <div class="min-w-0">
                  <p class="text-muted text-xs">Extension</p>
                  <p class="text-highlighted text-base font-semibold">{{ selectedSetDisplayName }}</p>
                  <p class="text-muted text-xs">
                    {{ selectedSet.id }} ·
                    {{ selectedSet.cardCount?.official ?? selectedSet.cardCount?.total ?? '?' }} cartes
                  </p>
                </div>
              </div>
            </div>

            <div v-if="setLoading" class="flex items-center justify-center py-16">
              <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
            </div>

            <div
              v-else
              class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8"
            >
              <button
                v-for="c in catalogCardsDisplay"
                :key="c.id"
                type="button"
                class="group bg-elevated/30 border-default focus-visible:ring-primary relative overflow-hidden rounded-xl border transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
                :class="{ 'pointer-events-none opacity-60': pendingCardId === c.id }"
                @click="onPickCard(c)"
              >
                <div class="bg-muted/30 relative aspect-[63/88] w-full">
                  <img
                    v-if="c.thumbUrl"
                    :src="c.thumbUrl"
                    :alt="c.displayName"
                    class="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.04]"
                    referrerpolicy="no-referrer"
                    decoding="async"
                    loading="lazy"
                  />
                  <div
                    v-if="pendingCardId === c.id"
                    class="absolute inset-0 flex items-center justify-center bg-black/40"
                  >
                    <UIcon name="i-lucide-loader-2" class="size-7 animate-spin text-white" />
                  </div>
                  <span
                    v-if="ownedCount(c.id) > 0"
                    class="bg-success/90 text-inverted absolute top-1.5 right-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
                    title="Déjà dans la collection"
                  >
                    ×{{ ownedCount(c.id) }}
                  </span>
                </div>
                <div class="space-y-0.5 px-2 py-1.5 text-left">
                  <p class="text-highlighted truncate text-xs leading-snug font-medium">
                    {{ c.displayName }}
                  </p>
                  <p class="text-muted text-[10px]">#{{ c.localId }}</p>
                </div>
              </button>
            </div>
          </div>

          <div v-else-if="activeSeriesId" class="space-y-3">
            <div v-if="seriesDetailLoading" class="flex items-center justify-center py-16">
              <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
            </div>
            <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <button
                v-for="s in setsInSeries"
                :key="s.id"
                type="button"
                class="bg-elevated/30 border-default group focus-visible:ring-primary flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
                @click="openSet(s)"
              >
                <div class="bg-primary/10 flex size-14 shrink-0 items-center justify-center rounded-xl">
                  <img
                    v-if="s.logo"
                    :src="s.logo"
                    :alt="briefDisplayName(s)"
                    class="size-11 object-contain"
                    referrerpolicy="no-referrer"
                    decoding="async"
                    loading="lazy"
                  />
                  <UIcon v-else name="i-lucide-package" class="text-muted size-6" />
                </div>
                <div class="min-w-0 flex-1">
                  <p class="text-highlighted truncate text-sm font-medium">
                    {{ briefDisplayName(s) }}
                  </p>
                  <p class="text-muted text-xs">
                    {{ s.id }} · {{ s.cardCount?.official ?? s.cardCount?.total ?? '?' }} cartes
                  </p>
                </div>
                <UIcon
                  name="i-lucide-chevron-right"
                  class="text-muted size-4 shrink-0 transition-transform group-hover:translate-x-0.5"
                />
              </button>
            </div>
            <div
              v-if="!seriesDetailLoading && !setsInSeries.length"
              class="border-default text-muted rounded-xl border border-dashed p-10 text-center text-sm"
            >
              Aucune extension dans cette série.
            </div>
          </div>

          <div v-else class="space-y-4">
            <template v-if="search.trim()">
              <div v-if="seriesSorted.length" class="space-y-2">
                <p class="text-muted text-xs font-semibold uppercase">Séries</p>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  <button
                    v-for="ser in seriesSorted"
                    :key="ser.id"
                    type="button"
                    class="bg-elevated/30 border-default group focus-visible:ring-primary flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
                    @click="openSeries(ser)"
                  >
                    <div class="bg-primary/10 flex size-12 shrink-0 items-center justify-center rounded-xl">
                      <img
                        v-if="ser.logo"
                        :src="ser.logo"
                        :alt="briefDisplayName(ser)"
                        class="size-9 object-contain"
                        referrerpolicy="no-referrer"
                        decoding="async"
                        loading="lazy"
                      />
                      <UIcon v-else name="i-lucide-layers" class="text-muted size-5" />
                    </div>
                    <div class="min-w-0 flex-1">
                      <p class="text-highlighted truncate text-sm font-medium">
                        {{ briefDisplayName(ser) }}
                      </p>
                      <p class="text-muted text-xs">{{ ser.id }}</p>
                    </div>
                    <UIcon name="i-lucide-chevron-right" class="text-muted size-4 shrink-0" />
                  </button>
                </div>
              </div>
              <div v-if="sets.length" class="space-y-2">
                <p class="text-muted text-xs font-semibold uppercase">Extensions</p>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  <button
                    v-for="s in sets"
                    :key="s.id"
                    type="button"
                    class="bg-elevated/30 border-default group focus-visible:ring-primary flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
                    @click="openSet(s)"
                  >
                    <div class="bg-primary/10 flex size-12 shrink-0 items-center justify-center rounded-xl">
                      <img
                        v-if="s.logo"
                        :src="s.logo"
                        :alt="briefDisplayName(s)"
                        class="size-9 object-contain"
                        referrerpolicy="no-referrer"
                        decoding="async"
                        loading="lazy"
                      />
                      <UIcon v-else name="i-lucide-package" class="text-muted size-5" />
                    </div>
                    <div class="min-w-0 flex-1">
                      <p class="text-highlighted truncate text-sm font-medium">
                        {{ briefDisplayName(s) }}
                      </p>
                      <p class="text-muted text-xs">
                        {{ s.id }} · {{ s.cardCount?.official ?? s.cardCount?.total ?? '?' }} cartes
                      </p>
                    </div>
                    <UIcon name="i-lucide-chevron-right" class="text-muted size-4 shrink-0" />
                  </button>
                </div>
              </div>
              <div
                v-if="!seriesSorted.length && !sets.length"
                class="border-default text-muted rounded-xl border border-dashed p-10 text-center text-sm"
              >
                Aucun résultat pour cette recherche.
              </div>
            </template>
            <template v-else>
              <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                <button
                  v-for="ser in seriesSorted"
                  :key="ser.id"
                  type="button"
                  class="bg-elevated/30 border-default group focus-visible:ring-primary flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
                  @click="openSeries(ser)"
                >
                  <div class="bg-primary/10 flex size-14 shrink-0 items-center justify-center rounded-xl">
                    <img
                      v-if="ser.logo"
                      :src="ser.logo"
                      :alt="briefDisplayName(ser)"
                      class="size-11 object-contain"
                      referrerpolicy="no-referrer"
                      decoding="async"
                      loading="lazy"
                    />
                    <UIcon v-else name="i-lucide-layers" class="text-muted size-6" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <p class="text-highlighted truncate text-sm font-medium">
                      {{ briefDisplayName(ser) }}
                    </p>
                    <p class="text-muted text-xs">{{ ser.id }}</p>
                  </div>
                  <UIcon
                    name="i-lucide-chevron-right"
                    class="text-muted size-4 shrink-0 transition-transform group-hover:translate-x-0.5"
                  />
                </button>
              </div>
              <div
                v-if="!seriesSorted.length"
                class="border-default text-muted rounded-xl border border-dashed p-10 text-center text-sm"
              >
                Aucune série n’a été renvoyée. Cliquez sur « Actualiser ».
              </div>
            </template>
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type {
  CatalogLocale,
  TcgdexSeriesBrief,
  TcgdexSetBrief,
  TcgdexSetDetail,
  TcgdexCardInSetBrief,
} from '~/composables/useCardCatalog'
import type { CollectionCard } from '~/composables/useCollection'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Catalogue Pokémon — ajouter à la collection',
  'Parcourez les séries et extensions TCGdex et ajoutez les cartes à votre collection personnelle GoupixDex.',
)

const toast = useToast()
const { listSeries, getSeries, listSets, getSet } = useCardCatalog()
const { addToCollection, listCollection } = useCollection()

const catalogLocale = ref<CatalogLocale>('fr')
const physicalLanguage = ref<'fr' | 'en' | 'ja'>('fr')
const search = ref('')
const seriesList = ref<TcgdexSeriesBrief[]>([])
const seriesLoading = ref(false)
const sets = ref<TcgdexSetBrief[]>([])
const setsLoading = ref(false)
const activeSeriesId = ref<string | null>(null)
const setsInSeries = ref<TcgdexSetBrief[]>([])
const seriesDetailLoading = ref(false)
const selectedSet = ref<TcgdexSetDetail | null>(null)
const setLoading = ref(false)
const pendingCardId = ref<string | null>(null)
const ownedCards = ref<Map<string, number>>(new Map())

const catalogLocaleItems = [
  { label: 'Français', value: 'fr' },
  { label: 'English', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]
const physicalLanguageItems = [
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

let searchDebounce: ReturnType<typeof setTimeout> | null = null

const seriesSorted = computed<TcgdexSeriesBrief[]>(() => {
  const loc = catalogLocale.value === 'ja' ? 'fr' : catalogLocale.value
  return [...seriesList.value].sort((a, b) =>
    briefDisplayName(a).localeCompare(briefDisplayName(b), loc, { sensitivity: 'base' }),
  )
})

const selectedSetDisplayName = computed(() => (selectedSet.value ? briefDisplayName(selectedSet.value) : ''))

const breadcrumbItems = computed(() => {
  const items: { label: string; icon?: string; onSelect?: () => void }[] = [
    {
      label: 'Catalogue',
      icon: 'i-lucide-library',
      onSelect: () => {
        backToHome()
      },
    },
  ]
  if (activeSeriesId.value) {
    const series = seriesSorted.value.find((s) => s.id === activeSeriesId.value)
    items.push({
      label: series ? briefDisplayName(series) : activeSeriesId.value,
      icon: 'i-lucide-layers',
      onSelect: () => {
        backToSeriesList()
      },
    })
  }
  if (selectedSet.value) {
    items.push({
      label: selectedSetDisplayName.value,
      icon: 'i-lucide-package',
    })
  }
  return items
})

const initialLoading = computed(
  () =>
    (seriesLoading.value || setsLoading.value) &&
    !selectedSet.value &&
    !activeSeriesId.value &&
    !seriesList.value.length,
)

const catalogCardsDisplay = computed(() => {
  const raw = selectedSet.value?.cards as TcgdexCardInSetBrief[] | undefined
  if (!raw?.length) {
    return []
  }
  return raw.map((c) => ({
    id: c.id,
    localId: c.localId,
    displayName: c.display_name?.trim() || c.name,
    thumbUrl: cardThumbSrc(c),
  }))
})

function briefDisplayName(item: { display_name?: string; name?: string; id?: string }): string {
  return item.display_name?.trim() || item.name?.trim() || item.id || ''
}

function cardThumbSrc(c: TcgdexCardInSetBrief): string | undefined {
  if (c.image_low?.trim()) {
    return c.image_low.trim()
  }
  const base = c.image?.trim()
  if (!base) {
    return undefined
  }
  if (base.includes('/low.')) {
    return base
  }
  return `${base.replace(/\/$/, '')}/low.webp`
}

function ownedCount(cardId: string): number {
  return ownedCards.value.get(cardId) ?? 0
}

async function loadBrowse(force = false): Promise<void> {
  if (force) {
    seriesList.value = []
    sets.value = []
  }
  const q = search.value.trim()
  seriesLoading.value = true
  setsLoading.value = !!q
  try {
    const seriesRes = await listSeries({ locale: catalogLocale.value, name: q || undefined })
    seriesList.value = seriesRes.series
    if (q) {
      const setsRes = await listSets({
        locale: catalogLocale.value,
        page: 1,
        perPage: 80,
        name: q,
      })
      sets.value = setsRes.sets
    } else {
      sets.value = []
    }
  } catch (err) {
    toast.add({ title: 'Catalogue', description: apiErrorMessage(err), color: 'error' })
    seriesList.value = []
    sets.value = []
  } finally {
    seriesLoading.value = false
    setsLoading.value = false
  }
}

function scheduleSearch(): void {
  if (searchDebounce) {
    clearTimeout(searchDebounce)
  }
  searchDebounce = setTimeout(() => {
    searchDebounce = null
    activeSeriesId.value = null
    setsInSeries.value = []
    selectedSet.value = null
    void loadBrowse()
  }, 300)
}

watch(catalogLocale, () => {
  selectedSet.value = null
  activeSeriesId.value = null
  setsInSeries.value = []
  void loadBrowse(true)
})

watch(physicalLanguage, () => {
  void refreshOwnedIndex()
})

async function openSeries(s: TcgdexSeriesBrief): Promise<void> {
  seriesDetailLoading.value = true
  activeSeriesId.value = s.id
  selectedSet.value = null
  setsInSeries.value = []
  try {
    const res = await getSeries(catalogLocale.value, s.id)
    setsInSeries.value = res.series.sets ?? []
  } catch (err) {
    toast.add({ title: 'Série', description: apiErrorMessage(err), color: 'error' })
    activeSeriesId.value = null
  } finally {
    seriesDetailLoading.value = false
  }
}

async function openSet(s: TcgdexSetBrief): Promise<void> {
  setLoading.value = true
  selectedSet.value = null
  try {
    const res = await getSet(catalogLocale.value, s.id)
    selectedSet.value = res.set
  } catch (err) {
    toast.add({ title: 'Extension', description: apiErrorMessage(err), color: 'error' })
  } finally {
    setLoading.value = false
  }
}

function backToHome(): void {
  activeSeriesId.value = null
  setsInSeries.value = []
  selectedSet.value = null
}

function backToSeriesList(): void {
  selectedSet.value = null
}

async function onPickCard(c: { id: string; displayName: string }): Promise<void> {
  if (pendingCardId.value) {
    return
  }
  pendingCardId.value = c.id
  try {
    const res = await addToCollection({
      tcgdex_card_id: c.id,
      language: physicalLanguage.value,
      quantity: 1,
    })
    const newQty = res.card.quantity
    ownedCards.value.set(c.id, newQty)
    toast.add({
      title: res.created ? 'Ajoutée à la collection' : `Quantité mise à jour (×${newQty})`,
      description: `${c.displayName} · ${languageLabel(physicalLanguage.value)}`,
      color: 'success',
    })
  } catch (err) {
    toast.add({
      title: 'Ajout impossible',
      description: apiErrorMessage(err),
      color: 'error',
    })
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

async function refreshOwnedIndex(): Promise<void> {
  try {
    const res = await listCollection({ language: physicalLanguage.value })
    const map = new Map<string, number>()
    res.items.forEach((c: CollectionCard) => {
      map.set(c.tcgdex_card_id, c.quantity)
    })
    ownedCards.value = map
  } catch {
    /* ignore — owned badge is best-effort */
  }
}

onMounted(() => {
  void loadBrowse()
  void refreshOwnedIndex()
})
</script>
