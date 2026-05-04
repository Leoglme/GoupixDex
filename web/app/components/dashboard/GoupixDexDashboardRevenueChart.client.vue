<template>
  <UCard ref="cardRef" :ui="{ root: 'overflow-visible', body: 'px-0! pt-0! pb-3!' }">
    <template #header>
      <div>
        <p class="text-muted mb-1.5 text-xs uppercase">Chiffre d'affaires (ventes)</p>
        <p class="text-highlighted text-3xl font-semibold">
          {{ eur.format(total) }}
        </p>
        <p class="text-muted mt-1 text-xs">Sur la période sélectionnée</p>
      </div>
    </template>

    <VisXYContainer
      v-if="data.length"
      :data="data"
      :padding="{ top: 40 }"
      class="unovis-xy-container h-96"
      :width="width"
    >
      <VisLine :x="x" :y="y" color="var(--ui-primary)" />
      <VisArea :x="x" :y="y" color="var(--ui-primary)" :opacity="0.1" />

      <VisAxis type="x" :x="x" :tick-format="xTicks" />

      <VisCrosshair color="var(--ui-primary)" :template="template" />

      <VisTooltip />
    </VisXYContainer>
    <p v-else class="text-muted py-12 text-center text-sm">Aucune vente sur la période sélectionnée.</p>
  </UCard>
</template>

<script setup lang="ts">
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { VisXYContainer, VisLine, VisAxis, VisArea, VisCrosshair, VisTooltip } from '@unovis/vue'
import type { ComputedRef } from 'vue'
import type { DashboardPeriod, DashboardStats } from '~/composables/useStats'

const cardRef = useTemplateRef<HTMLElement | null>('cardRef')

const props = defineProps<{
  stats: DashboardStats | null
  period: DashboardPeriod
}>()

const { width } = useElementSize(cardRef)

type DataRecord = {
  date: Date
  amount: number
}

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const data: ComputedRef<DataRecord[]> = computed(() => {
  const points = props.stats?.revenue_timeline ?? []
  return points.map((p) => ({
    date: new Date(p.date),
    amount: p.revenue_eur,
  }))
})

const x = (_: DataRecord, i: number) => i
const y = (d: DataRecord) => d.amount

const total = computed(() => data.value.reduce((acc, { amount }) => acc + amount, 0))

const formatDate = (date: Date): string => {
  if (props.period === 'monthly') {
    return format(date, 'LLL yyyy', { locale: fr })
  }
  return format(date, 'd MMM', { locale: fr })
}

const xTicks = (i: number) => {
  if (!data.value.length) {
    return ''
  }
  if (i === 0 || i === data.value.length - 1 || !data.value[i]) {
    return ''
  }
  return formatDate(data.value[i].date)
}

const template = (d: DataRecord) => `${formatDate(d.date)} : ${eur.format(d.amount)}`
</script>
