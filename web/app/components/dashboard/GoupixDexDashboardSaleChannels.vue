<template>
  <UCard :ui="{ body: 'p-4' }" class="min-w-0">
    <div class="mb-4 flex items-center justify-between gap-2">
      <h2 class="text-highlighted text-sm font-semibold">Canaux de vente</h2>
      <span class="text-muted text-xs tabular-nums">{{ totalSalesLabel }}</span>
    </div>

    <ul class="space-y-4.5">
      <li
        v-for="channel in channelsByRevenue"
        :key="channel.sale_source"
        :class="{ 'opacity-50': channel.sales_count === 0 }"
      >
        <div class="flex items-center gap-2.5">
          <GoupixDexMarketplaceAppIcon :marketplace="channel.sale_source" />
          <span class="min-w-0 flex-1">
            <span class="text-highlighted block text-sm font-semibold">{{
              MARKETPLACE_NAMES[channel.sale_source]
            }}</span>
            <span class="text-muted block truncate text-xs">{{ buildChannelSubtitle(channel) }}</span>
          </span>
          <span class="shrink-0 text-right tabular-nums">
            <span class="text-highlighted block text-sm font-semibold">
              {{ roundedEuroFormatter.format(channel.revenue_eur) }}
            </span>
            <span class="text-muted block text-xs">{{ Math.round(computeRevenueSharePercent(channel)) }} %</span>
          </span>
        </div>
        <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-(--app-surface-2)">
          <div
            class="h-full rounded-full"
            :class="BAR_CLASSES_BY_MARKETPLACE[channel.sale_source]"
            :style="{ width: `${computeRevenueSharePercent(channel)}%` }"
          />
        </div>
      </li>
    </ul>
  </UCard>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type { ChannelSales } from '~/composables/useStats'
import type { GoupixDexDashboardSaleChannelsProps } from '~/types/GoupixDexDashboardSaleChannels'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES } from '~/utils/marketplaces'

const props: GoupixDexDashboardSaleChannelsProps = defineProps({
  channels: {
    type: Array as PropType<ChannelSales[]>,
    required: true,
  },
})

const BAR_CLASSES_BY_MARKETPLACE: Record<Marketplace, string> = {
  vinted: 'bg-[#00838f]',
  ebay: 'bg-[#86b817]',
  leboncoin: 'bg-[#ff6e14]',
}

const roundedEuroFormatter: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const totalRevenue: ComputedRef<number> = computed((): number =>
  props.channels.reduce((total: number, channel: ChannelSales): number => total + channel.revenue_eur, 0),
)

const totalSalesLabel: ComputedRef<string> = computed((): string => {
  const salesCount: number = props.channels.reduce(
    (total: number, channel: ChannelSales): number => total + channel.sales_count,
    0,
  )
  return `${salesCount} vente${salesCount > 1 ? 's' : ''}`
})

const channelsByRevenue: ComputedRef<ChannelSales[]> = computed((): ChannelSales[] =>
  [...props.channels].sort(
    (first: ChannelSales, second: ChannelSales): number => second.revenue_eur - first.revenue_eur,
  ),
)

/**
 * Part du chiffre d'affaires de la période faite sur ce canal.
 * @param {ChannelSales} channel - Canal décrit.
 * @returns {number} Pourcentage entre 0 et 100.
 */
function computeRevenueSharePercent(channel: ChannelSales): number {
  return totalRevenue.value > 0 ? (channel.revenue_eur / totalRevenue.value) * 100 : 0
}

/**
 * Ligne sous le nom du canal : nombre de ventes et bénéfice.
 * @param {ChannelSales} channel - Canal décrit.
 * @returns {string} « 18 ventes · +290 € de bénéfice », ou « Aucune vente ».
 */
function buildChannelSubtitle(channel: ChannelSales): string {
  if (channel.sales_count === 0) {
    return 'Aucune vente'
  }

  const profitSign: string = channel.profit_eur > 0 ? '+' : ''
  const salesLabel: string = `${channel.sales_count} vente${channel.sales_count > 1 ? 's' : ''}`
  return `${salesLabel} · ${profitSign}${roundedEuroFormatter.format(channel.profit_eur)} de bénéfice`
}
</script>
