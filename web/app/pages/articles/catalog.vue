<script setup lang="ts">
import type {
  CatalogLocale,
  TcgdexSeriesBrief,
  TcgdexSetBrief,
  TcgdexSetDetail
} from '~/composables/useCardCatalog'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Catalogue Pokémon',
  'Parcourez les séries et extensions (TCGdex), choisissez une carte et préremplissez une fiche article avec les prix PokéWallet.'
)

type FormExpose = {
  applyCatalogPrefill: (p: import('~/composables/useCardCatalog').CatalogCardPreviewResponse) => Promise<void>
  buildCreateFormData: () => FormData
}

const locale = ref<CatalogLocale>('fr')
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
const previewLoading = ref(false)
const formRef = ref<FormExpose | null>(null)
const submitting = ref(false)
const toast = useToast()
const { listSeries, getSeries, listSets, getSet, previewCard } = useCardCatalog()
const { createArticle, publishArticleToVinted } = useArticles()
const { isDesktopApp } = useDesktopRuntime()

let searchDebounce: ReturnType<typeof setTimeout> | null = null

const seriesSorted = computed(() => {
  const loc = locale.value === 'ja' ? 'ja' : locale.value === 'fr' ? 'fr' : 'en'
  return [...seriesList.value].sort((a, b) =>
    a.name.localeCompare(b.name, loc, { sensitivity: 'base' })
  )
})

const browseSubtitle = computed(() => {
  if (selectedSet.value) {
    return `${cardCountInSet.value} · cliquez sur une carte pour préremplir le formulaire`
  }
  if (activeSeriesId.value) {
    const n = setsInSeries.value.length
    if (n === 0) {
      return 'Aucune extension dans cette série'
    }
    if (n === 1) {
      return '1 extension · ouvrez-la pour voir les cartes'
    }
    return `${n} extensions · ouvrez une ligne pour voir les cartes`
  }
  const q = search.value.trim()
  if (q) {
    const ns = seriesList.value.length
    const ne = sets.value.length
    const parts: string[] = []
    if (ns) {
      parts.push(ns === 1 ? '1 série' : `${ns} séries`)
    }
    if (ne) {
      parts.push(ne === 1 ? '1 extension' : `${ne} extensions`)
    }
    if (!parts.length) {
      return 'Aucun résultat pour cette recherche'
    }
    return `${parts.join(' · ')} · ouvrez une série ou une extension`
  }
  const n = seriesList.value.length
  if (n === 0) {
    return 'Aucune série'
  }
  if (n === 1) {
    return '1 série · ouvrez-la pour voir les extensions'
  }
  return `${n} séries · ouvrez une ligne pour voir les extensions`
})

const cardCountInSet = computed(() => {
  const n = selectedSet.value?.cards?.length ?? 0
  if (n === 0) {
    return 'Aucune carte'
  }
  if (n === 1) {
    return '1 carte'
  }
  return `${n} cartes`
})

const browseTitle = computed(() => {
  if (selectedSet.value) {
    return 'Cartes du set'
  }
  if (activeSeriesId.value) {
    return 'Extensions dans la série'
  }
  if (search.value.trim()) {
    return 'Séries et extensions'
  }
  return 'Séries'
})

const activeSeriesName = computed(() => {
  const id = activeSeriesId.value
  if (!id) {
    return ''
  }
  return seriesSorted.value.find(s => s.id === id)?.name ?? id
})

async function loadBrowse() {
  const q = search.value.trim()
  seriesLoading.value = true
  setsLoading.value = !!q
  try {
    const seriesRes = await listSeries({
      locale: locale.value,
      name: q || undefined
    })
    seriesList.value = seriesRes.series
    if (q) {
      const setsRes = await listSets({
        locale: locale.value,
        page: 1,
        perPage: 80,
        name: q
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

function scheduleSearch() {
  if (searchDebounce) {
    clearTimeout(searchDebounce)
  }
  searchDebounce = setTimeout(() => {
    searchDebounce = null
    activeSeriesId.value = null
    setsInSeries.value = []
    selectedSet.value = null
    void loadBrowse()
  }, 350)
}

watch(locale, () => {
  selectedSet.value = null
  activeSeriesId.value = null
  setsInSeries.value = []
  void loadBrowse()
})

onMounted(() => {
  void loadBrowse()
})

async function openSeries(s: TcgdexSeriesBrief) {
  seriesDetailLoading.value = true
  activeSeriesId.value = s.id
  selectedSet.value = null
  setsInSeries.value = []
  try {
    const res = await getSeries(locale.value, s.id)
    setsInSeries.value = res.series.sets ?? []
  } catch (err) {
    toast.add({ title: 'Série', description: apiErrorMessage(err), color: 'error' })
    activeSeriesId.value = null
  } finally {
    seriesDetailLoading.value = false
  }
}

async function openSet(s: TcgdexSetBrief) {
  setLoading.value = true
  selectedSet.value = null
  try {
    const res = await getSet(locale.value, s.id)
    selectedSet.value = res.set
  } catch (err) {
    toast.add({ title: 'Extension', description: apiErrorMessage(err), color: 'error' })
  } finally {
    setLoading.value = false
  }
}

function backToSeriesList() {
  activeSeriesId.value = null
  setsInSeries.value = []
  selectedSet.value = null
}

function backToSets() {
  selectedSet.value = null
}

/** Voir https://tcgdex.dev/assets — vignettes ``low.webp``. */
function cardThumbSrc(c: { image_low?: string, image?: string }): string | undefined {
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

const catalogCardsDisplay = computed(() => {
  const raw = selectedSet.value?.cards
  if (!raw?.length) {
    return []
  }
  return raw.map(c => ({ ...c, thumbUrl: cardThumbSrc(c) }))
})

async function pickCard(cardId: string) {
  const abbrev = selectedSet.value?.abbreviation?.official
  previewLoading.value = true
  try {
    const data = await previewCard(cardId, abbrev ?? null, locale.value)
    await formRef.value?.applyCatalogPrefill(data)
    toast.add({
      title: 'Carte chargée',
      description: 'Vérifiez le prix, le titre et les photos avant d’enregistrer.',
      color: 'success'
    })
  } catch (err) {
    toast.add({ title: 'Aperçu impossible', description: apiErrorMessage(err), color: 'error' })
  } finally {
    previewLoading.value = false
  }
}

function onPickCard(cardId: string) {
  if (previewLoading.value) {
    return
  }
  void pickCard(cardId)
}

async function onSubmitCreate(fd: FormData) {
  if (!isDesktopApp.value) {
    fd.set('publish_to_vinted', 'false')
  }
  submitting.value = true
  try {
    const { article, vinted } = await createArticle(fd)
    if (isDesktopApp.value && vinted.desktop_local && vinted.stream_path) {
      try {
        await publishArticleToVinted(article.id)
      } catch (e) {
        toast.add({ title: 'Worker Vinted', description: apiErrorMessage(e), color: 'error' })
        await navigateTo('/articles/stock')
        return
      }
      await navigateTo({ path: '/articles/listing-logs', query: { article: String(article.id), progress: 'local' } })
      return
    }
    toast.add({ title: 'Article créé', color: 'success' })
    await navigateTo('/articles/stock')
  } catch (err) {
    toast.add({ title: 'Création impossible', description: apiErrorMessage(err), color: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="articles-catalog-page">
    <template #header>
      <UDashboardNavbar title="Catalogue Pokémon">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            to="/articles/create"
            color="neutral"
            variant="ghost"
            icon="i-lucide-scan-line"
          >
            Scan
          </UButton>
          <UButton
            to="/articles/stock"
            color="neutral"
            variant="ghost"
            icon="i-lucide-package"
          >
            Stock
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full max-w-7xl mx-auto px-4 sm:px-8 py-6 sm:py-10 space-y-8">
        <div
          class="relative overflow-hidden rounded-2xl border border-default bg-gradient-to-br from-primary/10 via-elevated/50 to-primary/5 p-8 sm:p-10"
        >
          <div class="absolute -right-16 -top-16 size-64 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
          <div class="absolute -bottom-20 -left-12 size-56 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
          <div class="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="space-y-3 max-w-2xl">
              <p class="text-sm font-medium text-primary">
                Données TCGdex · prix PokéWallet
              </p>
              <h1 class="text-2xl sm:text-3xl font-semibold text-highlighted tracking-tight">
                Ajouter une carte depuis le catalogue officiel
              </h1>
              <p class="text-muted text-base leading-relaxed">
                Parcourez d’abord les <strong class="font-medium text-highlighted">séries</strong> (Bloc, Écarlate et Violet…),
                ouvrez une extension puis une carte : le formulaire se remplit
                (titre, description, code set, numéro, image HD). La recherche filtre séries et extensions.
                Les tarifs Cardmarket / TCGPlayer ne sont demandés à PokéWallet qu’au moment du clic.
              </p>
            </div>
            <div class="flex shrink-0 gap-3 lg:flex-col lg:items-end">
              <div
                class="flex items-center gap-2 rounded-xl bg-elevated/80 border border-default px-4 py-3 backdrop-blur-sm"
              >
                <UIcon name="i-lucide-library" class="size-8 text-primary" />
                <UIcon name="i-lucide-sparkles" class="size-8 text-highlighted" />
              </div>
            </div>
          </div>
        </div>

        <UAlert
          color="info"
          variant="subtle"
          icon="i-lucide-lightbulb"
          title="Comment utiliser cette page ?"
          description="Choisissez la langue d’affichage TCGdex (français, anglais ou japonais), ouvrez une série puis une extension, ou utilisez la recherche. Cliquez sur une carte pour préremplir le formulaire, vérifiez le prix puis enregistrez — comme après un scan."
        />

        <UCard
          class="ring-1 ring-default/60 shadow-sm"
          :ui="{ body: 'sm:p-8 p-6' }"
        >
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3 px-1">
              <div class="min-w-0 space-y-1">
                <p class="text-sm text-muted">
                  Parcours guidé
                </p>
                <p class="text-lg font-semibold text-highlighted">
                  Catalogue et fiche article
                </p>
                <p v-if="selectedSet" class="text-sm text-muted">
                  Extension sélectionnée : <span class="font-medium text-highlighted">{{ selectedSet.name }}</span>
                </p>
                <p v-else-if="activeSeriesId" class="text-sm text-muted">
                  Série : <span class="font-medium text-highlighted">{{ activeSeriesName }}</span>
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2 shrink-0">
                <UBadge color="neutral" variant="subtle" size="md">
                  {{ locale === 'fr' ? 'TCGdex FR' : locale === 'ja' ? 'TCGdex JA' : 'TCGdex EN' }}
                </UBadge>
                <UBadge
                  v-if="selectedSet?.abbreviation?.official"
                  color="primary"
                  variant="subtle"
                  size="md"
                >
                  PokéWallet {{ selectedSet.abbreviation.official }}
                </UBadge>
              </div>
            </div>
          </template>

          <div class="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between mb-8">
            <div class="flex flex-wrap items-end gap-3">
              <UFormField label="Langue catalogue" class="w-56 sm:w-60">
                <USelect
                  v-model="locale"
                  :items="[
                    { label: 'Français', value: 'fr' },
                    { label: 'English', value: 'en' },
                    { label: '日本語', value: 'ja' }
                  ]"
                  value-key="value"
                  label-key="label"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Recherche" class="min-w-[12rem] max-w-md flex-1">
                <UInput
                  v-model="search"
                  placeholder="Série ou extension (ex. Écarlate, 151, sv04…)"
                  icon="i-lucide-search"
                  class="w-full"
                  @update:model-value="scheduleSearch"
                />
              </UFormField>
            </div>
            <UButton
              :loading="seriesLoading || setsLoading"
              color="neutral"
              variant="soft"
              icon="i-lucide-refresh-cw"
              @click="loadBrowse"
            >
              Actualiser la liste
            </UButton>
          </div>

          <div class="grid gap-8 lg:grid-cols-2 lg:gap-10 lg:items-start">
            <div class="space-y-4 min-w-0">
              <div class="flex items-center gap-3 border-b border-default pb-3">
                <div class="flex size-12 items-center justify-center rounded-xl bg-primary/15">
                  <UIcon name="i-lucide-library" class="size-7 text-primary" />
                </div>
                <div class="min-w-0">
                  <h2 class="text-lg font-semibold text-highlighted">
                    {{ browseTitle }}
                  </h2>
                  <p class="text-sm text-muted">
                    {{ browseSubtitle }}
                  </p>
                </div>
              </div>

              <div
                v-if="(seriesLoading || setsLoading) && !selectedSet && !activeSeriesId"
                class="space-y-3 py-2"
              >
                <p class="text-sm text-muted">
                  Chargement du catalogue…
                </p>
                <UProgress animation="carousel" />
              </div>

              <div v-else-if="seriesDetailLoading && !selectedSet" class="space-y-3 py-2">
                <p class="text-sm text-muted">
                  Chargement des extensions…
                </p>
                <UProgress animation="carousel" />
              </div>

              <div v-else-if="setLoading" class="space-y-3 py-2">
                <p class="text-sm text-muted">
                  Chargement des cartes…
                </p>
                <UProgress animation="carousel" />
              </div>

              <div v-else-if="selectedSet" class="space-y-4">
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  icon="i-lucide-arrow-left"
                  @click="backToSets"
                >
                  {{ activeSeriesId ? 'Retour aux extensions' : (search.trim() ? 'Retour aux résultats' : 'Retour aux séries') }}
                </UButton>

                <div
                  class="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[min(62vh,560px)] overflow-y-auto pr-1"
                >
                  <UCard
                    v-for="c in catalogCardsDisplay"
                    :key="c.id"
                    variant="subtle"
                    class="overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                    :class="{ 'opacity-60 pointer-events-none': previewLoading }"
                    tabindex="0"
                    role="button"
                    @click="onPickCard(c.id)"
                    @keydown.enter.prevent="onPickCard(c.id)"
                  >
                    <div class="p-2 space-y-2">
                      <div class="aspect-[63/88] w-full overflow-hidden rounded-lg bg-muted/30">
                        <img
                          v-if="c.thumbUrl"
                          :src="c.thumbUrl"
                          :alt="c.name"
                          class="h-full w-full object-contain"
                          referrerpolicy="no-referrer"
                          decoding="async"
                        >
                      </div>
                      <p class="truncate text-xs font-medium text-highlighted leading-snug">
                        {{ c.name }}
                      </p>
                      <p class="text-[10px] text-muted">
                        #{{ c.localId }}
                      </p>
                    </div>
                  </UCard>
                </div>
              </div>

              <div v-else-if="activeSeriesId" class="space-y-4">
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  icon="i-lucide-arrow-left"
                  @click="backToSeriesList"
                >
                  Retour aux séries
                </UButton>

                <div
                  v-if="!setsInSeries.length && !seriesDetailLoading"
                  class="rounded-xl border border-dashed border-default px-4 py-10 text-center text-sm text-muted"
                >
                  Aucune extension dans cette série.
                </div>

                <div v-else class="space-y-3 max-h-[min(62vh,560px)] overflow-y-auto pr-1">
                  <UCard
                    v-for="s in setsInSeries"
                    :key="s.id"
                    variant="subtle"
                    class="overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                    tabindex="0"
                    role="button"
                    @click="openSet(s)"
                    @keydown.enter.prevent="openSet(s)"
                  >
                    <div class="flex gap-4 min-w-0 items-center p-4">
                      <div
                        class="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10"
                      >
                        <img
                          v-if="s.logo"
                          :src="s.logo"
                          :alt="s.name"
                          class="size-10 object-contain"
                          referrerpolicy="no-referrer"
                          decoding="async"
                        >
                        <UIcon
                          v-else
                          name="i-lucide-package"
                          class="size-6 text-muted"
                        />
                      </div>
                      <div class="min-w-0 flex-1 space-y-1">
                        <p class="font-medium text-highlighted leading-snug">
                          {{ s.name }}
                        </p>
                        <p class="text-sm text-muted leading-relaxed">
                          {{ s.id }} · {{ s.cardCount?.official ?? s.cardCount?.total ?? '?' }} cartes
                        </p>
                      </div>
                      <UIcon name="i-lucide-chevron-right" class="size-5 shrink-0 text-muted" />
                    </div>
                  </UCard>
                </div>
              </div>

              <div v-else class="space-y-6">
                <div
                  v-if="!search.trim() && !seriesSorted.length && !seriesLoading"
                  class="rounded-xl border border-dashed border-default px-4 py-10 text-center text-sm text-muted"
                >
                  Aucune série n’a été renvoyée par TCGdex. Vérifiez la connexion ou cliquez sur « Actualiser la liste ».
                </div>

                <div
                  v-else-if="search.trim() && !seriesSorted.length && !sets.length && !seriesLoading && !setsLoading"
                  class="rounded-xl border border-dashed border-default px-4 py-10 text-center text-sm text-muted"
                >
                  Aucune série ni extension ne correspond à votre recherche. Essayez un autre mot-clé.
                </div>

                <template v-if="!search.trim() && seriesSorted.length">
                  <div class="space-y-3 max-h-[min(62vh,560px)] overflow-y-auto pr-1">
                    <UCard
                      v-for="ser in seriesSorted"
                      :key="ser.id"
                      variant="subtle"
                      class="overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                      tabindex="0"
                      role="button"
                      @click="openSeries(ser)"
                      @keydown.enter.prevent="openSeries(ser)"
                    >
                      <div class="flex gap-4 min-w-0 items-center p-4">
                        <div
                          class="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10"
                        >
                          <img
                            v-if="ser.logo"
                            :src="ser.logo"
                            :alt="ser.name"
                            class="size-10 object-contain"
                            referrerpolicy="no-referrer"
                            decoding="async"
                          >
                          <UIcon
                            v-else
                            name="i-lucide-layers"
                            class="size-6 text-muted"
                          />
                        </div>
                        <div class="min-w-0 flex-1 space-y-1">
                          <p class="font-medium text-highlighted leading-snug">
                            {{ ser.name }}
                          </p>
                          <p class="text-sm text-muted leading-relaxed">
                            {{ ser.id }}
                          </p>
                        </div>
                        <UIcon name="i-lucide-chevron-right" class="size-5 shrink-0 text-muted" />
                      </div>
                    </UCard>
                  </div>
                </template>

                <template v-else-if="search.trim()">
                  <div
                    v-if="seriesSorted.length"
                    class="space-y-2 max-h-[min(30vh,280px)] overflow-y-auto pr-1"
                  >
                    <p class="text-xs font-semibold uppercase tracking-wide text-muted">
                      Séries
                    </p>
                    <div class="space-y-2">
                      <UCard
                        v-for="ser in seriesSorted"
                        :key="ser.id"
                        variant="subtle"
                        class="overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                        tabindex="0"
                        role="button"
                        @click="openSeries(ser)"
                        @keydown.enter.prevent="openSeries(ser)"
                      >
                        <div class="flex gap-3 min-w-0 items-center p-3">
                          <div
                            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10"
                          >
                            <img
                              v-if="ser.logo"
                              :src="ser.logo"
                              :alt="ser.name"
                              class="size-8 object-contain"
                              referrerpolicy="no-referrer"
                              decoding="async"
                            >
                            <UIcon
                              v-else
                              name="i-lucide-layers"
                              class="size-5 text-muted"
                            />
                          </div>
                          <div class="min-w-0 flex-1">
                            <p class="text-sm font-medium text-highlighted leading-snug truncate">
                              {{ ser.name }}
                            </p>
                            <p class="text-xs text-muted">
                              {{ ser.id }}
                            </p>
                          </div>
                          <UIcon name="i-lucide-chevron-right" class="size-4 shrink-0 text-muted" />
                        </div>
                      </UCard>
                    </div>
                  </div>

                  <div
                    v-if="sets.length"
                    class="space-y-2 max-h-[min(42vh,400px)] overflow-y-auto pr-1"
                  >
                    <p class="text-xs font-semibold uppercase tracking-wide text-muted">
                      Extensions
                    </p>
                    <div class="space-y-2">
                      <UCard
                        v-for="s in sets"
                        :key="s.id"
                        variant="subtle"
                        class="overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                        tabindex="0"
                        role="button"
                        @click="openSet(s)"
                        @keydown.enter.prevent="openSet(s)"
                      >
                        <div class="flex gap-3 min-w-0 items-center p-3">
                          <div
                            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10"
                          >
                            <img
                              v-if="s.logo"
                              :src="s.logo"
                              :alt="s.name"
                              class="size-8 object-contain"
                              referrerpolicy="no-referrer"
                              decoding="async"
                            >
                            <UIcon
                              v-else
                              name="i-lucide-package"
                              class="size-5 text-muted"
                            />
                          </div>
                          <div class="min-w-0 flex-1">
                            <p class="text-sm font-medium text-highlighted leading-snug truncate">
                              {{ s.name }}
                            </p>
                            <p class="text-xs text-muted">
                              {{ s.id }} · {{ s.cardCount?.official ?? s.cardCount?.total ?? '?' }} cartes
                            </p>
                          </div>
                          <UIcon name="i-lucide-chevron-right" class="size-4 shrink-0 text-muted" />
                        </div>
                      </UCard>
                    </div>
                  </div>
                </template>
              </div>
            </div>

            <div class="space-y-4 min-w-0">
              <div class="flex items-center gap-3 border-b border-default pb-3">
                <div class="flex size-12 items-center justify-center rounded-xl bg-neutral-500/15">
                  <UIcon name="i-lucide-file-pen-line" class="size-7 text-highlighted" />
                </div>
                <div>
                  <h2 class="text-lg font-semibold text-highlighted">
                    Fiche article
                  </h2>
                  <p class="text-sm text-muted">
                    Même formulaire que « Nouvel article » : photos, prix, Vinted / eBay si disponibles
                  </p>
                </div>
              </div>

              <UCard variant="subtle" class="ring-1 ring-default/40">
                <ArticleForm
                  ref="formRef"
                  mode="create"
                  :loading="submitting"
                  @submit-create="onSubmitCreate"
                />
              </UCard>
            </div>
          </div>
        </UCard>

        <p class="text-center text-xs text-muted">
          Données cartes et visuels :
          <a
            href="https://tcgdex.dev/"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary underline underline-offset-2"
          >TCGdex</a>
          · Images :
          <a
            href="https://tcgdex.dev/assets"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary underline underline-offset-2"
          >règles des assets</a>
        </p>
      </div>
    </template>
  </UDashboardPanel>
</template>
