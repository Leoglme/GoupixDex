<template>
  <UDashboardPanel id="portfolio-value-page">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-line-chart" class="h-3 w-3 text-(--app-accent)" />
            Valeur
          </span>
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="reloadAll" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full">
        <GoupixDexPageHeader
          title="Valeur de la collection"
          description="Répartition cartes / produits et évolution de la valeur dans le temps."
        />

        <GoupixDexCollectionSectionTabs active="valeur" />

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <UCard class="lg:col-span-2" :ui="{ body: 'p-5 sm:p-6' }">
            <p class="app-label">Valeur du marché</p>
            <p class="text-highlighted mt-1.5 text-3xl font-semibold tabular-nums sm:text-4xl">
              {{ eur.format(summary.total_market_eur) }}
            </p>
            <div class="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              <span class="text-muted">
                Cartes <span class="text-highlighted font-medium">{{ eur.format(summary.cards_market_eur) }}</span>
              </span>
              <span class="text-muted">
                Produits <span class="text-highlighted font-medium">{{ eur.format(summary.sealed_market_eur) }}</span>
              </span>
              <span
                v-if="summary.sealed_gain_percent != null"
                class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                :class="
                  summary.sealed_gain_eur >= 0
                    ? 'bg-(--app-green-soft) text-(--app-green)'
                    : 'bg-(--app-red-soft) text-(--app-red)'
                "
              >
                <UIcon
                  :name="summary.sealed_gain_eur >= 0 ? 'i-lucide-trending-up' : 'i-lucide-trending-down'"
                  class="size-3.5"
                />
                {{ gainLabel }} sur les produits
              </span>
            </div>
          </UCard>

          <UCard :ui="{ body: 'p-5 sm:p-6' }">
            <p class="app-label mb-3">Répartition</p>
            <div v-if="hasSplit" class="flex items-center gap-4">
              <div class="relative grid shrink-0 place-items-center">
                <div class="h-28 w-28 rounded-full" :style="donutRingStyle" />
                <div class="absolute text-center">
                  <p class="text-highlighted text-sm font-semibold tabular-nums">
                    {{ eur.format(summary.total_market_eur) }}
                  </p>
                </div>
              </div>
              <div class="min-w-0 space-y-2 text-sm">
                <div class="flex items-center gap-2">
                  <span class="size-2.5 shrink-0 rounded-full bg-(--app-blue)" />
                  <span class="text-muted">Cartes</span>
                  <span class="text-highlighted ml-auto font-medium tabular-nums">{{ cardsPct }}%</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="size-2.5 shrink-0 rounded-full bg-(--app-accent)" />
                  <span class="text-muted">Produits</span>
                  <span class="text-highlighted ml-auto font-medium tabular-nums">{{ sealedPct }}%</span>
                </div>
              </div>
            </div>
            <p v-else class="text-muted py-8 text-center text-sm">Ajoutez des cartes ou des produits cotés.</p>
          </UCard>
        </div>

        <UCard :ui="{ body: 'p-4 sm:p-5' }">
          <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-4 text-xs">
              <span class="flex items-center gap-1.5">
                <span class="h-0.5 w-4 rounded bg-(--ui-primary)" />
                <span class="text-muted">Valeur du marché</span>
              </span>
              <span class="flex items-center gap-1.5">
                <span class="w-4 border-t border-dashed border-(--app-ink-soft)" />
                <span class="text-muted">Valeur d'achat (produits)</span>
              </span>
            </div>
            <div class="flex flex-wrap gap-1">
              <UButton
                v-for="option in periodOptions"
                :key="option.value"
                :color="option.value === period ? 'primary' : 'neutral'"
                :variant="option.value === period ? 'solid' : 'ghost'"
                size="xs"
                @click="setPeriod(option.value)"
              >
                {{ option.label }}
              </UButton>
            </div>
          </div>

          <div v-if="loading && !timeline.length" class="flex items-center justify-center py-16">
            <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
          </div>
          <GoupixDexPortfolioValueChart v-else :points="timeline" :period="period" />
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { PortfolioPeriod, PortfolioSummary, PortfolioTimelinePoint } from '~/composables/usePortfolio'
import { formatSignedPercent } from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo('Valeur de la collection', 'Suivez la valeur de vos cartes et produits scellés et son évolution.')

const { getSummary, getTimeline } = usePortfolio()
const toast = useToast()

const EMPTY_SUMMARY: PortfolioSummary = {
  total_market_eur: 0,
  cards_market_eur: 0,
  sealed_market_eur: 0,
  purchase_value_eur: 0,
  sealed_gain_eur: 0,
  sealed_gain_percent: null,
  split: [],
  cards_count: 0,
  sealed_count: 0,
  sealed_total_quantity: 0,
  history_days: 0,
}

const summary = ref<PortfolioSummary>(EMPTY_SUMMARY)
const timeline = ref<PortfolioTimelinePoint[]>([])
const period = ref<PortfolioPeriod>('tout')
const loading = ref(false)

const periodOptions: { label: string; value: PortfolioPeriod }[] = [
  { label: '1J', value: '1j' },
  { label: '7J', value: '7j' },
  { label: '1M', value: '1m' },
  { label: '3M', value: '3m' },
  { label: '6M', value: '6m' },
  { label: 'Tout', value: 'tout' },
]

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const hasSplit = computed<boolean>(() => summary.value.total_market_eur > 0)

const cardsPct = computed<number>(() => {
  const total = summary.value.total_market_eur
  return total > 0 ? Math.round((summary.value.cards_market_eur / total) * 100) : 0
})

const sealedPct = computed<number>(() => (hasSplit.value ? 100 - cardsPct.value : 0))

const donutRingStyle = computed<Record<string, string>>(() => {
  const cards = cardsPct.value
  const mask = 'radial-gradient(farthest-side, transparent 58%, #000 59%)'
  return {
    background: `conic-gradient(var(--app-blue) 0 ${cards}%, var(--app-accent) ${cards}% 100%)`,
    mask,
    WebkitMask: mask,
  }
})

const gainLabel = computed<string>(() => {
  const percent = summary.value.sealed_gain_percent
  return percent == null ? eur.format(summary.value.sealed_gain_eur) : formatSignedPercent(percent)
})

/**
 * Recharge le résumé de valeur (chiffres et répartition).
 * @returns Résolue après mise à jour du résumé.
 */
async function loadSummary(): Promise<void> {
  try {
    summary.value = await getSummary()
  } catch (e) {
    toast.add({ title: 'Valeur de la collection', description: apiErrorMessage(e), color: 'error' })
  }
}

/**
 * Recharge la courbe pour la période sélectionnée.
 * @returns Résolue après mise à jour de la timeline.
 */
async function loadTimeline(): Promise<void> {
  try {
    const data = await getTimeline(period.value)
    timeline.value = data.points
  } catch (e) {
    toast.add({ title: 'Évolution de la valeur', description: apiErrorMessage(e), color: 'error' })
  }
}

/**
 * Recharge résumé et courbe ensemble.
 * @returns Résolue quand les deux appels sont terminés.
 */
async function reloadAll(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([loadSummary(), loadTimeline()])
  } finally {
    loading.value = false
  }
}

/**
 * Change la période affichée et recharge la courbe.
 * @param next - Nouvelle période.
 * @returns Résolue après rechargement.
 */
async function setPeriod(next: PortfolioPeriod): Promise<void> {
  if (next === period.value) {
    return
  }
  period.value = next
  loading.value = true
  try {
    await loadTimeline()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void reloadAll()
})
</script>
