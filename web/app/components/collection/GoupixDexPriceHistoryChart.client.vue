<template>
  <div ref="chartRef" class="w-full space-y-2">
    <div v-if="visibleRanges.length > 1 || periodChange" class="flex flex-wrap items-center justify-between gap-2">
      <div v-if="visibleRanges.length > 1" class="flex flex-wrap gap-1">
        <button
          v-for="range in visibleRanges"
          :key="range.key"
          type="button"
          class="rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors"
          :class="
            currentRange?.key === range.key
              ? 'bg-(--app-accent) text-white'
              : 'text-(--app-ink-soft) hover:bg-(--app-surface-2)'
          "
          @click="selectedRangeKey = range.key"
        >
          {{ range.label }}
        </button>
      </div>

      <p
        v-if="periodChange"
        class="ml-auto flex items-center gap-1 text-[11px] font-medium tabular-nums"
        :class="PERIOD_CHANGE_COLOR_CLASSES[periodChangeDirection]"
        :title="periodChangeTitle"
      >
        <UIcon :name="PERIOD_CHANGE_ICONS[periodChangeDirection]" class="size-3.5" />
        <span>{{ periodChangeLabel }}</span>
      </p>
    </div>

    <VisXYContainer
      v-if="data.length >= 2"
      :data="data"
      :padding="{ top: 8 }"
      :y-domain="yDomain"
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
import type { ComputedRef, PropType, Ref } from 'vue'
import type {
  GoupixDexPriceHistoryChartPeriodChange,
  GoupixDexPriceHistoryChartPeriodChangeDirection,
  GoupixDexPriceHistoryChartProps,
  GoupixDexPriceHistoryChartRange,
  GoupixDexPriceHistoryChartRecord,
} from '~/types/GoupixDexPriceHistoryChart'
import type { GoupixPriceHistoryPoint } from '~/types/PriceHistory'
import { differenceInCalendarDays, format, startOfToday, subDays } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisArea, VisAxis, VisCrosshair, VisTooltip } from '@unovis/vue'

/**
 * Mini-courbe d'évolution du prix marché (partagée cartes / produits scellés).
 * Les périodes (7 j, 1 mois, 3 mois, 6 mois, Tout) façon Pikacheck n'apparaissent
 * que quand l'historique réel les couvre — elles se révèlent au fil des snapshots.
 */
const props: GoupixDexPriceHistoryChartProps = defineProps({
  points: {
    type: Array as PropType<GoupixPriceHistoryPoint[]>,
    required: true,
  },
})

const chartRef = useTemplateRef<HTMLElement | null>('chartRef')
const { width } = useElementSize(chartRef)

const Y_DOMAIN_MARGIN_RATIO: number = 0.2
const Y_DOMAIN_MIN_MARGIN_PRICE_RATIO: number = 0.02
const Y_DOMAIN_MIN_MARGIN_EUR: number = 0.05
const FLAT_CHANGE_THRESHOLD_EUR: number = 0.005

const FIXED_RANGES: GoupixDexPriceHistoryChartRange[] = [
  { key: '7d', label: '7 j', days: 7 },
  { key: '1m', label: '1 mois', days: 30 },
  { key: '3m', label: '3 mois', days: 90 },
  { key: '6m', label: '6 mois', days: 180 },
]
const ALL_RANGE: GoupixDexPriceHistoryChartRange = { key: 'all', label: 'Tout', days: null }

const PERIOD_CHANGE_ICONS: Record<GoupixDexPriceHistoryChartPeriodChangeDirection, string> = {
  up: 'i-lucide-trending-up',
  down: 'i-lucide-trending-down',
  flat: 'i-lucide-minus',
}
const PERIOD_CHANGE_COLOR_CLASSES: Record<GoupixDexPriceHistoryChartPeriodChangeDirection, string> = {
  up: 'text-(--app-green)',
  down: 'text-(--app-red)',
  flat: 'text-muted',
}

const eurAxisTick: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})
const eurExact: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const eurSignedChange: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  signDisplay: 'exceptZero',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const percentSignedChange: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  signDisplay: 'exceptZero',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const selectedRangeKey: Ref<string> = ref('1m')

const allData: ComputedRef<GoupixDexPriceHistoryChartRecord[]> = computed(() =>
  props.points.map(
    (point: GoupixPriceHistoryPoint): GoupixDexPriceHistoryChartRecord => ({
      // Minuit local du jour relevé : lu en UTC, le point J-30 sortait de la fenêtre « 1 mois ».
      date: new Date(`${point.date.slice(0, 10)}T00:00:00`),
      price: point.price_eur,
    }),
  ),
)

/** Étendue de l'historique en jours (0 quand il y a moins de deux points). */
const dataSpanDays: ComputedRef<number> = computed(() => {
  if (allData.value.length < 2) {
    return 0
  }
  const oldest = allData.value[0]?.date
  return oldest ? differenceInCalendarDays(startOfToday(), oldest) : 0
})

/** Périodes réellement couvertes par les données : chaque cran apparaît quand l'historique le dépasse. */
const visibleRanges: ComputedRef<GoupixDexPriceHistoryChartRange[]> = computed(() => {
  if (allData.value.length < 2) {
    return []
  }
  const span = dataSpanDays.value
  const ranges: GoupixDexPriceHistoryChartRange[] = []
  FIXED_RANGES.forEach((range: GoupixDexPriceHistoryChartRange, index: number): void => {
    const previousDays = index === 0 ? 0 : (FIXED_RANGES[index - 1]?.days ?? 0)
    if (index === 0 || span > previousDays) {
      ranges.push(range)
    }
  })
  if (span > 180) {
    ranges.push(ALL_RANGE)
  }
  return ranges
})

/** Période effective : le choix de l'utilisateur s'il est visible, sinon la plus large disponible. */
const currentRange: ComputedRef<GoupixDexPriceHistoryChartRange | null> = computed(() => {
  const ranges = visibleRanges.value
  if (ranges.length === 0) {
    return null
  }
  return (
    ranges.find((range: GoupixDexPriceHistoryChartRange): boolean => range.key === selectedRangeKey.value) ??
    ranges[ranges.length - 1] ??
    null
  )
})

const data: ComputedRef<GoupixDexPriceHistoryChartRecord[]> = computed(() => {
  const range = currentRange.value
  if (!range || range.days == null) {
    return allData.value
  }
  const cutoff = subDays(startOfToday(), range.days).getTime()
  return allData.value.filter((record: GoupixDexPriceHistoryChartRecord): boolean => record.date.getTime() >= cutoff)
})

/** Axe Y calé sur l'amplitude des prix visibles plutôt que sur 0 € : marge de 20 %, plancher à 2 % du prix max pour ne pas amplifier le bruit. */
const yDomain: ComputedRef<[number, number]> = computed(() => {
  const prices = data.value.map((record: GoupixDexPriceHistoryChartRecord): number => record.price)
  if (prices.length === 0) {
    return [0, 1]
  }
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const margin = Math.max(
    (max - min) * Y_DOMAIN_MARGIN_RATIO,
    max * Y_DOMAIN_MIN_MARGIN_PRICE_RATIO,
    Y_DOMAIN_MIN_MARGIN_EUR,
  )
  return [Math.max(0, min - margin), max + margin]
})

const periodChange: ComputedRef<GoupixDexPriceHistoryChartPeriodChange | null> = computed(() => {
  const first = data.value[0]
  const last = data.value[data.value.length - 1]
  if (data.value.length < 2 || !first || !last) {
    return null
  }
  const amountEur = last.price - first.price
  const ratio = first.price > 0 ? amountEur / first.price : null
  return { amountEur, ratio }
})

const periodChangeDirection: ComputedRef<GoupixDexPriceHistoryChartPeriodChangeDirection> = computed(() => {
  const amountEur = periodChange.value?.amountEur ?? 0
  if (Math.abs(amountEur) < FLAT_CHANGE_THRESHOLD_EUR) {
    return 'flat'
  }
  return amountEur > 0 ? 'up' : 'down'
})

const periodChangeLabel: ComputedRef<string> = computed(() => {
  const change = periodChange.value
  if (!change) {
    return ''
  }
  const amount = eurSignedChange.format(change.amountEur)
  return change.ratio != null ? `${amount} (${percentSignedChange.format(change.ratio)})` : amount
})

const periodChangeTitle: ComputedRef<string> = computed(() => {
  const first = data.value[0]
  const last = data.value[data.value.length - 1]
  if (!first || !last) {
    return ''
  }
  const from = format(first.date, 'd MMM yyyy', { locale: fr })
  const to = format(last.date, 'd MMM yyyy', { locale: fr })
  return `Variation du ${from} au ${to}`
})

const x = (_: GoupixDexPriceHistoryChartRecord, i: number): number => i
const y = (d: GoupixDexPriceHistoryChartRecord): number => d.price

const xTicks = (i: number): string => {
  const record = data.value[i]
  if (!record || (i !== 0 && i !== data.value.length - 1)) {
    return ''
  }
  return format(record.date, 'd MMM', { locale: fr })
}

const yTicks = (value: number): string => eurAxisTick.format(value)

const template = (d: GoupixDexPriceHistoryChartRecord): string =>
  `${format(d.date, 'd MMM yyyy', { locale: fr })} — ${eurExact.format(d.price)}`
</script>
