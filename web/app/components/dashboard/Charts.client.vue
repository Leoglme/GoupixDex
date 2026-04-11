<script setup lang="ts">
import { VisXYContainer, VisLine, VisAxis, VisArea, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { DashboardStats } from '~/composables/useStats'

const props = defineProps<{
  stats: DashboardStats | null
}>()

const cardRef = useTemplateRef<HTMLElement | null>('cardRef')
const { width } = useElementSize(cardRef)

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
})

const weeklyData = computed(() => {
  const w = props.stats?.weekly_sold_profit ?? []
  return w.map((d, i) => ({
    x: i,
    label: d.week,
    profit: d.profit_eur
  }))
})

const x = (d: { x: number }) => d.x
const y = (d: { profit: number }) => d.profit

const formatTick = (i: number) => weeklyData.value[i]?.label ?? ''

const template = (d: { label: string, profit: number }) =>
  `${d.label} : ${eur.format(d.profit)}`
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-2">
    <UCard
      ref="cardRef"
      :ui="{ root: 'overflow-visible', body: 'px-0! pt-0! pb-3!' }"
    >
      <template #header>
        <p class="text-xs text-muted uppercase mb-1">
          Bénéfices des ventes (par semaine)
        </p>
      </template>
      <VisXYContainer
        v-if="weeklyData.length"
        :data="weeklyData"
        class="h-72 unovis-xy-container"
        :width="width"
        :padding="{ top: 24, left: 16, right: 16 }"
      >
        <VisLine :x="x" :y="y" color="var(--ui-primary)" />
        <VisArea
          :x="x"
          :y="y"
          color="var(--ui-primary)"
          :opacity="0.12"
        />
        <VisAxis type="x" :x="x" :tick-format="formatTick" />
        <VisAxis type="y" :y="y" :tick-format="(v: number) => eur.format(v)" />
        <VisCrosshair color="var(--ui-primary)" :template="template" />
        <VisTooltip />
      </VisXYContainer>
      <p v-else class="text-sm text-muted px-4 py-8">
        Pas encore assez de ventes pour tracer le graphique.
      </p>
    </UCard>

    <UCard>
      <template #header>
        <p class="text-xs text-muted uppercase mb-1">
          Cartes les plus rentables
        </p>
      </template>
      <ul v-if="stats?.top_profitable?.length" class="divide-y divide-default">
        <li
          v-for="r in stats.top_profitable"
          :key="r.article_id"
          class="flex justify-between gap-2 py-2 text-sm"
        >
          <span class="truncate text-highlighted">{{ r.pokemon_name || r.title }}</span>
          <span class="shrink-0 font-medium text-primary">{{ eur.format(r.profit_eur) }}</span>
        </li>
      </ul>
      <p v-else class="text-sm text-muted py-4">
        Aucune vente.
      </p>
    </UCard>
  </div>
</template>

<style scoped>
.unovis-xy-container {
  --vis-crosshair-line-stroke-color: var(--ui-primary);
  --vis-crosshair-circle-stroke-color: var(--ui-bg);
  --vis-axis-grid-color: var(--ui-border);
  --vis-axis-tick-color: var(--ui-border);
  --vis-axis-tick-label-color: var(--ui-text-dimmed);
  --vis-tooltip-background-color: var(--ui-bg);
  --vis-tooltip-border-color: var(--ui-border);
  --vis-tooltip-text-color: var(--ui-text-highlighted);
}
</style>
