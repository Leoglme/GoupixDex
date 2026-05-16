<template>
  <UDashboardPanel id="my-collection-page">
    <template #header>
      <UDashboardNavbar title="Ma collection">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load" />
          <UButton v-if="!isDesktopApp" color="neutral" variant="soft" icon="i-lucide-camera" to="/collection/scan">
            Scanner
          </UButton>
          <UButton color="primary" variant="solid" icon="i-lucide-plus" to="/collection/add">
            Ajouter à ma collection
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-5 px-4 py-6 sm:space-y-6 sm:px-6 sm:py-8">
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <UPageCard
            icon="i-lucide-layers"
            title="Cartes uniques"
            variant="subtle"
            :ui="{ leading: 'p-2.5 rounded-full bg-primary/10 ring ring-inset ring-primary/25 flex-col' }"
          >
            <p class="text-highlighted text-2xl font-semibold">{{ stats.unique_cards }}</p>
            <p class="text-muted text-xs">Cartes distinctes dans le binder</p>
          </UPageCard>
          <UPageCard
            icon="i-lucide-package"
            title="Exemplaires"
            variant="subtle"
            :ui="{ leading: 'p-2.5 rounded-full bg-primary/10 ring ring-inset ring-primary/25 flex-col' }"
          >
            <p class="text-highlighted text-2xl font-semibold">{{ stats.total_quantity }}</p>
            <p class="text-muted text-xs">Quantité totale possédée</p>
          </UPageCard>
          <UPageCard
            icon="i-lucide-bookmark"
            title="Extensions"
            variant="subtle"
            :ui="{ leading: 'p-2.5 rounded-full bg-primary/10 ring ring-inset ring-primary/25 flex-col' }"
          >
            <p class="text-highlighted text-2xl font-semibold">{{ stats.unique_sets }}</p>
            <p class="text-muted text-xs">Sets représentés</p>
          </UPageCard>
          <UPageCard
            icon="i-lucide-tag"
            title="En vente"
            variant="subtle"
            :ui="{ leading: 'p-2.5 rounded-full bg-primary/10 ring ring-inset ring-primary/25 flex-col' }"
          >
            <p class="text-highlighted text-2xl font-semibold">{{ stats.with_article }}</p>
            <p class="text-muted text-xs">Cartes liées à un article</p>
          </UPageCard>
        </div>

        <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4 sm:p-5 space-y-4' }">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div class="flex flex-1 flex-col gap-3 sm:flex-row sm:items-end">
              <UFormField label="Recherche" class="flex-1">
                <UInput v-model="search" icon="i-lucide-search" placeholder="Nom, set, numéro…" class="w-full" />
              </UFormField>
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
            <div class="flex flex-wrap items-center justify-between gap-3 lg:justify-end">
              <span class="text-muted text-xs">{{ filteredItems.length }} carte(s) affichée(s)</span>
              <UTabs
                v-model="viewMode"
                :items="viewItems"
                size="sm"
                color="primary"
                variant="link"
                :ui="{ list: 'gap-1' }"
              />
            </div>
          </div>
        </UCard>

        <div v-if="loading && !payload" class="flex items-center justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
        </div>

        <UCard
          v-else-if="!loading && filteredItems.length === 0"
          class="ring-default/60 shadow-sm ring-1"
          :ui="{ body: 'p-10 text-center space-y-4' }"
        >
          <UIcon name="i-lucide-album" class="text-muted mx-auto size-14" />
          <div class="space-y-1">
            <p class="text-highlighted text-lg font-semibold">Aucune carte dans votre collection</p>
            <p class="text-muted text-sm">Démarrez votre binder en piochant dans le catalogue Pokémon officiel.</p>
          </div>
          <UButton color="primary" icon="i-lucide-plus" to="/collection/add"> Ajouter ma première carte </UButton>
        </UCard>

        <div
          v-else-if="viewMode === 'grid'"
          class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8"
        >
          <UCard
            v-for="card in filteredItems"
            :key="card.id"
            variant="subtle"
            class="group focus-within:ring-primary cursor-pointer overflow-hidden transition-all focus-within:ring-2 hover:shadow-md"
            tabindex="0"
            role="link"
            @click="openCard(card.id)"
            @keydown.enter.prevent="openCard(card.id)"
          >
            <div class="space-y-2 p-2">
              <div class="bg-muted/30 relative aspect-[63/88] w-full overflow-hidden rounded-md">
                <img
                  v-if="card.image_url"
                  :src="card.image_url"
                  :alt="card.display_name"
                  class="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105"
                  referrerpolicy="no-referrer"
                  decoding="async"
                  loading="lazy"
                />
                <div v-else class="flex h-full items-center justify-center">
                  <UIcon name="i-lucide-image-off" class="text-muted size-8" />
                </div>
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
                  v-if="card.article_id"
                  class="bg-success/90 text-inverted absolute top-1.5 right-1.5 rounded-full p-1 backdrop-blur-sm"
                  title="Article créé"
                >
                  <UIcon name="i-lucide-tag" class="size-3" />
                </span>
              </div>
              <p class="text-highlighted truncate text-xs leading-snug font-medium">
                {{ card.display_name }}
              </p>
              <p class="text-muted text-[10px]">{{ card.set_code || card.tcgdex_set_id }} · #{{ card.card_number }}</p>
            </div>
          </UCard>
        </div>

        <UCard v-else class="ring-default/60 overflow-hidden shadow-sm ring-1" :ui="{ body: 'p-0' }">
          <table class="w-full border-separate border-spacing-0 text-sm">
            <thead class="sticky top-0 z-10">
              <tr class="bg-elevated/95 border-default border-y backdrop-blur">
                <th class="text-muted px-3 py-2.5 text-left font-medium first:rounded-tl-lg">Carte</th>
                <th class="text-muted px-3 py-2.5 text-left font-medium">Extension</th>
                <th class="text-muted px-3 py-2.5 text-left font-medium">Langue</th>
                <th class="text-muted px-3 py-2.5 text-right font-medium">Qté</th>
                <th class="text-muted px-3 py-2.5 text-left font-medium">Statut</th>
                <th class="w-12 last:rounded-tr-lg" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredItems"
                :key="row.id"
                class="border-default hover:bg-elevated/40 cursor-pointer border-b transition-colors last:border-b-0"
                @click="openCard(row.id)"
              >
                <td class="px-3 py-2.5">
                  <div class="flex items-center gap-3">
                    <div class="bg-muted/30 size-12 shrink-0 overflow-hidden rounded-md">
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
                    <p class="text-highlighted truncate text-sm font-medium">{{ row.display_name }}</p>
                  </div>
                </td>
                <td class="text-muted px-3 py-2.5 text-xs">
                  {{ row.set_name || row.tcgdex_set_id }} · #{{ row.card_number }}
                </td>
                <td class="px-3 py-2.5">
                  <UBadge color="neutral" variant="subtle" size="sm">
                    {{ languageLabel(row.language) }}
                  </UBadge>
                </td>
                <td class="px-3 py-2.5 text-right tabular-nums">×{{ row.quantity }}</td>
                <td class="px-3 py-2.5">
                  <UBadge v-if="row.article_id" color="success" variant="subtle" size="sm" icon="i-lucide-tag">
                    Article #{{ row.article_id }}
                  </UBadge>
                  <span v-else class="text-muted text-xs">—</span>
                </td>
                <td class="px-2 py-2.5 text-right">
                  <UIcon name="i-lucide-chevron-right" class="text-muted size-4" />
                </td>
              </tr>
            </tbody>
          </table>
        </UCard>
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
  { label: 'Sans article (en stock)', value: 'without_article' },
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
    }
  )
})

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

function openCard(id: number): void {
  void navigateTo(`/collection/${id}`)
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

onMounted(() => {
  void load()
  void connectScanStream()
})

onBeforeUnmount(() => {
  disconnectScanStream()
})
</script>
