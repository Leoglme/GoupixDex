<script setup lang="ts">
import type { DashboardStats } from '~/composables/useStats'

defineProps<{
  stats: DashboardStats | null
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
})
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-2">
    <UCard>
      <template #header>
        <p class="text-sm font-medium text-highlighted">
          Cartes les plus rentables
        </p>
        <p class="text-xs text-muted">
          Marge par article (toutes périodes)
        </p>
      </template>
      <ul v-if="stats?.top_profitable?.length" class="divide-y divide-default">
        <li
          v-for="r in stats.top_profitable"
          :key="r.article_id"
          class="flex justify-between gap-2 py-2.5 text-sm"
        >
          <span class="truncate text-highlighted">{{ r.pokemon_name || r.title }}</span>
          <span class="shrink-0 font-semibold text-primary">{{ eur.format(r.profit_eur) }}</span>
        </li>
      </ul>
      <p v-else class="text-sm text-muted py-6 text-center">
        Aucune vente.
      </p>
    </UCard>

    <UCard>
      <template #header>
        <p class="text-sm font-medium text-highlighted">
          Ventes les plus rapides
        </p>
        <p class="text-xs text-muted">
          Délai entre mise en ligne et vente
        </p>
      </template>
      <ul v-if="stats?.fastest_sold?.length" class="divide-y divide-default">
        <li
          v-for="r in stats.fastest_sold"
          :key="r.article_id"
          class="flex justify-between gap-2 py-2.5 text-sm"
        >
          <span class="truncate">{{ r.pokemon_name || r.title }}</span>
          <span class="shrink-0 tabular-nums text-muted">{{ r.hours_to_sell }} h</span>
        </li>
      </ul>
      <p v-else class="text-sm text-muted py-6 text-center">
        Aucune vente.
      </p>
    </UCard>
  </div>
</template>
