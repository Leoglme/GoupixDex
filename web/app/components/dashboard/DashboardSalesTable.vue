<script setup lang="ts">
import type { RecentSaleRow } from '~/composables/useStats'

defineProps<{
  sales: RecentSaleRow[]
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

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
      v-if="sales.length"
      class="overflow-x-auto"
    >
      <table class="w-full text-sm border-separate border-spacing-0">
        <thead>
          <tr class="bg-elevated/50 border-y border-default">
            <th class="text-left font-medium text-muted py-2.5 px-4 first:rounded-tl-lg border-l border-default">
              Date
            </th>
            <th class="text-left font-medium text-muted py-2.5 px-4">
              Carte
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Achat
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Vente
            </th>
            <th class="text-right font-medium text-muted py-2.5 px-4">
              Marge
            </th>
            <th class="w-12 py-2.5 px-2 last:rounded-tr-lg border-r border-default" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in sales"
            :key="r.article_id"
            class="border-b border-default last:border-b-0 hover:bg-elevated/30 transition-colors"
          >
            <td class="py-2.5 px-4 text-muted whitespace-nowrap border-l border-default">
              {{ formatDate(r.sold_at) }}
            </td>
            <td class="py-2.5 px-4 max-w-[200px]">
              <span class="truncate block font-medium text-highlighted">{{ r.pokemon_name || r.title }}</span>
            </td>
            <td class="py-2.5 px-4 text-right tabular-nums">
              {{ eur.format(r.purchase_price_eur) }}
            </td>
            <td class="py-2.5 px-4 text-right tabular-nums font-medium">
              {{ r.sell_price_eur != null ? eur.format(r.sell_price_eur) : '—' }}
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
