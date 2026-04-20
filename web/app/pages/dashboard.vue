<script setup lang="ts">
import { sub } from 'date-fns'
import type { DashboardPeriod, DashboardRange, DashboardStats } from '~/composables/useStats'
import {
  dashboardPrefsToRange,
  loadDashboardPrefs,
  saveDashboardPrefs
} from '~/composables/useUiPrefsLocalStorage'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Tableau de bord',
  "Vue d'ensemble GoupixDex : stock, chiffre d'affaires, marges et répartition des ventes pour vos cartes Pokémon TCG."
)

const { fetchDashboard } = useStats()

const stats = ref<DashboardStats | null>(null)
const loading = ref(true)
/** When true, the API aggregates Cardmarket refs via PokéWallet (slower). */
const fetchMarketData = ref(false)
const toast = useToast()

const range = shallowRef<DashboardRange>({
  start: sub(new Date(), { days: 30 }),
  end: new Date()
})
const period = ref<DashboardPeriod>('daily')

const suppressDashboardPrefsWatch = ref(false)

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
})

const eur2 = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

const numberFmt = new Intl.NumberFormat('fr-FR')

/** Vinted vs eBay channel colors (per the spec). */
const CHANNEL_COLORS = {
  vinted: 'rgb(0, 131, 143)',
  ebay: 'rgb(134, 184, 23)'
} as const

type PieSegment = { value: number, label: string, color: string, count: number }

async function load() {
  loading.value = true
  try {
    stats.value = await fetchDashboard({
      includeMarket: fetchMarketData.value,
      range: range.value,
      period: period.value
    })
  } catch {
    toast.add({ title: 'Impossible de charger les statistiques', color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  suppressDashboardPrefsWatch.value = true
  try {
    const saved = loadDashboardPrefs()
    if (saved?.range) {
      const r = dashboardPrefsToRange({
        startIso: saved.range.startIso,
        endIso: saved.range.endIso
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
  load()
})

watch([fetchMarketData, range, period], () => {
  if (suppressDashboardPrefsWatch.value) {
    return
  }
  saveDashboardPrefs({
    range: range.value,
    period: period.value,
    fetchMarketData: fetchMarketData.value
  })
  load()
})

const channelSegments = computed<PieSegment[]>(() => {
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
      color: CHANNEL_COLORS.vinted
    })
  }
  if (split.ebay_revenue_eur > 0 || split.ebay_count > 0) {
    out.push({
      label: 'eBay',
      value: split.ebay_revenue_eur,
      count: split.ebay_count,
      color: CHANNEL_COLORS.ebay
    })
  }
  return out
})

const channelTotal = computed(() =>
  channelSegments.value.reduce((acc, s) => acc + s.value, 0)
)

const pieStyle = computed(() => {
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

function pct(value: number): string {
  if (channelTotal.value <= 0) {
    return '0%'
  }
  return `${Math.round((value / channelTotal.value) * 100)}%`
}
</script>

<template>
  <UDashboardPanel id="dashboard">
    <template #header>
      <UDashboardNavbar title="Tableau de bord">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            :loading="loading"
            @click="load"
          />
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <template #left>
          <DashboardDateRangePicker v-model="range" class="-ms-1" />
          <DashboardPeriodSelect v-model="period" :range="range" />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <USwitch v-model="fetchMarketData" />
            <span class="text-xs text-muted">
              Données Cardmarket (plus lent)
            </span>
          </div>
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="space-y-8 p-4 sm:p-6">
        <div v-if="loading && !stats" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-primary" />
        </div>

        <template v-else-if="stats">
          <!-- Profit / revenue stat cards -->
          <UPageGrid class="lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-px">
            <StatsCard
              title="Bénéfice de la période"
              :value="eur.format(stats.profit_period_eur)"
              icon="i-lucide-trending-up"
            />
            <StatsCard
              title="Vente de la période"
              :value="eur.format(stats.revenue_period_eur)"
              :description="`${numberFmt.format(stats.period_sales_count)} vente${stats.period_sales_count > 1 ? 's' : ''}`"
              icon="i-lucide-shopping-bag"
            />
            <StatsCard
              title="Bénéfice total"
              :value="eur.format(stats.profit_total_eur)"
              icon="i-lucide-piggy-bank"
            />
            <StatsCard
              title="Vente total"
              :value="eur.format(stats.vinted_revenue_eur)"
              icon="i-lucide-coins"
            />
          </UPageGrid>

          <div class="grid gap-6 lg:grid-cols-2">
            <!-- Inventory for sale -->
            <UCard>
              <template #header>
                <p class="text-sm font-medium text-highlighted">
                  Stock en vente
                </p>
                <p class="text-xs text-muted">
                  Cartes non vendues — totaux demandés, coût d'achat, marché et bénéfice estimé
                </p>
              </template>
              <dl class="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt class="text-xs text-muted uppercase tracking-wide">
                    Cartes
                  </dt>
                  <dd class="text-2xl font-semibold text-highlighted tabular-nums">
                    {{ stats.inventory_count }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-muted uppercase tracking-wide">
                    Prix de vente affichés
                  </dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{ eur2.format(stats.inventory_sell_total_eur) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-muted uppercase tracking-wide">
                    Coût d'achat
                  </dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{ eur2.format(stats.inventory_purchase_total_eur) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-muted uppercase tracking-wide">
                    Bénéfice estimé
                  </dt>
                  <dd class="text-xl font-semibold tabular-nums text-primary">
                    {{ eur2.format(stats.inventory_estimated_profit_eur) }}
                  </dd>
                </div>
                <div class="sm:col-span-2">
                  <dt class="text-xs text-muted uppercase tracking-wide">
                    Prix Cardmarket
                  </dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{
                      stats.estimated_cardmarket_unsold_eur != null
                        ? eur2.format(stats.estimated_cardmarket_unsold_eur)
                        : '—'
                    }}
                  </dd>
                </div>
              </dl>
              <p
                v-if="stats.market_lookup_errors && fetchMarketData"
                class="text-xs text-warning mt-4"
              >
                {{ stats.market_lookup_errors }} carte(s) sans prix PokéWallet (réf. incomplète).
              </p>
            </UCard>

            <!-- Vinted vs eBay sales pie -->
            <UCard>
              <template #header>
                <p class="text-sm font-medium text-highlighted">
                  Ventes Vinted vs eBay
                </p>
                <p class="text-xs text-muted">
                  Répartition du chiffre d'affaires par canal (toutes périodes)
                </p>
              </template>
              <div class="flex flex-col sm:flex-row gap-6 items-center">
                <div
                  class="size-40 rounded-full shrink-0 ring-2 ring-default shadow-sm"
                  :style="pieStyle"
                />
                <ul class="text-sm space-y-3 flex-1 w-full min-w-0">
                  <li
                    v-for="seg in channelSegments"
                    :key="seg.label"
                    class="flex items-start justify-between gap-x-4"
                  >
                    <span class="flex items-center gap-2 min-w-0">
                      <span
                        class="size-2.5 rounded-full shrink-0 mt-1.5"
                        :style="{ backgroundColor: seg.color }"
                      />
                      <span class="leading-snug">
                        <span class="text-highlighted font-medium">{{ seg.label }}</span>
                        <span class="text-muted"> · {{ numberFmt.format(seg.count) }} vente{{ seg.count > 1 ? 's' : '' }}</span>
                      </span>
                    </span>
                    <span class="text-right shrink-0">
                      <span class="font-semibold tabular-nums block">{{ eur.format(seg.value) }}</span>
                      <span class="text-xs text-muted tabular-nums">{{ pct(seg.value) }}</span>
                    </span>
                  </li>
                  <li
                    v-if="!channelSegments.length"
                    class="text-muted text-sm"
                  >
                    Aucune vente enregistrée sur Vinted ou eBay.
                  </li>
                </ul>
              </div>
            </UCard>
          </div>

          <!-- Revenue chart driven by period + range -->
          <DashboardRevenueChart :stats="stats" :period="period" />

          <!-- Recent sales -->
          <DashboardSalesTable :sales="stats.recent_sales" />

          <!-- Rankings -->
          <Charts :stats="stats" />
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
