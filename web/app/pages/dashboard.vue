<script setup lang="ts">
import type { DashboardStats } from '~/composables/useStats'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Tableau de bord',
  'Vue d’ensemble GoupixDex : stock, chiffre d’affaires, marges et répartition des ventes pour vos cartes Pokémon TCG.'
)

const { fetchDashboard } = useStats()

const stats = ref<DashboardStats | null>(null)
const loading = ref(true)
/** Si vrai, l’API agrège les refs Cardmarket via PokéWallet (plus lent). */
const fetchMarketData = ref(false)
const toast = useToast()

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

/** Couleurs du camembert (pas de jaune — bleu / vert / violet) */
const PIE = {
  vinted: '#e76112',
  cost: '#fcaa79',
  cardmarket: '#e08804'
} as const

type PieSegment = { value: number, label: string, color: string }

async function load() {
  loading.value = true
  try {
    stats.value = await fetchDashboard(fetchMarketData.value)
  } catch {
    toast.add({ title: 'Impossible de charger les statistiques', color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})

watch(fetchMarketData, () => load())

const pieSegments = computed<PieSegment[]>(() => {
  const s = stats.value
  if (!s) {
    return []
  }
  const v = Math.max(0, s.vinted_revenue_eur)
  const p = Math.max(0, s.inventory_purchase_total_eur)
  const m = fetchMarketData.value ? Math.max(0, s.estimated_cardmarket_unsold_eur ?? 0) : 0
  const out: PieSegment[] = []
  if (v > 0) {
    out.push({ value: v, label: 'CA cumulé (ventes Vinted)', color: PIE.vinted })
  }
  if (p > 0) {
    out.push({ value: p, label: 'Coût d\'achat du stock en vente', color: PIE.cost })
  }
  if (fetchMarketData.value && m > 0) {
    out.push({ value: m, label: 'Ref. Cardmarket (stock seulement)', color: PIE.cardmarket })
  }
  return out
})

const pieStyle = computed(() => {
  const segs = pieSegments.value
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
    </template>

    <template #body>
      <div class="space-y-8 p-4 sm:p-6">
        <div class="flex flex-wrap items-center gap-3">
          <USwitch v-model="fetchMarketData" />
          <span class="text-sm text-muted">
            Récupérer les données Cardmarket / PokéWallet (plus lent)
          </span>
        </div>

        <div v-if="loading && !stats" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-primary" />
        </div>

        <template v-else-if="stats">
          <!-- Cartes bénéfices / CA : une seule bande (style Nuxt UI dashboard) -->
          <UPageGrid class="lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-px">
            <StatsCard
              title="Bénéfice (7 j)"
              :value="eur.format(stats.profit_week_eur)"
              icon="i-lucide-trending-up"
            />
            <StatsCard
              title="Bénéfice (30 j)"
              :value="eur.format(stats.profit_month_eur)"
              icon="i-lucide-calendar"
            />
            <StatsCard
              title="Bénéfice total"
              :value="eur.format(stats.profit_total_eur)"
              icon="i-lucide-piggy-bank"
            />
            <StatsCard
              title="CA Vinted (vendus)"
              :value="eur.format(stats.vinted_revenue_eur)"
              icon="i-lucide-shopping-bag"
            />
          </UPageGrid>

          <div class="grid gap-6 lg:grid-cols-2">
            <!-- Stock en vente -->
            <UCard>
              <template #header>
                <p class="text-sm font-medium text-highlighted">
                  Stock en vente
                </p>
                <p class="text-xs text-muted">
                  Cartes non vendues — totaux demandés, coût d'achat et ref. marché
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
                    Ref. Cardmarket
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

            <!-- Camembert + légende avec pastilles -->
            <UCard>
              <template #header>
                <p class="text-sm font-medium text-highlighted">
                  Ventes vs stock
                </p>
                <p class="text-xs text-muted">
                  CA réalisé comparé au coût du stock restant
                  <template v-if="fetchMarketData">
                    et à l'estimation Cardmarket du stock
                  </template>
                </p>
              </template>
              <div class="flex flex-col sm:flex-row gap-6 items-center">
                <div
                  class="size-40 rounded-full shrink-0 ring-2 ring-default shadow-sm"
                  :style="pieStyle"
                />
                <ul class="text-sm space-y-3 flex-1 w-full min-w-0">
                  <li
                    v-for="seg in pieSegments"
                    :key="seg.label"
                    class="flex items-start justify-between gap-x-4"
                  >
                    <span class="flex items-center gap-2 min-w-0">
                      <span
                        class="size-2.5 rounded-full shrink-0 mt-1.5"
                        :style="{ backgroundColor: seg.color }"
                      />
                      <span class="text-muted leading-snug">{{ seg.label }}</span>
                    </span>
                    <span class="font-semibold tabular-nums shrink-0">{{ eur.format(seg.value) }}</span>
                  </li>
                  <li
                    v-if="!pieSegments.length"
                    class="text-muted text-sm"
                  >
                    Aucune donnée à afficher (pas encore de ventes ni de stock valorisé).
                  </li>
                </ul>
              </div>
            </UCard>
          </div>

          <!-- Graphique CA cumulé (pleine largeur) -->
          <DashboardRevenueChart :stats="stats" />

          <!-- Dernières ventes -->
          <DashboardSalesTable :sales="stats.recent_sales" />

          <!-- Classements -->
          <Charts :stats="stats" />
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
