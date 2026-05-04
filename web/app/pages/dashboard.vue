<template>
  <UDashboardPanel id="dashboard">
    <template #header>
      <UDashboardNavbar title="Tableau de bord">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton icon="i-lucide-refresh-cw" color="neutral" variant="ghost" :loading="loading" @click="load" />
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <template #left>
          <GoupixDexDashboardDateRangePicker v-model="range" class="-ms-1" />
          <GoupixDexDashboardPeriodSelect v-model="period" :range="range" />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <USwitch v-model="fetchMarketData" />
            <span class="text-muted text-xs"> Données Cardmarket (plus lent) </span>
          </div>
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="space-y-8 p-4 sm:p-6">
        <div v-if="loading && !stats" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
        </div>

        <template v-else-if="stats">
          <!-- Profit / revenue stat cards -->
          <UPageGrid class="gap-4 sm:gap-6 lg:grid-cols-4 lg:gap-px">
            <GoupixDexStatsCard
              title="Bénéfice de la période"
              :value="eur.format(stats.profit_period_eur)"
              icon="i-lucide-trending-up"
            />
            <GoupixDexStatsCard
              title="Vente de la période"
              :value="eur.format(stats.revenue_period_eur)"
              :description="`${numberFmt.format(stats.period_sales_count)} vente${stats.period_sales_count > 1 ? 's' : ''}`"
              icon="i-lucide-shopping-bag"
            />
            <GoupixDexStatsCard
              title="Bénéfice total"
              :value="eur.format(stats.profit_total_eur)"
              icon="i-lucide-piggy-bank"
            />
            <GoupixDexStatsCard
              title="Vente total"
              :value="eur.format(stats.vinted_revenue_eur)"
              icon="i-lucide-coins"
            />
          </UPageGrid>

          <div class="grid gap-6 lg:grid-cols-2">
            <!-- Inventory for sale -->
            <UCard>
              <template #header>
                <p class="text-highlighted text-sm font-medium">Stock en vente</p>
                <p class="text-muted text-xs">
                  Cartes non vendues — totaux demandés, coût d'achat, marché et bénéfice estimé
                </p>
              </template>
              <dl class="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt class="text-muted text-xs tracking-wide uppercase">Cartes</dt>
                  <dd class="text-highlighted text-2xl font-semibold tabular-nums">
                    {{ stats.inventory_count }}
                  </dd>
                </div>
                <div>
                  <dt class="text-muted text-xs tracking-wide uppercase">Prix de vente affichés</dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{ eur2.format(stats.inventory_sell_total_eur) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-muted text-xs tracking-wide uppercase">Coût d'achat</dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{ eur2.format(stats.inventory_purchase_total_eur) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-muted text-xs tracking-wide uppercase">Bénéfice estimé</dt>
                  <dd class="text-primary text-xl font-semibold tabular-nums">
                    {{ eur2.format(stats.inventory_estimated_profit_eur) }}
                  </dd>
                </div>
                <div class="sm:col-span-2">
                  <dt class="text-muted text-xs tracking-wide uppercase">Prix Cardmarket</dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{
                      stats.estimated_cardmarket_unsold_eur != null
                        ? eur2.format(stats.estimated_cardmarket_unsold_eur)
                        : '—'
                    }}
                  </dd>
                </div>
              </dl>
              <p v-if="stats.market_lookup_errors && fetchMarketData" class="text-warning mt-4 text-xs">
                {{ stats.market_lookup_errors }} carte(s) sans prix PokéWallet (réf. incomplète).
              </p>
            </UCard>

            <!-- Vinted vs eBay sales pie -->
            <UCard>
              <template #header>
                <p class="text-highlighted text-sm font-medium">Ventes Vinted vs eBay</p>
                <p class="text-muted text-xs">Répartition du chiffre d'affaires par canal (toutes périodes)</p>
              </template>
              <div class="flex flex-col items-center gap-6 sm:flex-row">
                <div class="ring-default size-40 shrink-0 rounded-full shadow-sm ring-2" :style="pieStyle" />
                <ul class="w-full min-w-0 flex-1 space-y-3 text-sm">
                  <li v-for="seg in channelSegments" :key="seg.label" class="flex items-start justify-between gap-x-4">
                    <span class="flex min-w-0 items-center gap-2">
                      <span class="mt-1.5 size-2.5 shrink-0 rounded-full" :style="{ backgroundColor: seg.color }" />
                      <span class="leading-snug">
                        <span class="text-highlighted font-medium">{{ seg.label }}</span>
                        <span class="text-muted">
                          · {{ numberFmt.format(seg.count) }} vente{{ seg.count > 1 ? 's' : '' }}</span
                        >
                      </span>
                    </span>
                    <span class="shrink-0 text-right">
                      <span class="block font-semibold tabular-nums">{{ eur.format(seg.value) }}</span>
                      <span class="text-muted text-xs tabular-nums">{{ pct(seg.value) }}</span>
                    </span>
                  </li>
                  <li v-if="!channelSegments.length" class="text-muted text-sm">
                    Aucune vente enregistrée sur Vinted ou eBay.
                  </li>
                </ul>
              </div>
            </UCard>
          </div>

          <!-- Revenue chart driven by period + range -->
          <GoupixDexDashboardRevenueChart :stats="stats" :period="period" />

          <!-- Recent sales -->
          <GoupixDexDashboardSalesTable :sales="stats.recent_sales" />

          <!-- Rankings -->
          <GoupixDexCharts :stats="stats" />
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref, ShallowRef } from 'vue'
import { sub } from 'date-fns'
import type { DashboardPeriod, DashboardRange, DashboardStats } from '~/composables/useStats'
import { dashboardPrefsToRange, loadDashboardPrefs, saveDashboardPrefs } from '~/composables/useUiPrefsLocalStorage'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Tableau de bord',
  "Vue d'ensemble GoupixDex : stock, chiffre d'affaires, marges et répartition des ventes pour vos cartes Pokémon TCG.",
)

const { fetchDashboard } = useStats()
const toast = useToast()

const stats: Ref<DashboardStats | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const fetchMarketData: Ref<boolean> = ref(false)
const range: ShallowRef<DashboardRange> = shallowRef<DashboardRange>({
  start: sub(new Date(), { days: 30 }),
  end: new Date(),
})
const period: Ref<DashboardPeriod> = ref('daily')
const suppressDashboardPrefsWatch: Ref<boolean> = ref(false)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const eur2: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const numberFmt: Intl.NumberFormat = new Intl.NumberFormat('fr-FR')

const CHANNEL_COLORS = {
  vinted: 'rgb(0, 131, 143)',
  ebay: 'rgb(134, 184, 23)',
} as const

type PieSegment = { value: number; label: string; color: string; count: number }

const channelSegments: ComputedRef<PieSegment[]> = computed(() => {
  const split = stats.value?.channel_split_total
  if (!split) {
    return []
  }
  const out: PieSegment[] = []
  if (split.vinted_revenue_eur > 0 || split.vinted_count > 0) {
    out.push({
      label: 'Vinted',
      value: split.vinted_revenue_eur,
      count: split.vinted_count,
      color: CHANNEL_COLORS.vinted,
    })
  }
  if (split.ebay_revenue_eur > 0 || split.ebay_count > 0) {
    out.push({
      label: 'eBay',
      value: split.ebay_revenue_eur,
      count: split.ebay_count,
      color: CHANNEL_COLORS.ebay,
    })
  }
  return out
})

const channelTotal: ComputedRef<number> = computed(() => channelSegments.value.reduce((acc, s) => acc + s.value, 0))

const pieStyle: ComputedRef<{ background: string }> = computed(() => {
  const segs = channelSegments.value
  const total = segs.reduce((a, b) => a + b.value, 0)
  if (total <= 0) {
    return { background: 'conic-gradient(var(--ui-border) 0% 100%)' }
  }
  let acc = 0
  const parts = segs.map((s) => {
    const pct = (s.value / total) * 100
    const start = acc
    acc += pct
    return `${s.color} ${start}% ${acc}%`
  })
  return { background: `conic-gradient(${parts.join(', ')})` }
})

async function load(): Promise<void> {
  loading.value = true
  try {
    stats.value = await fetchDashboard({
      includeMarket: fetchMarketData.value,
      range: range.value,
      period: period.value,
    })
  } catch {
    toast.add({ title: 'Impossible de charger les statistiques', color: 'error' })
  } finally {
    loading.value = false
  }
}

function pct(value: number): string {
  if (channelTotal.value <= 0) {
    return '0%'
  }
  return `${Math.round((value / channelTotal.value) * 100)}%`
}

watch([fetchMarketData, range, period], (): void => {
  if (suppressDashboardPrefsWatch.value) {
    return
  }
  saveDashboardPrefs({
    range: range.value,
    period: period.value,
    fetchMarketData: fetchMarketData.value,
  })
  void load()
})

onMounted((): void => {
  suppressDashboardPrefsWatch.value = true
  try {
    const saved = loadDashboardPrefs()
    if (saved?.range) {
      const r = dashboardPrefsToRange({
        startIso: saved.range.startIso,
        endIso: saved.range.endIso,
      })
      if (r) {
        range.value = r
      }
    }
    if (saved?.period) {
      period.value = saved.period
    }
    if (typeof saved?.fetchMarketData === 'boolean') {
      fetchMarketData.value = saved.fetchMarketData
    }
  } finally {
    suppressDashboardPrefsWatch.value = false
  }
  void load()
})
</script>
