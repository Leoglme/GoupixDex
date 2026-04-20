<script setup lang="ts">
import type { MarketStats } from '~/composables/useMarketSearch'

const props = defineProps<{
  stats: MarketStats
  totalMatches: number
  periodDays: number
  outliersExcluded?: number
  effectiveQuery?: string
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

function formatPrice(value: number | null | undefined): string {
  if (value == null) {
    return '—'
  }
  return eur.format(value)
}

type StatCard = {
  label: string
  value: string
  icon: string
  description: string
  accent: string
}

const cards = computed<StatCard[]>(() => [
  {
    label: 'Prix minimum',
    value: formatPrice(props.stats.min),
    icon: 'i-lucide-arrow-down-right',
    description: "L'annonce active la moins chère",
    accent: 'text-emerald-500'
  },
  {
    label: 'Médiane',
    value: formatPrice(props.stats.median),
    icon: 'i-lucide-activity',
    description: 'Prix médian des résultats',
    accent: 'text-primary'
  },
  {
    label: 'Moyenne',
    value: formatPrice(props.stats.avg),
    icon: 'i-lucide-sigma',
    description: 'Moyenne arithmétique',
    accent: 'text-indigo-500'
  },
  {
    label: 'Prix maximum',
    value: formatPrice(props.stats.max),
    icon: 'i-lucide-arrow-up-right',
    description: "L'annonce active la plus chère",
    accent: 'text-rose-500'
  }
])
</script>

<template>
  <section class="space-y-3">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="text-sm font-medium text-highlighted">
          Aperçu du marché
        </p>
        <p class="text-xs text-muted">
          Basé sur <span class="font-medium text-highlighted">{{ stats.count }}</span>
          annonce<span v-if="stats.count > 1">s</span> analysée<span v-if="stats.count > 1">s</span>
          <span v-if="totalMatches > stats.count">
            (sur {{ totalMatches.toLocaleString('fr-FR') }} résultat<span v-if="totalMatches > 1">s</span>)
          </span>
          — annonces publiées sur les {{ periodDays }} dernier<span v-if="periodDays > 1">s</span> jour<span v-if="periodDays > 1">s</span>.
        </p>
        <p
          v-if="outliersExcluded && outliersExcluded > 0"
          class="mt-1 inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
        >
          <UIcon name="i-lucide-filter-x" class="size-3.5" />
          <span>
            {{ outliersExcluded }} annonce<span v-if="outliersExcluded > 1">s</span>
            hors-marché exclue<span v-if="outliersExcluded > 1">s</span> du calcul
          </span>
        </p>
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <UCard
        v-for="card in cards"
        :key="card.label"
        :ui="{ body: 'p-4 sm:p-5' }"
        class="ring-1 ring-default/60"
      >
        <div class="flex items-center gap-3">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-elevated/80"
          >
            <UIcon :name="card.icon" :class="['size-5', card.accent]" />
          </div>
          <div class="min-w-0 space-y-0.5">
            <p class="text-xs font-medium uppercase tracking-wide text-muted">
              {{ card.label }}
            </p>
            <p class="text-lg sm:text-xl font-semibold text-highlighted tabular-nums">
              {{ card.value }}
            </p>
          </div>
        </div>
        <p class="mt-2 text-xs text-muted leading-relaxed">
          {{ card.description }}
        </p>
      </UCard>
    </div>
  </section>
</template>
