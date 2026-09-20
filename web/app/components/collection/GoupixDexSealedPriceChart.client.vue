<template>
  <div ref="chartRef" class="w-full">
    <VisXYContainer
      v-if="data.length >= 2"
      :data="data"
      :padding="{ top: 8 }"
      class="unovis-xy-container h-40"
      :width="width"
    >
      <VisArea :x="x" :y="y" color="var(--ui-primary)" :opacity="0.12" />
      <VisLine :x="x" :y="y" color="var(--ui-primary)" />
      <VisAxis type="x" :x="x" :tick-format="xTicks" :grid-line="false" />
      <VisAxis type="y" :tick-format="yTicks" :num-ticks="3" :grid-line="false" />
      <VisCrosshair color="var(--ui-primary)" :template="template" />
      <VisTooltip />
    </VisXYContainer>

    <div
      v-else
      class="border-default text-muted flex h-40 flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed text-center"
    >
      <UIcon name="i-lucide-line-chart" class="size-6" />
      <p class="text-xs">L'historique du prix se construit jour après jour.</p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisArea, VisAxis, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { ComputedRef, PropType } from 'vue'
import type { SealedPriceHistoryPoint } from '~/composables/useSealed'

interface SealedPricePoint {
  date: Date
  price: number
}

/**
 * Mini-courbe d'évolution du prix marché d'un produit scellé.
 */
const props = defineProps({
  points: {
    type: Array as PropType<SealedPriceHistoryPoint[]>,
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

const data: ComputedRef<SealedPricePoint[]> = computed(() =>
  props.points.map((p) => ({ date: new Date(p.date), price: p.price_eur })),
)

const x = (_: SealedPricePoint, i: number): number => i
const y = (d: SealedPricePoint): number => d.price

const xTicks = (i: number): string => {
  const record = data.value[i]
  if (!record || (i !== 0 && i !== data.value.length - 1)) {
    return ''
  }
  return format(record.date, 'd MMM', { locale: fr })
}

const yTicks = (value: number): string => eur.format(value)

const template = (d: SealedPricePoint): string =>
  `${format(d.date, 'd MMM yyyy', { locale: fr })} — ${eur.format(d.price)}`
</script>
