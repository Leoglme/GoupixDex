<template>
  <UCard
    :ui="{
      header: 'px-4 sm:px-6 pt-6 pb-3 border-b border-default/60',
      body: 'p-0 sm:p-0',
    }"
  >
    <template #header>
      <div>
        <p class="text-highlighted text-sm font-medium">{{ title }}</p>
        <p class="text-muted text-xs">{{ subtitle }}</p>
      </div>
    </template>

    <div v-if="sortedSales.length" :class="maxHeightClass">
      <table class="w-full border-separate border-spacing-0 text-sm">
        <thead class="sticky top-0 z-10">
          <tr class="bg-elevated/95 border-default border-y backdrop-blur">
            <th class="text-muted border-default border-l px-4 py-2.5 text-left font-medium first:rounded-tl-lg">
              Date
            </th>
            <th class="text-muted px-4 py-2.5 text-left font-medium">Article</th>
            <th class="text-muted px-4 py-2.5 text-left font-medium">Canal</th>
            <th class="text-muted px-4 py-2.5 text-right font-medium">Achat</th>
            <th class="text-muted px-4 py-2.5 text-right font-medium">Prix affiché</th>
            <th class="text-muted px-4 py-2.5 text-right font-medium">Prix réalisé</th>
            <th class="text-muted px-4 py-2.5 text-right font-medium">Marge</th>
            <th class="border-default w-12 border-r px-2 py-2.5 last:rounded-tr-lg" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in sortedSales"
            :key="r.article_id"
            class="border-default hover:bg-elevated/30 border-b transition-colors last:border-b-0"
          >
            <td class="text-muted border-default border-l px-4 py-2.5 whitespace-nowrap">
              {{ formatDate(r.sold_at) }}
            </td>
            <td class="max-w-[280px] px-4 py-2.5">
              <span class="text-highlighted block truncate font-medium">{{ r.title }}</span>
            </td>
            <td class="px-4 py-2.5">
              <span
                v-if="r.sale_source && SOURCE_STYLES[r.sale_source]"
                class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                :style="{
                  backgroundColor: SOURCE_STYLES[r.sale_source].bg,
                  color: SOURCE_STYLES[r.sale_source].text,
                }"
              >
                {{ SOURCE_STYLES[r.sale_source].label }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-4 py-2.5 text-right tabular-nums">
              {{ eur.format(r.purchase_price_eur) }}
            </td>
            <td class="text-muted px-4 py-2.5 text-right tabular-nums">
              {{ r.listing_price_eur != null ? eur.format(r.listing_price_eur) : '—' }}
            </td>
            <td class="px-4 py-2.5 text-right font-medium tabular-nums">
              {{ r.realized_price_eur != null ? eur.format(r.realized_price_eur) : '—' }}
            </td>
            <td class="text-primary px-4 py-2.5 text-right font-semibold tabular-nums">
              {{ eur.format(r.profit_eur) }}
            </td>
            <td class="border-default border-r px-2 py-2 text-center">
              <UButton
                :to="`/articles/${r.article_id}`"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-external-link"
                square
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="text-muted px-4 py-8 text-center text-sm">{{ emptyMessage }}</p>
  </UCard>
</template>

<script setup lang="ts">
import type { RecentSaleRow } from '~/composables/useStats'

const props = withDefaults(
  defineProps<{
    sales: RecentSaleRow[]
    title?: string
    subtitle?: string
    emptyMessage?: string
    maxHeightClass?: string
  }>(),
  {
    title: 'Dernières ventes',
    subtitle: 'Les transactions les plus récentes en premier',
    emptyMessage: "Aucune vente pour l'instant.",
    maxHeightClass: 'max-h-96 overflow-auto',
  },
)

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const sortedSales = computed(() =>
  [...props.sales].sort((a, b) => {
    const ta = a.sold_at ? new Date(a.sold_at).getTime() : 0
    const tb = b.sold_at ? new Date(b.sold_at).getTime() : 0
    return tb - ta
  }),
)

/**
 * Format an ISO timestamp for the sales table (French locale).
 * @param raw - `sold_at` from API or null
 * @returns {string} Localized date/time or em dash
 */
function formatDate(raw: string | null): string {
  if (!raw) {
    return '—'
  }
  return new Date(raw).toLocaleString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const SOURCE_STYLES: Record<'vinted' | 'ebay', { label: string; bg: string; text: string }> = {
  vinted: { label: 'Vinted', bg: 'rgb(0, 131, 143)', text: '#fff' },
  ebay: { label: 'eBay', bg: 'rgb(134, 184, 23)', text: '#fff' },
}
</script>
