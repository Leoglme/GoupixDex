<template>
  <UDashboardPanel id="articles-sold">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Vente
          </span>
        </template>
        <template #right>
          <UButton icon="i-lucide-refresh-cw" color="neutral" variant="ghost" :loading="loading" @click="load" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-4 px-3 py-3 sm:px-4 sm:py-4">
        <GoupixDexPageHeader
          title="Mes articles"
          description="Ventes enregistrées sur Vinted et eBay, de la plus récente à la plus ancienne."
        />

        <GoupixDexPageTabs :items="ARTICLES_PAGE_TABS">
          <template #trailing>
            <div class="flex flex-wrap gap-2">
              <UButton
                v-for="opt in channelOptions"
                :key="opt.value ?? 'all'"
                size="xs"
                :color="channelFilter === opt.value ? 'primary' : 'neutral'"
                :variant="channelFilter === opt.value ? 'solid' : 'subtle'"
                @click="channelFilter = opt.value"
              >
                {{ opt.label }}
              </UButton>
            </div>
          </template>
        </GoupixDexPageTabs>

        <div v-if="loading && !payload" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
        </div>

        <template v-else-if="payload">
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <GoupixDexStatsCard
              title="Ventes"
              :value="String(payload.count)"
              :description="channelDescription"
              icon="i-lucide-shopping-bag"
            />
            <GoupixDexStatsCard
              title="Chiffre d'affaires"
              :value="eur.format(payload.revenue_eur)"
              icon="i-lucide-coins"
            />
            <GoupixDexStatsCard
              title="Marge totale"
              :value="eur.format(payload.profit_eur)"
              icon="i-lucide-trending-up"
            />
            <GoupixDexStatsCard
              v-if="channelFilter === null"
              title="Répartition"
              :value="`${payload.vinted_count} / ${payload.ebay_count}`"
              description="Vinted / eBay"
              icon="i-lucide-pie-chart"
            />
          </div>

          <GoupixDexDashboardSalesTable
            :sales="payload.sales"
            title="Toutes les ventes"
            subtitle="Même tableau que sur le tableau de bord — accès à la fiche article via la flèche"
            :empty-message="emptyTableMessage"
            max-height-class="max-h-[min(70vh,48rem)] overflow-auto"
          />
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { SoldSalesChannelFilter, SoldSalesResponse } from '~/composables/useStats'
import { apiErrorMessage } from '~/composables/useApiError'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Mes articles — Vendus',
  'Historique de vos ventes Vinted et eBay enregistrées dans GoupixDex : prix, marge et canal de vente.',
)

const { fetchSoldSales } = useStats()
const toast = useToast()

const loading: Ref<boolean> = ref(false)
const payload: Ref<SoldSalesResponse | null> = ref(null)
const channelFilter: Ref<SoldSalesChannelFilter> = ref(null)

const channelOptions: { label: string; value: SoldSalesChannelFilter }[] = [
  { label: 'Tous', value: null },
  { label: 'Vinted', value: 'vinted' },
  { label: 'eBay', value: 'ebay' },
]

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const channelDescription = computed(() => {
  if (channelFilter.value === 'vinted') {
    return 'Canal Vinted uniquement'
  }
  if (channelFilter.value === 'ebay') {
    return 'Canal eBay uniquement'
  }
  return 'Vinted et eBay'
})

const emptyTableMessage = computed(() => {
  if (channelFilter.value === 'vinted') {
    return 'Aucune vente Vinted enregistrée.'
  }
  if (channelFilter.value === 'ebay') {
    return 'Aucune vente eBay enregistrée.'
  }
  return 'Aucune vente enregistrée pour le moment.'
})

async function load(): Promise<void> {
  loading.value = true
  try {
    payload.value = await fetchSoldSales(channelFilter.value)
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

watch(
  channelFilter,
  () => {
    void load()
  },
  { immediate: true },
)
</script>
