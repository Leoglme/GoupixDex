<template>
  <UCard :ui="{ body: 'p-4' }" class="min-w-0">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
      <h2 class="text-highlighted text-sm font-semibold">
        Évolution des ventes
        <span class="text-muted font-normal">· {{ GRANULARITY_LABELS[props.period] }}</span>
      </h2>
      <div class="text-muted flex items-center gap-3.5 text-xs">
        <span class="flex items-center gap-1.5">
          <span class="size-2.5 rounded-sm bg-(--app-accent)/30" />
          Chiffre d'affaires
        </span>
        <span class="flex items-center gap-1.5">
          <span class="size-2.5 rounded-sm bg-(--app-accent)" />
          Bénéfice
        </span>
      </div>
    </div>

    <template v-if="hasSales">
      <div class="flex h-44 gap-2 sm:h-52">
        <div class="text-muted flex w-11 shrink-0 flex-col justify-between text-right text-[11px] tabular-nums">
          <span class="-translate-y-1/2">{{ roundedEuroFormatter.format(axisMaximum) }}</span>
          <span>{{ roundedEuroFormatter.format(axisMaximum / 2) }}</span>
          <span class="translate-y-1/2">{{ roundedEuroFormatter.format(0) }}</span>
        </div>
        <div class="relative min-w-0 flex-1" @pointerleave="hideBarDetail">
          <div class="absolute inset-x-0 top-0 border-t border-dashed border-(--app-line)" />
          <div class="absolute inset-x-0 top-1/2 border-t border-dashed border-(--app-line)" />
          <div class="absolute inset-x-0 bottom-0 border-t border-(--app-line)" />
          <div class="absolute inset-0 flex items-end" :class="bars.length > 20 ? 'gap-px sm:gap-0.5' : 'gap-1.5'">
            <div
              v-for="(bar, index) in bars"
              :key="bar.date"
              class="flex h-full min-w-0 flex-1 items-end justify-center"
              @pointerenter="hoveredBarIndex = index"
            >
              <div
                class="relative w-3/4 max-w-10 rounded-t-sm transition-colors"
                :class="hoveredBarIndex === index ? 'bg-(--app-accent)/45' : 'bg-(--app-accent)/30'"
                :style="{ height: bar.revenueHeight }"
              >
                <div
                  class="absolute inset-x-0 bottom-0 rounded-t-sm bg-(--app-accent)"
                  :style="{ height: bar.profitHeight }"
                />
              </div>
            </div>
          </div>
          <p
            v-if="hoveredBar"
            class="pointer-events-none absolute top-0 z-10 rounded-md border border-(--app-line) bg-(--app-surface) px-2 py-1 text-xs whitespace-nowrap shadow-sm"
            :class="tooltipAlignClass"
            :style="{ left: tooltipLeft }"
          >
            <span class="font-semibold text-(--app-ink)">{{ hoveredBar.label }}</span>
            <span class="text-muted"> · {{ hoveredBar.detail }}</span>
          </p>
        </div>
      </div>
      <div class="text-muted mt-2 flex justify-between pl-13 text-[11px]">
        <span v-for="tick in ticks" :key="tick.date" :class="{ 'max-sm:hidden': tick.isHiddenOnMobile }">
          {{ tick.label }}
        </span>
      </div>
    </template>
    <p v-else class="text-muted py-16 text-center text-sm">Aucune vente sur cette période.</p>
  </UCard>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import type { DashboardPeriod, SalesTimelinePoint } from '~/composables/useStats'
import type {
  GoupixDexDashboardSalesChartProps,
  SalesChartBar,
  SalesChartTick,
} from '~/types/GoupixDexDashboardSalesChart'

const props: GoupixDexDashboardSalesChartProps = defineProps({
  points: {
    type: Array as PropType<SalesTimelinePoint[]>,
    required: true,
  },
  period: {
    type: String as PropType<DashboardPeriod>,
    required: true,
  },
})

const GRANULARITY_LABELS: Record<DashboardPeriod, string> = {
  daily: 'par jour',
  weekly: 'par semaine',
  monthly: 'par mois',
}

const roundedEuroFormatter: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const dayFormatter: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })

const monthFormatter: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', { month: 'short', year: '2-digit' })

const hoveredBarIndex: Ref<number | null> = ref(null)

const hasSales: ComputedRef<boolean> = computed((): boolean =>
  props.points.some((point: SalesTimelinePoint): boolean => point.sales_count > 0),
)

const axisMaximum: ComputedRef<number> = computed((): number =>
  computeRoundedAxisMaximum(Math.max(0, ...props.points.map((point: SalesTimelinePoint): number => point.revenue_eur))),
)

const bars: ComputedRef<SalesChartBar[]> = computed((): SalesChartBar[] =>
  props.points.map((point: SalesTimelinePoint): SalesChartBar => {
    const profitShare: number =
      point.revenue_eur > 0 ? Math.min(1, Math.max(0, point.profit_eur / point.revenue_eur)) : 0

    return {
      date: point.date,
      label: buildBucketLabel(point.date),
      revenueHeight: `${(Math.max(0, point.revenue_eur) / axisMaximum.value) * 100}%`,
      profitHeight: `${profitShare * 100}%`,
      detail: buildBucketDetail(point),
    }
  }),
)

const hoveredBar: ComputedRef<SalesChartBar | null> = computed((): SalesChartBar | null =>
  hoveredBarIndex.value === null ? null : (bars.value[hoveredBarIndex.value] ?? null),
)

const tooltipLeft: ComputedRef<string> = computed(
  (): string => `${(((hoveredBarIndex.value ?? 0) + 0.5) / Math.max(1, bars.value.length)) * 100}%`,
)

const tooltipAlignClass: ComputedRef<string> = computed((): string => {
  const position: number = ((hoveredBarIndex.value ?? 0) + 0.5) / Math.max(1, bars.value.length)

  if (position < 0.25) {
    return ''
  }
  return position > 0.75 ? '-translate-x-full' : '-translate-x-1/2'
})

const ticks: ComputedRef<SalesChartTick[]> = computed((): SalesChartTick[] => {
  const lastIndex: number = bars.value.length - 1
  const tickIndexes: number[] =
    bars.value.length <= 5
      ? [...bars.value.keys()]
      : [0, Math.round(lastIndex * 0.25), Math.round(lastIndex * 0.5), Math.round(lastIndex * 0.75), lastIndex]

  return tickIndexes.flatMap((barIndex: number, position: number): SalesChartTick[] => {
    const bar: SalesChartBar | undefined = bars.value[barIndex]
    return bar ? [{ date: bar.date, label: bar.label, isHiddenOnMobile: position % 2 === 1 }] : []
  })
})

/**
 * Plafond arrondi de l'axe (90 €, 150 €, 2 500 €…) pour des graduations lisibles.
 * @param {number} highestRevenue - Chiffre d'affaires de la meilleure tranche.
 * @returns {number} Le haut de l'axe, au moins 10 €.
 */
function computeRoundedAxisMaximum(highestRevenue: number): number {
  if (highestRevenue <= 0) {
    return 10
  }

  const step: number = Math.max(5, 10 ** Math.floor(Math.log10(highestRevenue)) / 2)
  return Math.ceil(highestRevenue / step) * step
}

/**
 * Libellé d'une tranche : le jour pour les jours et semaines, le mois sinon.
 * @param {string} isoDate - Début de la tranche.
 * @returns {string} « 2 oct. » ou « oct. 26 ».
 */
function buildBucketLabel(isoDate: string): string {
  const date: Date = new Date(isoDate)
  return props.period === 'monthly' ? monthFormatter.format(date) : dayFormatter.format(date)
}

/**
 * Détail d'une tranche affiché au survol : chiffre d'affaires, bénéfice et nombre de ventes.
 * @param {SalesTimelinePoint} point - Tranche survolée.
 * @returns {string} Le détail, ou « aucune vente ».
 */
function buildBucketDetail(point: SalesTimelinePoint): string {
  if (point.sales_count === 0) {
    return 'aucune vente'
  }

  const profitSign: string = point.profit_eur > 0 ? '+' : ''
  const salesLabel: string = `${point.sales_count} vente${point.sales_count > 1 ? 's' : ''}`
  return `${roundedEuroFormatter.format(point.revenue_eur)} · ${profitSign}${roundedEuroFormatter.format(point.profit_eur)} de bénéfice · ${salesLabel}`
}

/**
 * Masque le détail quand la souris quitte la courbe (au doigt, il reste affiché jusqu'au prochain bâton touché).
 * @param {PointerEvent} event - Sortie du pointeur.
 * @returns {void}
 */
function hideBarDetail(event: PointerEvent): void {
  if (event.pointerType === 'mouse') {
    hoveredBarIndex.value = null
  }
}
</script>
