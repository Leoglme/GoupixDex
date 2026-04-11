<script setup lang="ts">
import type { DashboardStats } from '~/composables/useStats'

definePageMeta({ middleware: 'auth' })

const { fetchDashboard } = useStats()

const stats = ref<DashboardStats | null>(null)
const loading = ref(true)
const includeMarket = ref(true)
const toast = useToast()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
})

async function load() {
  loading.value = true
  try {
    stats.value = await fetchDashboard(includeMarket.value)
  } catch {
    toast.add({ title: 'Impossible de charger les statistiques', color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})

watch(includeMarket, () => load())

const pieStyle = computed(() => {
  const v = stats.value?.vinted_revenue_eur ?? 0
  const m = stats.value?.estimated_cardmarket_inventory_eur
  if (m == null) {
    return {
      background:
        v > 0
          ? 'conic-gradient(var(--ui-primary) 0% 100%)'
          : 'conic-gradient(var(--ui-border) 0% 100%)'
    }
  }
  const total = v + m
  if (total <= 0) {
    return { background: 'conic-gradient(var(--ui-border) 0% 100%)' }
  }
  const pV = Math.round((v / total) * 100)
  return {
    background: `conic-gradient(var(--ui-primary) 0% ${pV}%, var(--color-secondary-400) ${pV}% 100%)`
  }
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
      <div class="space-y-6 p-4 sm:p-6">
        <div class="flex flex-wrap items-center gap-3">
          <USwitch v-model="includeMarket" />
          <span class="text-sm text-muted">Inclure l’estimation Cardmarket (PokéWallet, plus lent)</span>
        </div>

        <div v-if="loading && !stats" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-primary" />
        </div>

        <template v-else-if="stats">
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
            <UCard>
              <template #header>
                <p class="text-sm font-medium text-highlighted">
                  Revenus estimés
                </p>
                <p class="text-xs text-muted">
                  Somme des prix de vente Vinted vs. valeur Cardmarket de l’inventaire (PokéWallet)
                </p>
              </template>
              <div class="flex flex-col sm:flex-row gap-6 items-center">
                <div
                  class="size-36 rounded-full shrink-0"
                  :style="pieStyle"
                />
                <ul class="text-sm space-y-2 flex-1">
                  <li class="flex justify-between gap-2">
                    <span class="text-muted">Vinted (vendu)</span>
                    <span class="font-medium">{{ eur.format(stats.vinted_revenue_eur) }}</span>
                  </li>
                  <li class="flex justify-between gap-2">
                    <span class="text-muted">Cardmarket (stock, ref.)</span>
                    <span class="font-medium">
                      {{
                        stats.estimated_cardmarket_inventory_eur != null
                          ? eur.format(stats.estimated_cardmarket_inventory_eur)
                          : '—'
                      }}
                    </span>
                  </li>
                  <li
                    v-if="stats.market_lookup_errors"
                    class="text-xs text-warning"
                  >
                    {{ stats.market_lookup_errors }} carte(s) sans prix PokéWallet
                  </li>
                </ul>
              </div>
            </UCard>

            <UCard>
              <template #header>
                <p class="text-sm font-medium text-highlighted">
                  Ventes les plus rapides
                </p>
                <p class="text-xs text-muted">
                  Délai entre création et vente
                </p>
              </template>
              <ul v-if="stats.fastest_sold.length" class="divide-y divide-default">
                <li
                  v-for="r in stats.fastest_sold"
                  :key="r.article_id"
                  class="flex justify-between gap-2 py-2 text-sm"
                >
                  <span class="truncate">{{ r.pokemon_name || r.title }}</span>
                  <span class="shrink-0 text-muted">{{ r.hours_to_sell }} h</span>
                </li>
              </ul>
              <p v-else class="text-sm text-muted py-4">
                Aucune vente.
              </p>
            </UCard>
          </div>

          <Charts :stats="stats" />
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
