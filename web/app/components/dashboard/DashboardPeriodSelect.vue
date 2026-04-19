<script setup lang="ts">
import { eachDayOfInterval } from 'date-fns'
import type { DashboardPeriod, DashboardRange } from '~/composables/useStats'

const model = defineModel<DashboardPeriod>({ required: true })

const props = defineProps<{
  range: DashboardRange
}>()

const days = computed(() => eachDayOfInterval(props.range))

const PERIOD_LABEL: Record<DashboardPeriod, string> = {
  daily: 'Quotidien',
  weekly: 'Hebdomadaire',
  monthly: 'Mensuel'
}

const periods = computed<DashboardPeriod[]>(() => {
  if (days.value.length <= 8) {
    return ['daily']
  }
  if (days.value.length <= 31) {
    return ['daily', 'weekly']
  }
  return ['weekly', 'monthly']
})

const items = computed(() =>
  periods.value.map(value => ({ value, label: PERIOD_LABEL[value] }))
)

watch(periods, () => {
  if (!periods.value.includes(model.value)) {
    model.value = periods.value[0]!
  }
})
</script>

<template>
  <USelect
    v-model="model"
    :items="items"
    value-key="value"
    variant="ghost"
    class="data-[state=open]:bg-elevated"
    :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
  />
</template>
