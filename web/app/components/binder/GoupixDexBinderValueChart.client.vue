<template>
  <div ref="chartRef" class="w-full">
    <VisXYContainer
      v-if="data.length"
      :data="data"
      :padding="{ top: 20 }"
      class="unovis-xy-container h-72"
      :width="width"
    >
      <VisArea :x="x" :y="marketY" color="var(--ui-primary)" :opacity="0.1" />
      <VisLine :x="x" :y="marketY" color="var(--ui-primary)" />
      <VisLine :x="x" :y="ownedY" color="var(--app-green)" />

      <VisAxis type="x" :x="x" :tick-format="xTicks" />
      <VisAxis type="y" :tick-format="yTicks" />

      <VisCrosshair color="var(--ui-primary)" :template="template" />
      <VisTooltip />
    </VisXYContainer>
    <p v-else class="text-muted py-16 text-center text-sm">
      Pas encore d'historique : la courbe se remplit à mesure que les cartes sont valorisées.
    </p>
  </div>
</template>

<script lang="ts" setup>
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisArea, VisAxis, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { ComputedRef, PropType } from 'vue'
import type { BinderValuePeriod, BinderValueTimelinePoint } from '~/types/binders'
import type { GoupixDexBinderValueChartProps } from '~/types/GoupixDexBinderValueChart'

interface BinderChartRecord {
  date: Date
  market: number
  owned: number
}

/**
 * Courbes d'évolution de la valeur d'un classeur : valeur totale (marché plein)
 * et valeur possédée.
 */
const props: GoupixDexBinderValueChartProps = defineProps({
  points: {
    type: Array as PropType<BinderValueTimelinePoint[]>,
    required: true,
  },
  period: {
    type: String as PropType<BinderValuePeriod>,
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

const data: ComputedRef<BinderChartRecord[]> = computed(() =>
  props.points.map((point) => ({
    date: new Date(point.date),
    market: point.market_eur,
    owned: point.owned_eur,
  })),
)

const x = (_: BinderChartRecord, index: number): number => index
const marketY = (record: BinderChartRecord): number => record.market
const ownedY = (record: BinderChartRecord): number => record.owned

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

const xTicks = (index: number): string => {
  const record = data.value[index]
  if (!record || index === 0 || index === data.value.length - 1) {
    return ''
  }
  return formatDate(record.date)
}

const yTicks = (value: number): string => eur.format(value)

const template = (record: BinderChartRecord): string =>
  `${formatDate(record.date)} — total ${eur.format(record.market)} · possédé ${eur.format(record.owned)}`
</script>
