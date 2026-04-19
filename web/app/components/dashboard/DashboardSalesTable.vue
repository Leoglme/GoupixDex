<script setup lang="ts">
import type { RecentSaleRow } from '~/composables/useStats'

const props = defineProps<{
  sales: RecentSaleRow[]
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

const sortedSales = computed(() =>
  [...props.sales].sort((a, b) => {
    const ta = a.sold_at ? new Date(a.sold_at).getTime() : 0
    const tb = b.sold_at ? new Date(b.sold_at).getTime() : 0
    return tb - ta
  })
)

function formatDate(raw: string | null) {
  if (!raw) {
    return '—'
  }
  return new Date(raw).toLocaleString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const SOURCE_STYLES: Record<'vinted' | 'ebay', { label: string, bg: string, text: string }> = {
  vinted: { label: 'Vinted', bg: 'rgb(0, 131, 143)', text: '#fff' },
  ebay: { label: 'eBay', bg: 'rgb(134, 184, 23)', text: '#fff' }
}
</script>

<template>
  <UCard
    :ui="{
      header: 'px-4 sm:px-6 pt-6 pb-3 border-b border-default/60',
      body: 'p-0 sm:p-0'
    }"
  >
    <template #header>
      <div>
        <p class="text-sm font-medium text-highlighted">
          Dernières ventes
        </p>
        <p class="text-xs text-muted">
          Les transactions les plus récentes en premier
        </p>
      </div>
    </template>

    <div
      v-if="sortedSales.length"
      class="max-h-96 overflow-auto"
    >
      <table class="w-full text-sm border-separate border-spacing-0">
        <thead class="sticky top-0 z-10">
          <tr class="bg-elevated/95 backdrop-blur border-y border-default">
            <th class="text-left font-medium text-muted py-2.5 px-4 first:rounded-tl-lg border-l border-default">
              Date
            </th>
            <th class="text-left font-medium text-muted py-2.5 px-4">
              Article
            </th>
            <th class="text-left font-medium text-muted py-2.5 px-4">
              Canal
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Achat
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Prix affiché
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Prix réalisé
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Marge
            </th>
            <th class="w-12 py-2.5 px-2 last:rounded-tr-lg border-r border-default" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in sortedSales"
            :key="r.article_id"
            class="border-b border-default last:border-b-0 hover:bg-elevated/30 transition-colors"
          >
            <td class="py-2.5 px-4 text-muted whitespace-nowrap border-l border-default">
              {{ formatDate(r.sold_at) }}
            </td>
            <td class="py-2.5 px-4 max-w-[280px]">
              <span class="truncate block font-medium text-highlighted">{{ r.title }}</span>
            </td>
            <td class="py-2.5 px-4">
              <span
                v-if="r.sale_source && SOURCE_STYLES[r.sale_source]"
                class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                :style="{
                  backgroundColor: SOURCE_STYLES[r.sale_source].bg,
                  color: SOURCE_STYLES[r.sale_source].text
                }"
              >
                {{ SOURCE_STYLES[r.sale_source].label }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="py-2.5 px-4 text-right tabular-nums">
              {{ eur.format(r.purchase_price_eur) }}
            </td>
            <td class="py-2.5 px-4 text-right tabular-nums text-muted">
              {{ r.listing_price_eur != null ? eur.format(r.listing_price_eur) : '—' }}
            </td>
            <td class="py-2.5 px-4 text-right tabular-nums font-medium">
              {{ r.realized_price_eur != null ? eur.format(r.realized_price_eur) : '—' }}
            </td>
            <td class="py-2.5 px-4 text-right tabular-nums font-semibold text-primary">
              {{ eur.format(r.profit_eur) }}
            </td>
            <td class="py-2 px-2 text-center border-r border-default">
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
    <p v-else class="text-sm text-muted px-4 py-8 text-center">
      Aucune vente pour l'instant.
    </p>
  </UCard>
</template>
