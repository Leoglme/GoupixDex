<template>
  <UDashboardPanel id="dashboard">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Pilotage
          </span>
        </template>
        <template #right>
          <UButton
            v-if="dashboardTab === 'ventes'"
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            aria-label="Rafraîchir"
            :loading="loading"
            @click="load"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page">
        <GoupixDexCollectionViewTabs v-model="dashboardTab" :items="dashboardTabs" content stretch />

        <GoupixDexCollectionDashboard v-if="dashboardTab === 'collection'" />

        <template v-else>
          <GoupixDexPageHeader
            title="Mes ventes"
            description="Chiffre d'affaires, bénéfices et rythme de vente sur la période choisie."
          >
            <template #actions>
              <div class="flex min-w-0 flex-col gap-1.5 lg:items-end">
                <div class="flex min-w-0 items-center gap-2">
                  <GoupixDexDashboardRangePresetButtons v-model="range" />
                  <GoupixDexDashboardDateRangePicker v-model="range" />
                </div>
                <p class="text-muted text-xs">{{ rangeLabel }}</p>
              </div>
            </template>
          </GoupixDexPageHeader>

          <div v-if="loading && !stats" class="flex justify-center py-16">
            <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
          </div>

          <GoupixDexSalesDashboard v-else-if="stats" :stats="stats" :range-preset-id="rangePresetId" />
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref, ShallowRef } from 'vue'
import type { DashboardRange, DashboardStats } from '~/composables/useStats'
import type { DashboardRangePresetId } from '~/utils/dashboardRange'
import { loadDashboardRange, saveDashboardPrefs } from '~/composables/useUiPrefsLocalStorage'
import { dashboardRangeForPreset, detectDashboardRangePreset } from '~/utils/dashboardRange'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Tableau de bord',
  "Vue d'ensemble GoupixDex : stock, chiffre d'affaires, marges et répartition des ventes pour vos cartes Pokémon TCG.",
)

const { fetchDashboard } = useStats()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const dashboardTabs: { label: string; value: string; icon: string }[] = [
  { label: 'Ventes', value: 'ventes', icon: 'i-lucide-shopping-bag' },
  { label: 'Collection', value: 'collection', icon: 'i-lucide-layers' },
]

const dayMonthFormatter: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })

const fullDateFormatter: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

let latestLoadId: number = 0

const stats: Ref<DashboardStats | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const range: ShallowRef<DashboardRange> = shallowRef(dashboardRangeForPreset('days30'))
const dashboardTab: Ref<string> = ref('ventes')

const rangePresetId: ComputedRef<DashboardRangePresetId | null> = computed((): DashboardRangePresetId | null =>
  detectDashboardRangePreset(range.value),
)

const rangeLabel: ComputedRef<string> = computed((): string => {
  if (rangePresetId.value === 'all') {
    return stats.value?.period_sales_count
      ? `Depuis votre première vente, le ${fullDateFormatter.format(new Date(stats.value.range.start))}`
      : 'Depuis toujours'
  }

  const isSameYear: boolean = range.value.start.getFullYear() === range.value.end.getFullYear()
  const startLabel: string = (isSameYear ? dayMonthFormatter : fullDateFormatter).format(range.value.start)
  return `Du ${startLabel} au ${fullDateFormatter.format(range.value.end)}`
})

/**
 * Charge les ventes de la période affichée ; seule la réponse de la dernière demande est gardée.
 * @returns {Promise<void>}
 */
async function load(): Promise<void> {
  latestLoadId += 1
  const loadId: number = latestLoadId
  loading.value = true

  try {
    const loadedStats: DashboardStats = await fetchDashboard(range.value)

    if (loadId === latestLoadId) {
      stats.value = loadedStats
    }
  } catch {
    toast.add({ title: 'Impossible de charger les statistiques', color: 'error' })
  } finally {
    if (loadId === latestLoadId) {
      loading.value = false
    }
  }
}

watch(range, (): void => {
  saveDashboardPrefs(range.value, rangePresetId.value)
  load()
})

watch(
  (): number => drawerStack.articleMutationCounter.value,
  (): void => {
    load()
  },
)

onMounted((): void => {
  const savedRange: DashboardRange | null = loadDashboardRange()

  if (savedRange) {
    range.value = savedRange
    return
  }
  load()
})
</script>
