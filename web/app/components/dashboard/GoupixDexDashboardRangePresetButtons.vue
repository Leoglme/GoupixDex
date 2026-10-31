<template>
  <div
    role="group"
    aria-label="Période"
    class="flex min-w-0 grow gap-0.5 overflow-x-auto rounded-lg bg-(--app-surface-2) p-0.5 lg:grow-0"
  >
    <button
      v-for="option in PRESET_OPTIONS"
      :key="option.id"
      type="button"
      :aria-pressed="option.id === selectedPresetId"
      class="h-9 flex-1 shrink-0 rounded-md px-3 text-[13px] whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-(--app-accent) focus-visible:outline-none lg:h-8 lg:flex-none"
      :class="
        option.id === selectedPresetId
          ? 'bg-(--app-surface) font-bold text-(--app-ink) shadow-xs'
          : 'font-semibold text-(--app-ink-soft) hover:text-(--app-ink)'
      "
      @click="range = dashboardRangeForPreset(option.id)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef } from 'vue'
import type { DashboardRange } from '~/composables/useStats'
import type { DashboardRangePresetOption } from '~/types/GoupixDexDashboardRangePresetButtons'
import type { DashboardRangePresetId } from '~/utils/dashboardRange'
import { dashboardRangeForPreset, detectDashboardRangePreset } from '~/utils/dashboardRange'

const range = defineModel<DashboardRange>({ required: true })

const PRESET_OPTIONS: DashboardRangePresetOption[] = [
  { id: 'days7', label: '7 j' },
  { id: 'days30', label: '30 j' },
  { id: 'months3', label: '3 mois' },
  { id: 'months12', label: '12 mois' },
  { id: 'all', label: 'Tout' },
]

const selectedPresetId: ComputedRef<DashboardRangePresetId | null> = computed((): DashboardRangePresetId | null =>
  detectDashboardRangePreset(range.value),
)
</script>
