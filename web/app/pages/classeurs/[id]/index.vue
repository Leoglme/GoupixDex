<template>
  <UDashboardPanel
    id="binder-detail"
    :ui="{
      body: viewMode === 'pages' && binder ? 'min-w-0 overflow-x-hidden p-0 sm:p-0' : 'min-w-0 overflow-x-hidden',
    }"
  >
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-book-open" class="h-3 w-3 text-(--app-accent)" />
            Classeur
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="loading" class="flex justify-center py-20">
        <UIcon name="i-lucide-loader-2" class="size-10 animate-spin text-(--app-accent)" />
      </div>

      <div v-else-if="binder" class="flex min-h-0 min-w-0 flex-col overflow-x-hidden">
        <div class="app-dashboard-page w-full space-y-4 sm:space-y-5">
          <div class="flex items-center justify-between gap-3">
            <NuxtLink
              to="/classeurs"
              class="inline-flex min-w-0 items-center gap-1 text-sm font-medium text-(--app-accent) underline-offset-4 transition hover:underline"
            >
              <UIcon name="i-lucide-arrow-left" class="size-4 shrink-0" aria-hidden />
              Retour
            </NuxtLink>
            <UButton
              size="sm"
              color="error"
              variant="soft"
              icon="i-lucide-trash-2"
              class="shrink-0"
              @click="confirmDelete"
            >
              Supprimer
            </UButton>
          </div>

          <div class="min-w-0">
            <div class="flex min-w-0 items-center gap-0.5">
              <h1 class="app-page-title min-w-0 truncate">{{ binder.name }}</h1>
              <UButton
                color="neutral"
                variant="ghost"
                icon="i-lucide-pencil"
                size="xs"
                square
                class="shrink-0"
                aria-label="Renommer le classeur"
                @click="openRename"
              />
            </div>
            <p class="text-muted mt-1.5 text-sm tabular-nums">{{ binderMetaLine }}</p>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <GoupixDexCollectionViewTabs v-model="viewMode" :items="viewTabItems" class="shrink-0" />
            <div class="flex shrink-0 items-center gap-2">
              <UButton
                :to="`/classeurs/${id}/editeur`"
                size="sm"
                color="neutral"
                variant="outline"
                icon="i-lucide-palette"
              >
                Personnaliser
              </UButton>
              <UButton
                v-if="viewMode === 'pages'"
                color="neutral"
                variant="ghost"
                size="sm"
                :icon="cleanView ? 'i-lucide-eye' : 'i-lucide-eye-off'"
                square
                :aria-label="cleanView ? 'Afficher les contrôles' : 'Vue propre'"
                :title="cleanView ? 'Afficher les contrôles' : 'Vue propre'"
                @click="cleanView = !cleanView"
              />
            </div>
          </div>
        </div>

        <div v-if="viewMode === 'pages'" class="binder-stage mx-2 mb-3 sm:mx-4 sm:mb-4">
          <GoupixDexBinderPages
            :binder="binder"
            href-base="/collection/"
            :clean-view="cleanView"
            @updated="onBinderUpdated"
          />
        </div>

        <div v-else class="app-dashboard-page space-y-4">
          <div
            v-if="isCompletionBinder"
            class="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7"
          >
            <component
              :is="cell.item ? 'NuxtLink' : 'div'"
              v-for="cell in completionCells"
              :key="cell.key"
              :to="cell.item ? `/collection/${cell.item.collection_card_id}` : undefined"
              class="block"
            >
              <div
                class="card-tile relative aspect-[63/88]"
                :class="[
                  cell.item?.kind === 'wanted' ? 'opacity-75 grayscale-[0.35]' : '',
                  cell.item ? '' : 'ring-1 ring-white/10',
                ]"
              >
                <GoupixDexBinderCardImage
                  v-if="cell.item"
                  :src="cell.item.image_url"
                  :alt="cell.item.card_name"
                  :fallback-src="fallbackArtFor(cell.item)"
                />
                <GoupixDexBinderPokedexPlaceholder v-else-if="cell.placeholder" :placeholder="cell.placeholder" />
                <span v-if="cell.item && cell.item.quantity > 1" class="tile-badge num top-1.5 right-1.5">
                  ×{{ cell.item.quantity }}
                </span>
              </div>
              <p class="mt-1 truncate text-xs" :class="cell.item ? 'font-medium' : 'text-(--app-faint)'">
                {{ cell.item ? cell.item.card_name : cell.placeholder?.pokemonName }}
              </p>
            </component>
          </div>

          <template v-else>
            <p v-if="gridItems.length === 0" class="text-muted py-12 text-center text-sm">
              Aucune carte dans ce classeur. Passe en mode Pages pour en ranger.
            </p>
            <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
              <NuxtLink
                v-for="item in gridItems"
                :key="item.id"
                :to="`/collection/${item.collection_card_id}`"
                class="block"
              >
                <div class="card-tile aspect-[63/88]">
                  <GoupixDexBinderCardImage :src="item.image_url" :alt="item.card_name" />
                  <span v-if="item.quantity > 1" class="tile-badge num top-1.5 right-1.5">×{{ item.quantity }}</span>
                </div>
                <p class="mt-1 truncate text-xs font-medium">{{ item.card_name }}</p>
              </NuxtLink>
            </div>
          </template>
        </div>
      </div>
    </template>
  </UDashboardPanel>

  <GoupixDexDialogModal v-model:open="renameOpen" title="Renommer le classeur">
    <label class="text-muted mb-1.5 block text-xs font-medium" for="binder-rename">Nom</label>
    <input
      id="binder-rename"
      v-model="renameName"
      type="text"
      class="app-input"
      autocomplete="off"
      @keyup.enter="submitRename"
    />

    <template #footer>
      <button type="button" class="dialog-btn-secondary" @click="renameOpen = false">Annuler</button>
      <button type="button" class="dialog-btn-primary" :disabled="renaming || !renameName.trim()" @click="submitRename">
        <UIcon v-if="renaming" name="i-lucide-loader-2" class="size-4 animate-spin" />
        Enregistrer
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
import type { BinderDetail, BinderPocketItem } from '~/types/binders'
import { pokedexPlaceholderAt, pokedexRegionSize } from '~/utils/pokedex/kanto'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const router = useRouter()
const { getBinder, updateBinder, deleteBinder } = useBinders()
const { confirm } = useGoupixConfirm()
const toast = useToast()

const id = computed(() => Number(route.params.id))
const loading = ref(true)
const binder = ref<BinderDetail | null>(null)
const viewMode = computed({
  get: () => (route.query.vue === 'grille' ? 'grille' : 'pages') as 'pages' | 'grille',
  set: (v: 'pages' | 'grille') => {
    const q = { ...route.query }
    if (v === 'grille') {
      q.vue = 'grille'
    } else {
      delete q.vue
    }
    void router.replace({ query: q })
  },
})
const cleanView = ref(false)

const viewTabItems = [
  { label: 'Pages', value: 'pages', icon: 'i-lucide-book-open' },
  { label: 'Grille', value: 'grille', icon: 'i-lucide-grid-2x2' },
]

const gridItems = computed(() => [...(binder.value?.items ?? [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)))

const isCompletionBinder = computed(() => !!binder.value?.pokedex_region)

interface CompletionCell {
  key: string
  item: BinderPocketItem | null
  placeholder: ReturnType<typeof pokedexPlaceholderAt>
}

/**
 * Cellules de la grille en mode complétion : une par numéro de la région (carte
 * rangée ou placeholder), suivies des cartes hors plage (bonus).
 */
const completionCells = computed<CompletionCell[]>(() => {
  const detail = binder.value
  if (!detail || !detail.pokedex_region) {
    return []
  }
  const region = detail.pokedex_region
  const size = pokedexRegionSize(region)
  const byPosition = new Map<number, BinderPocketItem>()
  const extras: BinderPocketItem[] = []
  for (const item of detail.items) {
    const position = item.position
    if (position != null && position >= 0 && position < size && !byPosition.has(position)) {
      byPosition.set(position, item)
    } else {
      extras.push(item)
    }
  }
  const cells: CompletionCell[] = []
  for (let position = 0; position < size; position++) {
    const item = byPosition.get(position) ?? null
    cells.push({
      key: item ? item.id : `ph-${position}`,
      item,
      placeholder: item ? null : pokedexPlaceholderAt(region, position),
    })
  }
  for (const item of extras) {
    cells.push({ key: item.id, item, placeholder: null })
  }
  return cells
})

/**
 * Artwork Pokédex de repli pour une carte rangée sans image (ex. sets récents non
 * encore illustrés sur TCGdex).
 * @param item Carte rangée dans une pochette.
 */
function fallbackArtFor(item: BinderPocketItem): string | null {
  return pokedexPlaceholderAt(binder.value?.pokedex_region ?? null, item.position ?? -1)?.artworkUrl ?? null
}

const binderMetaLine = computed(() => {
  if (!binder.value) {
    return ''
  }
  const grid = binder.value.page_grid.replace('x', '×')
  if (binder.value.pokedex_region) {
    const owned = binder.value.items.filter((item) => item.kind === 'owned').length
    const total = pokedexRegionSize(binder.value.pokedex_region)
    return `${owned} / ${total} possédées · feuille ${grid}`
  }
  const n = binder.value.card_count
  return `${n} carte${n > 1 ? 's' : ''} · feuille ${grid}`
})

const renameOpen = ref(false)
const renameName = ref('')
const renaming = ref(false)

function openRename(): void {
  if (binder.value) {
    renameName.value = binder.value.name
  }
  renameOpen.value = true
}

async function load() {
  loading.value = true
  try {
    binder.value = await getBinder(id.value)
    renameName.value = binder.value.name
  } catch {
    toast.add({ title: 'Classeur introuvable', color: 'error' })
    await router.replace('/classeurs')
  } finally {
    loading.value = false
  }
}

function onBinderUpdated(detail: BinderDetail) {
  binder.value = detail
}

async function submitRename() {
  const name = renameName.value.trim()
  if (!name || !binder.value) return
  renaming.value = true
  try {
    binder.value = await updateBinder(binder.value.id, { name })
    renameOpen.value = false
  } catch {
    toast.add({ title: 'Renommage impossible', color: 'error' })
  } finally {
    renaming.value = false
  }
}

async function confirmDelete() {
  if (!binder.value) return
  const ok = await confirm({
    title: 'Supprimer ce classeur ?',
    description: 'Les cartes restent dans ma collection.',
    confirmLabel: 'Supprimer',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await deleteBinder(binder.value.id)
    await router.push('/classeurs')
  } catch {
    toast.add({ title: 'Suppression impossible', color: 'error' })
  }
}

watch(
  () => route.params.id,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
})
</script>
