<script setup lang="ts">
import { parse, format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisAxis, VisArea, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { DashboardStats } from '~/composables/useStats'

const props = defineProps<{
  stats: DashboardStats | null
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
})

/** Au moins 2 points pour tracer un segment ; point bas à 0 pour le cumul. */
const chartData = computed(() => {
  const t = props.stats?.revenue_timeline ?? []
  if (!t.length) {
    return [] as Array<{
      x: number
      label: string
      cumulative: number
      month: number
    }>
  }
  if (t.length === 1) {
    const row = t[0]!
    const d = parse(`${row.month}-01`, 'yyyy-MM-dd', new Date())
    const label = format(d, 'MMM yyyy', { locale: fr })
    const cum = row.revenue_cumulative_eur
    return [
      { x: 0, label: '', cumulative: 0, month: 0 },
      { x: 1, label, cumulative: cum, month: row.revenue_month_eur }
    ]
  }
  return t.map((row, i) => {
    const d = parse(`${row.month}-01`, 'yyyy-MM-dd', new Date())
    return {
      x: i,
      label: format(d, 'MMM yyyy', { locale: fr }),
      cumulative: row.revenue_cumulative_eur,
      month: row.revenue_month_eur
    }
  })
})

const x = (d: { x: number }) => d.x
const y = (d: { cumulative: number }) => d.cumulative

const totalCa = computed(
  () => chartData.value[chartData.value.length - 1]?.cumulative ?? 0
)

const yMax = computed(() => {
  const vals = chartData.value.map((d) => d.cumulative)
  const m = vals.length ? Math.max(...vals) : 0
  return Math.max(Math.ceil(m * 1.12), 5)
})

const yDomain = computed((): [number, number] => [0, yMax.value])

const formatTick = (i: number) => chartData.value[i]?.label ?? ''

const template = (d: {
  label: string
  cumulative: number
  month: number
}) =>
  `${d.label || 'Début'} — CA cumulé : ${eur.format(d.cumulative)}` +
  (d.month > 0 ? ` (+${eur.format(d.month)} ce mois)` : '')
</script>

<template>
  <UCard
    :ui="{
      root: 'overflow-visible',
      header: 'px-4 sm:px-6 pt-6 pb-3 border-b border-default/60',
      body: 'px-4 sm:px-6 pb-6 pt-4'
    }"
  >
    <template #header>
      <div>
        <p class="text-xs text-muted uppercase mb-1.5">
          Chiffre d'affaires (ventes)
        </p>
        <p class="text-3xl text-highlighted font-semibold">
          {{ eur.format(totalCa) }}
        </p>
        <p class="text-xs text-muted mt-1">
          Cumul depuis la première vente enregistrée
        </p>
      </div>
    </template>

    <div
      v-if="chartData.length"
      class="w-full min-w-0 min-h-96"
    >
      <VisXYContainer
        :data="chartData"
        :y-domain="yDomain"
        :prevent-empty-domain="true"
        :padding="{ top: 24, left: 52, right: 16, bottom: 36 }"
        class="h-96 w-full unovis-xy-container"
      >
        <VisLine
          :x="x"
          :y="y"
          color="var(--ui-primary)"
        />
        <VisArea
          :x="x"
          :y="y"
          color="var(--ui-primary)"
          :opacity="0.12"
        />
        <VisAxis
          type="x"
          :x="x"
          :tick-format="formatTick"
        />
        <VisAxis
          type="y"
          :y="y"
          :tick-format="(v: number) => eur.format(v)"
        />
        <VisCrosshair
          color="var(--ui-primary)"
          :template="template"
        />
        <VisTooltip />
      </VisXYContainer>
    </div>
    <p v-else class="text-sm text-muted py-12 text-center">
      Aucune vente enregistrée — le graphique apparaîtra après vos premières ventes.
    </p>
  </UCard>
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
