<template>
  <div ref="chartRef" class="w-full space-y-2">
    <div v-if="allData.length >= 2" class="flex flex-wrap gap-1">
      <button
        v-for="range in RANGES"
        :key="range.key"
        type="button"
        class="rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors"
        :class="
          selectedRangeKey === range.key
            ? 'bg-(--app-accent) text-white'
            : 'text-(--app-ink-soft) hover:bg-(--app-surface-2)'
        "
        @click="selectedRangeKey = range.key"
      >
        {{ range.label }}
      </button>
    </div>

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
      <p class="text-xs">
        {{
          allData.length >= 2 ? 'Aucun point sur cette période.' : "L'historique du prix se construit jour après jour."
        }}
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisArea, VisAxis, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { ComputedRef, PropType, Ref } from 'vue'
import type { GoupixPriceHistoryPoint } from '~/types/PriceHistory'

interface PriceHistoryDatum {
  date: Date
  price: number
}

interface PriceHistoryRange {
  key: string
  label: string
  days: number | null
}

/**
 * Mini-courbe d'évolution du prix marché (partagée cartes / produits scellés),
 * avec sélecteurs de période façon Pikacheck (7 j, 1 mois, 3 mois, 6 mois, Tout).
 */
const props = defineProps({
  points: {
    type: Array as PropType<GoupixPriceHistoryPoint[]>,
    required: true,
  },
})

const RANGES: PriceHistoryRange[] = [
  { key: '7d', label: '7 j', days: 7 },
  { key: '1m', label: '1 mois', days: 30 },
  { key: '3m', label: '3 mois', days: 90 },
  { key: '6m', label: '6 mois', days: 180 },
  { key: 'all', label: 'Tout', days: null },
]

const chartRef = useTemplateRef<HTMLElement | null>('chartRef')
const { width } = useElementSize(chartRef)
const selectedRangeKey: Ref<string> = ref('1m')

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const allData: ComputedRef<PriceHistoryDatum[]> = computed(() =>
  props.points.map((p) => ({ date: new Date(p.date), price: p.price_eur })),
)

const data: ComputedRef<PriceHistoryDatum[]> = computed(() => {
  const range = RANGES.find((r) => r.key === selectedRangeKey.value)
  if (!range || range.days == null) {
    return allData.value
  }
  const cutoff = Date.now() - range.days * 24 * 60 * 60 * 1000
  return allData.value.filter((d) => d.date.getTime() >= cutoff)
})

const x = (_: PriceHistoryDatum, i: number): number => i
const y = (d: PriceHistoryDatum): number => d.price

const xTicks = (i: number): string => {
  const record = data.value[i]
  if (!record || (i !== 0 && i !== data.value.length - 1)) {
    return ''
  }
  return format(record.date, 'd MMM', { locale: fr })
}

const yTicks = (value: number): string => eur.format(value)

const template = (d: PriceHistoryDatum): string =>
  `${format(d.date, 'd MMM yyyy', { locale: fr })} — ${eur.format(d.price)}`
</script>
