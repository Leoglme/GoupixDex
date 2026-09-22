<template>
  <UDashboardPanel id="my-collection-page">
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
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full">
        <GoupixDexPageHeader
          title="Ma collection"
          description="Votre binder personnel : cartes possédées, extensions et mises en vente."
        >
          <template #actions>
            <UButton color="primary" variant="solid" icon="i-lucide-plus" size="md" to="/collection/add">
              Ajouter à ma collection
            </UButton>
            <UButton
              v-if="!isDesktopApp"
              color="neutral"
              variant="outline"
              icon="i-lucide-scan-line"
              size="md"
              to="/collection/scan"
            >
              Scanner une carte
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <GoupixDexCollectionSectionTabs active="cartes" />

        <div class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
          <GoupixDexStatsCard
            title="Valeur estimée"
            :value="estimatedValueLabel"
            :description="`Prix marché Cardmarket · ${stats.priced_cards} carte(s) cotée(s)`"
            icon="i-lucide-euro"
          />
          <GoupixDexStatsCard
            title="Cartes uniques"
            :value="stats.unique_cards"
            description="Cartes distinctes dans le binder"
            icon="i-lucide-layers"
          />
          <GoupixDexStatsCard
            title="Exemplaires"
            :value="stats.total_quantity"
            description="Quantité totale possédée"
            icon="i-lucide-package"
          />
          <GoupixDexStatsCard
            title="Extensions"
            :value="stats.unique_sets"
            description="Sets représentés"
            icon="i-lucide-bookmark"
          />
          <GoupixDexStatsCard
            title="En vente"
            :value="stats.with_article"
            description="Cartes liées à un article"
            icon="i-lucide-tag"
          />
        </div>

        <UCard :ui="{ body: 'p-4 sm:p-5' }">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between lg:gap-4">
            <UFormField label="Recherche" class="min-w-0 flex-1">
              <UInput v-model="search" icon="i-lucide-search" placeholder="Nom, set, numéro…" class="w-full" />
            </UFormField>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:gap-3 lg:shrink-0">
              <UFormField label="Langue" class="w-full sm:w-48">
                <USelect
                  v-model="languageFilter"
                  :items="languageItems"
                  value-key="value"
                  label-key="label"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Statut" class="w-full sm:w-56">
                <USelect
                  v-model="listedFilter"
                  :items="listedItems"
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
            {{ filteredItems.length }} carte(s) affichée(s)
          </span>
        </div>

        <div v-if="loading && !payload" class="flex items-center justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
        </div>

        <UCard v-else-if="!loading && filteredItems.length === 0" :ui="{ body: 'p-10 text-center space-y-4' }">
          <UIcon name="i-lucide-album" class="text-muted mx-auto size-14" />
          <div class="space-y-1">
            <p class="text-highlighted text-lg font-semibold">Aucune carte dans votre collection</p>
            <p class="text-muted text-sm">Démarrez votre binder en piochant dans le catalogue Pokémon officiel.</p>
          </div>
          <UButton color="primary" icon="i-lucide-plus" to="/collection/add"> Ajouter ma première carte </UButton>
        </UCard>

        <div
          v-else-if="viewMode === 'grid'"
          class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6"
        >
          <button
            v-for="card in filteredItems"
            :key="card.id"
            type="button"
            class="border-default bg-elevated/30 group focus-visible:ring-primary block overflow-hidden rounded-xl border text-left transition-all hover:border-(--app-accent) hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
            @click="openCardFromClick(card.id, $event)"
            @keydown.enter.prevent="openCard(card.id)"
          >
            <div class="bg-muted/20 relative aspect-[63/88] w-full overflow-hidden">
              <GoupixDexCardImage
                :image-url="card.image_url"
                :tcgdex-card-id="card.tcgdex_card_id"
                :alt="card.display_name"
                img-class="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105"
              />
              <span
                class="bg-primary/90 text-inverted absolute top-1.5 left-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase backdrop-blur-sm"
              >
                {{ languageLabel(card.language) }}
              </span>
              <span
                v-if="card.quantity > 1"
                class="bg-elevated/95 text-highlighted absolute right-1.5 bottom-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
              >
                ×{{ card.quantity }}
              </span>
              <span
                v-if="card.market_price_eur != null"
                class="bg-elevated/95 text-highlighted absolute bottom-1.5 left-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
              >
                {{ eur.format(card.market_price_eur) }}
              </span>
              <span
                v-if="card.article_id"
                class="bg-success/90 text-inverted absolute top-1.5 right-1.5 rounded-full p-1 backdrop-blur-sm"
                title="Article créé"
              >
                <UIcon name="i-lucide-tag" class="size-3" />
              </span>
            </div>
            <div class="space-y-0.5 p-2">
              <p class="text-highlighted truncate text-xs leading-snug font-medium">
                {{ card.display_name }}
              </p>
              <p class="text-muted truncate text-[10px]">
                {{ card.set_code || card.tcgdex_set_id }} · #{{ card.card_number }}
              </p>
            </div>
          </button>
        </div>

        <div v-else class="app-card overflow-hidden">
          <GoupixDexBaseTable min-width="640px">
            <template #head>
              <GoupixDexBaseTableTh class="goupix-card-table__name-col">Carte</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh>Extension</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh>Langue</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="right">Qté</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="right">Prix marché</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh>Statut</GoupixDexBaseTableTh>
              <GoupixDexBaseTableTh align="center" sr-only>Ouvrir</GoupixDexBaseTableTh>
            </template>

            <GoupixDexBaseTableTr
              v-for="row in filteredItems"
              :key="row.id"
              class="cursor-pointer"
              @click="openCard(row.id)"
            >
              <GoupixDexBaseTableTd class="goupix-card-table__lead">
                <div class="flex min-w-0 items-center gap-3">
                  <div class="size-11 shrink-0 overflow-hidden rounded-md bg-[var(--app-surface-2)]">
                    <img
                      v-if="row.image_url"
                      :src="row.image_url"
                      :alt="row.display_name"
                      class="h-full w-full object-contain"
                      referrerpolicy="no-referrer"
                      decoding="async"
                      loading="lazy"
                    />
                  </div>
                  <p class="min-w-0 truncate text-sm font-medium text-[var(--app-ink)]">{{ row.display_name }}</p>
                </div>
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd label="Extension" class="text-xs text-[var(--app-ink-soft)]">
                {{ row.set_name || row.tcgdex_set_id }} · #{{ row.card_number }}
              </GoupixDexBaseTableTd>
              <GoupixDexBaseTableTd label="Langue">
                <UBadge color="neutral" variant="subtle" size="sm">{{ languageLabel(row.language) }}</UBadge>
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
              <GoupixDexBaseTableTd label="Statut">
                <UBadge v-if="row.article_id" color="success" variant="subtle" size="sm" icon="i-lucide-tag">
                  Article #{{ row.article_id }}
                </UBadge>
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
import type { CollectionCard, CollectionListResponse, CollectionStats } from '~/composables/useCollection'
import type { ScanEvent } from '~/composables/useScanStream'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Ma collection',
  'Gérez votre binder Pokémon : ajoutez des cartes depuis le catalogue officiel et préparez-les à la vente.',
)

const { listCollection } = useCollection()
const { isDesktopApp } = useDesktopRuntime()
const { openCard, openCardFromClick } = useOpenCardDrawer()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const payload = ref<CollectionListResponse | null>(null)
const loading = ref(false)
const search = ref('')
const languageFilter = ref<string>('any')
const listedFilter = ref<'any' | 'with_article' | 'without_article'>('any')
const viewMode = ref<'grid' | 'list'>('grid')

const languageItems = [
  { label: 'Toutes les langues', value: 'any' },
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const listedItems = [
  { label: 'Toutes les cartes', value: 'any' },
  { label: 'Pas en vente', value: 'without_article' },
  { label: 'Avec article (en vente)', value: 'with_article' },
]

const viewItems = [
  { label: 'Grille', value: 'grid', icon: 'i-lucide-grid-2x2' },
  { label: 'Liste', value: 'list', icon: 'i-lucide-list' },
]

const stats = computed<CollectionStats>(() => {
  return (
    payload.value?.stats ?? {
      unique_cards: 0,
      total_quantity: 0,
      unique_sets: 0,
      languages: {},
      with_article: 0,
      estimated_value_eur: 0,
      priced_cards: 0,
    }
  )
})

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const estimatedValueLabel = computed<string>(() => eur.format(stats.value.estimated_value_eur))

const filteredItems = computed<CollectionCard[]>(() => {
  const items = payload.value?.items ?? []
  const q = search.value.trim().toLowerCase()
  return items.filter((card) => {
    if (languageFilter.value !== 'any' && card.language !== languageFilter.value) {
      return false
    }
    if (listedFilter.value === 'with_article' && !card.article_id) {
      return false
    }
    if (listedFilter.value === 'without_article' && card.article_id) {
      return false
    }
    if (!q) {
      return true
    }
    return (
      card.display_name.toLowerCase().includes(q) ||
      (card.set_name?.toLowerCase().includes(q) ?? false) ||
      (card.set_code?.toLowerCase().includes(q) ?? false) ||
      card.card_number.toLowerCase().includes(q)
    )
  })
})

function languageLabel(code: string): string {
  switch (code) {
    case 'fr':
      return 'FR'
    case 'en':
      return 'EN'
    case 'ja':
      return 'JP'
    default:
      return code.toUpperCase()
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    payload.value = await listCollection()
  } catch (e) {
    toast.add({ title: 'Ma collection', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

/**
 * Insert (or refresh) a card freshly added via scan-stream into the local list
 * without re-hitting `/collection`. We dedupe on `id` so multiple events for
 * the same card (e.g. quantity bumps) just patch the existing row in place.
 */
function applyLiveScanCard(card: CollectionCard): void {
  const current = payload.value
  if (!current) {
    void load()
    return
  }
  const ix = current.items.findIndex((row) => row.id === card.id)
  const nextItems = current.items.slice()
  if (ix === -1) {
    nextItems.unshift(card)
  } else {
    nextItems[ix] = card
  }
  payload.value = { ...current, items: nextItems }
}

const { events: scanEvents, connect: connectScanStream, disconnect: disconnectScanStream } = useScanStream()

watch(
  scanEvents,
  (list: ScanEvent[]) => {
    for (const ev of list) {
      if (ev.status === 'added' && ev.collection_card) {
        applyLiveScanCard(ev.collection_card)
      }
    }
  },
  { deep: true },
)

watch(
  () => drawerStack.cardMutationCounter.value,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
  void connectScanStream()
})

onBeforeUnmount(() => {
  disconnectScanStream()
})
</script>
