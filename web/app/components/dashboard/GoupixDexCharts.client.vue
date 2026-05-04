<template>
  <div class="grid gap-6 lg:grid-cols-2">
    <UCard>
      <template #header>
        <p class="text-highlighted text-sm font-medium">Cartes les plus rentables</p>
        <p class="text-muted text-xs">Marge par article (toutes périodes)</p>
      </template>
      <ul v-if="stats?.top_profitable?.length" class="divide-default divide-y">
        <li v-for="r in stats.top_profitable" :key="r.article_id" class="flex justify-between gap-2 py-2.5 text-sm">
          <span class="text-highlighted truncate">{{ r.title }}</span>
          <span class="text-primary shrink-0 font-semibold">{{ eur.format(r.profit_eur) }}</span>
        </li>
      </ul>
      <p v-else class="text-muted py-6 text-center text-sm">Aucune vente.</p>
    </UCard>

    <UCard>
      <template #header>
        <p class="text-highlighted text-sm font-medium">Ventes les plus rapides</p>
        <p class="text-muted text-xs">Délai entre mise en ligne et vente</p>
      </template>
      <ul v-if="stats?.fastest_sold?.length" class="divide-default divide-y">
        <li v-for="r in stats.fastest_sold" :key="r.article_id" class="flex justify-between gap-2 py-2.5 text-sm">
          <span class="truncate">{{ r.title }}</span>
          <span class="text-muted shrink-0 tabular-nums">{{ formatTimeToSell(r.hours_to_sell) }}</span>
        </li>
      </ul>
      <p v-else class="text-muted py-6 text-center text-sm">Aucune vente.</p>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { DashboardStats } from '~/composables/useStats'

defineProps<{
  stats: DashboardStats | null
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

/**
 * Human-readable time-to-sell label from hour count.
 * @param hours - Hours between listing and sale
 * @returns {string} Short French label (hours or days)
 */
function formatTimeToSell(hours: number): string {
  if (!Number.isFinite(hours) || hours < 0) {
    return '—'
  }
  if (hours < 24) {
    const rounded = Math.max(1, Math.round(hours))
    return `${rounded} h`
  }
  const days = Math.round(hours / 24)
  return `${days} j`
}
</script>
