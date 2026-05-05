<template>
  <USelect
    :model-value="selected"
    :items="items"
    value-key="value"
    variant="ghost"
    class="data-[state=open]:bg-elevated min-w-[12rem]"
    :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
    @update:model-value="onSelect"
  />
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'
import type { DashboardRange } from '~/composables/useStats'
import {
  dashboardRangeForPreset,
  detectDashboardRangePreset,
  type DashboardRangePresetId,
} from '~/utils/dashboardRange'

const range = defineModel<DashboardRange>({ required: true })

type Item = { value: DashboardRangePresetId; label: string; disabled?: boolean }

const BASE_ITEMS: Item[] = [
  { value: 'week', label: 'Cette semaine' },
  { value: 'month', label: 'Ce mois-ci' },
  { value: 'days30', label: '30 derniers jours' },
  { value: 'months3', label: '3 derniers mois' },
  { value: 'all', label: 'Depuis toujours' },
]

const selected: ComputedRef<DashboardRangePresetId> = computed(() => detectDashboardRangePreset(range.value))

const items: ComputedRef<Item[]> = computed(() => {
  const base = [...BASE_ITEMS]
  if (selected.value === 'custom') {
    base.push({ value: 'custom', label: 'Personnalisé', disabled: true })
  }
  return base
})

function onSelect(value: unknown): void {
  if (value === 'custom' || typeof value !== 'string') {
    return
  }
  const id = value as Exclude<DashboardRangePresetId, 'custom'>
  const allowed: Exclude<DashboardRangePresetId, 'custom'>[] = ['week', 'month', 'days30', 'months3', 'all']
  if (!allowed.includes(id)) {
    return
  }
  range.value = dashboardRangeForPreset(id)
}
</script>
