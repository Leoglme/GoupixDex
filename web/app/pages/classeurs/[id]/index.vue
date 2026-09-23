<template>
  <UDashboardPanel id="binder-detail" :ui="{ body: 'min-w-0 overflow-x-hidden' }">
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
            <GoupixDexCollectionViewTabs
              v-model="viewMode"
              :items="viewTabItems"
              stretch-mobile
              class="max-sm:w-full"
            />
            <div v-if="viewMode !== 'valeurs'" class="flex shrink-0 items-center gap-2">
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
                color="neutral"
                :variant="previewComplete ? 'solid' : 'ghost'"
                size="sm"
                :icon="previewComplete ? 'i-lucide-eye' : 'i-lucide-eye-off'"
                square
                :aria-label="previewComplete ? 'Revenir à mon classeur' : 'Aperçu du classeur complété'"
                :title="
                  previewComplete
                    ? 'Revenir à mon classeur (cartes manquantes grisées)'
                    : 'Aperçu : voir le classeur comme s’il était complet'
                "
                @click="previewComplete = !previewComplete"
              />
            </div>
          </div>
        </div>

        <div v-if="viewMode === 'pages'" class="binder-stage mt-4 mb-3 sm:mt-5 sm:mb-4">
          <GoupixDexBinderPages
            :binder="binder"
            href-base="/collection/"
            :preview-complete="previewComplete"
            @updated="onBinderUpdated"
          />
        </div>

        <div v-else-if="viewMode === 'valeurs'" class="app-dashboard-page space-y-4 pt-4 sm:pt-5">
          <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <UCard class="lg:col-span-2" :ui="{ body: 'p-5 sm:p-6' }">
              <p class="app-label">Valeur du classeur complété</p>
              <p class="text-highlighted mt-1.5 text-3xl font-semibold tabular-nums sm:text-4xl">
                {{ eurValue.format(totalValue) }}
              </p>
              <div class="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
                <span class="text-muted">
                  Possédé <span class="text-highlighted font-medium">{{ eurValue.format(ownedValue) }}</span>
                </span>
                <span class="text-muted">
                  Reste à acquérir <span class="text-highlighted font-medium">{{ eurValue.format(missingValue) }}</span>
                </span>
                <span
                  v-if="binder.pokedex_total"
                  class="inline-flex items-center gap-1 rounded-full bg-(--app-green-soft) px-2 py-0.5 text-xs font-semibold text-(--app-green)"
                >
                  {{ binder.pokedex_owned ?? 0 }} / {{ binder.pokedex_total }} cartes
                </span>
              </div>
            </UCard>

            <UCard :ui="{ body: 'p-5 sm:p-6' }">
              <p class="app-label mb-3">Répartition</p>
              <div v-if="totalValue > 0" class="flex items-center gap-4">
                <div class="relative grid shrink-0 place-items-center">
                  <div class="h-28 w-28 rounded-full" :style="donutRingStyle" />
                  <div class="absolute text-center">
                    <p class="text-highlighted text-sm font-semibold tabular-nums">{{ ownedPct }}%</p>
                  </div>
                </div>
                <div class="min-w-0 space-y-2 text-sm">
                  <div class="flex items-center gap-2">
                    <span class="size-2.5 shrink-0 rounded-full bg-(--app-green)" />
                    <span class="text-muted">Possédé</span>
                    <span class="text-highlighted ml-auto font-medium tabular-nums">{{ ownedPct }}%</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="size-2.5 shrink-0 rounded-full bg-(--app-accent)" />
                    <span class="text-muted">Manquant</span>
                    <span class="text-highlighted ml-auto font-medium tabular-nums">{{ missingPct }}%</span>
                  </div>
                </div>
              </div>
              <p v-else class="text-muted py-8 text-center text-sm">Aucune carte cotée pour l'instant.</p>
            </UCard>
          </div>

          <UCard :ui="{ body: 'p-4 sm:p-5' }">
            <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex items-center gap-4 text-xs">
                <span class="flex items-center gap-1.5">
                  <span class="h-0.5 w-4 rounded bg-(--ui-primary)" />
                  <span class="text-muted">Valeur totale</span>
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="h-0.5 w-4 rounded bg-(--app-green)" />
                  <span class="text-muted">Possédé</span>
                </span>
              </div>
              <div class="flex flex-wrap gap-1">
                <UButton
                  v-for="option in valuePeriodOptions"
                  :key="option.value"
                  :color="option.value === valuePeriod ? 'primary' : 'neutral'"
                  :variant="option.value === valuePeriod ? 'solid' : 'ghost'"
                  size="xs"
                  @click="setValuePeriod(option.value)"
                >
                  {{ option.label }}
                </UButton>
              </div>
            </div>

            <div v-if="valueLoading && !valueTimeline.length" class="flex items-center justify-center py-16">
              <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
            </div>
            <GoupixDexBinderValueChart v-else :points="valueTimeline" :period="valuePeriod" />
          </UCard>
        </div>

        <div v-else class="app-dashboard-page space-y-4 pt-4 sm:pt-5">
          <div
            v-if="isCompletionBinder"
            class="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7"
          >
            <component
              :is="cell.item ? 'button' : 'div'"
              v-for="cell in completionCells"
              :key="cell.key"
              :type="cell.item ? 'button' : undefined"
              class="block w-full text-left"
              :class="cell.item ? 'cursor-pointer' : ''"
              @click="cell.item ? openCardDetail(cell.item) : undefined"
            >
              <div
                class="card-tile relative aspect-[63/88]"
                :class="[
                  cell.item?.kind === 'wanted' && !previewComplete ? 'opacity-70 grayscale' : '',
                  cell.item ? '' : 'ring-1 ring-white/10',
                ]"
              >
                <GoupixDexBinderCardImage
                  v-if="cell.item"
                  :src="cell.item.image_url || limitlessCardImageUrl(cell.item.tcgdex_card_id)"
                  :alt="cell.dex ? cell.dex.pokemonName : cell.item.card_name"
                  :fallback-src="cell.dex?.artworkUrl ?? null"
                />
                <GoupixDexBinderPokedexPlaceholder v-else-if="cell.dex" :placeholder="cell.dex" />
                <span v-if="cell.item && cell.item.quantity > 1" class="tile-badge num top-1.5 right-1.5">
                  ×{{ cell.item.quantity }}
                </span>
              </div>
              <p class="mt-1 truncate text-xs font-medium" :class="cell.item ? '' : 'font-normal text-(--app-faint)'">
                {{ cell.dex ? cell.dex.pokemonName : cell.item?.card_name }}
              </p>
              <p v-if="cell.item && cell.dex" class="truncate text-[10px] leading-tight text-(--app-faint)">
                {{ cell.item.card_name }}
              </p>
            </component>
          </div>

          <template v-else>
            <p v-if="gridItems.length === 0" class="text-muted py-12 text-center text-sm">
              Aucune carte dans ce classeur. Passe en mode Pages pour en ranger.
            </p>
            <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
              <button
                v-for="item in gridItems"
                :key="item.id"
                type="button"
                class="block w-full cursor-pointer text-left"
                @click="openCardDetail(item)"
              >
                <div class="card-tile aspect-[63/88]">
                  <GoupixDexBinderCardImage
                    :src="item.image_url || limitlessCardImageUrl(item.tcgdex_card_id)"
                    :alt="item.card_name"
                  />
                  <span v-if="item.quantity > 1" class="tile-badge num top-1.5 right-1.5">×{{ item.quantity }}</span>
                </div>
                <p class="mt-1 truncate text-xs font-medium">{{ item.card_name }}</p>
              </button>
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
import type { BinderDetail, BinderPocketItem, BinderValuePeriod, BinderValueTimelinePoint } from '~/types/binders'
import type { PokedexPlaceholder } from '~/utils/pokedex/kanto'
import { pokedexPlaceholder } from '~/utils/pokedex/kanto'
import { limitlessCardImageUrl } from '~/utils/cards/limitlessCardImage'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const router = useRouter()
const { getBinder, updateBinder, deleteBinder, getBinderValueTimeline } = useBinders()
const { confirm } = useGoupixConfirm()
const toast = useToast()
const drawerStack = useGoupixDrawerStack()

const id = computed(() => Number(route.params.id))
const loading = ref(true)
const binder = ref<BinderDetail | null>(null)
type BinderViewMode = 'pages' | 'grille' | 'valeurs'
const viewMode = computed({
  get: (): BinderViewMode => {
    if (route.query.vue === 'grille') {
      return 'grille'
    }
    if (route.query.vue === 'pages') {
      return 'pages'
    }
    if (route.query.vue === 'valeurs') {
      return 'valeurs'
    }
    // Un classeur de complétion s'affiche mieux en grille (toutes les cases visibles) : vue par défaut.
    return binder.value?.pokedex_region ? 'grille' : 'pages'
  },
  set: (v: BinderViewMode) => {
    void router.replace({ query: { ...route.query, vue: v } })
  },
})
const previewComplete = ref(false)

const viewTabItems = [
  { label: 'Pages', value: 'pages', icon: 'i-lucide-book-open' },
  { label: 'Grille', value: 'grille', icon: 'i-lucide-grid-2x2' },
  { label: 'Valeurs', value: 'valeurs', icon: 'i-lucide-line-chart' },
]

const gridItems = computed(() => [...(binder.value?.items ?? [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)))

const isCompletionBinder = computed(() => !!binder.value?.pokedex_region)

interface CompletionCell {
  key: string
  item: BinderPocketItem | null
  dex: PokedexPlaceholder | null
}

/**
 * Cellules de la grille en mode complétion, dans l'ordre exact des positions du
 * classeur (cartes rangées + placeholders des slots Pokédex), compactées (les
 * pochettes réellement vides ne sont pas affichées). `dex` porte le nom FR +
 * l'artwork du Pokémon de la pochette.
 */
const completionCells = computed<CompletionCell[]>(() => {
  const detail = binder.value
  if (!detail || !detail.pokedex_region) {
    return []
  }
  const slots = detail.pokedex_slots ?? {}
  const byPosition = new Map<number, BinderPocketItem>()
  for (const item of detail.items) {
    if (item.position != null && item.position >= 0 && !byPosition.has(item.position)) {
      byPosition.set(item.position, item)
    }
  }
  const positions = new Set<number>([...byPosition.keys(), ...Object.keys(slots).map(Number)])
  const cells: CompletionCell[] = []
  for (const position of [...positions].sort((a, b) => a - b)) {
    const item = byPosition.get(position) ?? null
    const dexNumber = slots[String(position)]
    cells.push({ key: item ? item.id : `ph-${position}`, item, dex: dexNumber ? pokedexPlaceholder(dexNumber) : null })
  }
  return cells
})

const binderMetaLine = computed(() => {
  if (!binder.value) {
    return ''
  }
  const grid = binder.value.page_grid.replace('x', '×')
  if (binder.value.pokedex_total != null) {
    return `${binder.value.pokedex_owned ?? 0} / ${binder.value.pokedex_total} possédées · feuille ${grid}`
  }
  const n = binder.value.card_count
  return `${n} carte${n > 1 ? 's' : ''} · feuille ${grid}`
})

// --- Onglet « Valeurs » : chiffres, répartition et courbe d'évolution ---
const eurValue: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const valuePeriod = ref<BinderValuePeriod>('tout')
const valueTimeline = ref<BinderValueTimelinePoint[]>([])
const valueLoading = ref(false)

const valuePeriodOptions: { label: string; value: BinderValuePeriod }[] = [
  { label: '7J', value: '7j' },
  { label: '1M', value: '1m' },
  { label: '3M', value: '3m' },
  { label: '6M', value: '6m' },
  { label: 'Tout', value: 'tout' },
]

const totalValue = computed<number>(() => binder.value?.total_value_eur ?? 0)
const ownedValue = computed<number>(() => binder.value?.estimated_value_eur ?? 0)
const missingValue = computed<number>(() => Math.max(0, totalValue.value - ownedValue.value))
const ownedPct = computed<number>(() =>
  totalValue.value > 0 ? Math.min(100, Math.round((ownedValue.value / totalValue.value) * 100)) : 0,
)
const missingPct = computed<number>(() => (totalValue.value > 0 ? 100 - ownedPct.value : 0))

const donutRingStyle = computed<Record<string, string>>(() => {
  const owned = ownedPct.value
  const mask = 'radial-gradient(farthest-side, transparent 58%, #000 59%)'
  return {
    background: `conic-gradient(var(--app-green) 0 ${owned}%, var(--app-accent) ${owned}% 100%)`,
    mask,
    WebkitMask: mask,
  }
})

/**
 * Recharge la courbe de valeur du classeur pour la période sélectionnée.
 * @returns Résolue après mise à jour de la timeline.
 */
async function loadValueTimeline(): Promise<void> {
  if (!binder.value) {
    return
  }
  valueLoading.value = true
  try {
    const data = await getBinderValueTimeline(binder.value.id, valuePeriod.value)
    valueTimeline.value = data.points
  } catch {
    toast.add({ title: 'Évolution de la valeur', color: 'error' })
  } finally {
    valueLoading.value = false
  }
}

/**
 * Change la période affichée et recharge la courbe.
 * @param next - Nouvelle période.
 * @returns Résolue après rechargement.
 */
async function setValuePeriod(next: BinderValuePeriod): Promise<void> {
  if (next === valuePeriod.value) {
    return
  }
  valuePeriod.value = next
  await loadValueTimeline()
}

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
    if (viewMode.value === 'valeurs') {
      void loadValueTimeline()
    }
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

/**
 * Ouvre la fiche (drawer) d'une carte du classeur : image, prix, lien Cardmarket.
 * @param item - Pochette cliquée (carte possédée ou manquante).
 * @returns {void}
 */
function openCardDetail(item: BinderPocketItem): void {
  drawerStack.pushCard(item.collection_card_id)
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

watch(viewMode, (mode) => {
  if (mode === 'valeurs' && binder.value && !valueTimeline.value.length) {
    void loadValueTimeline()
  }
})

watch(
  () => drawerStack.cardMutationCounter.value,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
})
</script>
