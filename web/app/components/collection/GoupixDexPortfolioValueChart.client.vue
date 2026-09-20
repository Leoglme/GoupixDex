<template>
  <div ref="chartRef" class="w-full">
    <VisXYContainer
      v-if="data.length"
      :data="data"
      :padding="{ top: 20 }"
      class="unovis-xy-container h-80"
      :width="width"
    >
      <VisArea :x="x" :y="marketY" color="var(--ui-primary)" :opacity="0.1" />
      <VisLine :x="x" :y="marketY" color="var(--ui-primary)" />
      <VisLine :x="x" :y="purchaseY" color="var(--app-ink-soft)" :line-dash-array="[4, 4]" />

      <VisAxis type="x" :x="x" :tick-format="xTicks" />
      <VisAxis type="y" :tick-format="yTicks" />

      <VisCrosshair color="var(--ui-primary)" :template="template" />
      <VisTooltip />
    </VisXYContainer>
    <p v-else class="text-muted py-16 text-center text-sm">
      Pas encore d'historique : le premier point apparaîtra après la valorisation de cette nuit.
    </p>
  </div>
</template>

<script lang="ts" setup>
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisArea, VisAxis, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { ComputedRef, PropType } from 'vue'
import type { PortfolioPeriod, PortfolioTimelinePoint } from '~/composables/usePortfolio'
import type { GoupixDexPortfolioValueChartProps } from '~/types/GoupixDexPortfolioValueChart'

interface PortfolioChartRecord {
  date: Date
  market: number
  purchase: number
}

/**
 * Courbes d'évolution de la valeur du portefeuille (marché plein, achat en pointillés).
 */
const props: GoupixDexPortfolioValueChartProps = defineProps({
  points: {
    type: Array as PropType<PortfolioTimelinePoint[]>,
    required: true,
  },
  period: {
    type: String as PropType<PortfolioPeriod>,
    required: true,
  },
})

const chartRef = useTemplateRef<HTMLElement | null>('chartRef')
const { width } = useElementSize(chartRef)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const data: ComputedRef<PortfolioChartRecord[]> = computed(() =>
  props.points.map((p) => ({
    date: new Date(p.date),
    market: p.market_eur,
    purchase: p.purchase_eur,
  })),
)

const x = (_: PortfolioChartRecord, i: number): number => i
const marketY = (d: PortfolioChartRecord): number => d.market
const purchaseY = (d: PortfolioChartRecord): number => d.purchase

/**
 * Formate une date selon la granularité de la période.
 * @param date - Date du point.
 * @returns Libellé court (jour ou mois selon la période).
 */
function formatDate(date: Date): string {
  if (props.period === '6m' || props.period === 'tout') {
    return format(date, 'LLL yyyy', { locale: fr })
  }
  return format(date, 'd MMM', { locale: fr })
}

const xTicks = (i: number): string => {
  const record = data.value[i]
  if (!record || i === 0 || i === data.value.length - 1) {
    return ''
  }
  return formatDate(record.date)
}

const yTicks = (value: number): string => eur.format(value)

const template = (d: PortfolioChartRecord): string =>
  `${formatDate(d.date)} — marché ${eur.format(d.market)} · achat ${eur.format(d.purchase)}`
</script>
