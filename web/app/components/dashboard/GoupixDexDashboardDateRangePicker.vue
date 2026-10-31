<template>
  <UPopover :content="{ align: 'end' }" :modal="true">
    <UButton
      icon="i-lucide-calendar"
      :color="isCustomRange ? 'primary' : 'neutral'"
      :variant="isCustomRange ? 'soft' : 'outline'"
      aria-label="Choisir des dates"
      square
      class="size-10 shrink-0 justify-center lg:size-9"
    />

    <template #content>
      <div class="flex flex-col sm:flex-row">
        <div
          class="flex flex-wrap gap-1 border-b border-(--app-line) p-2 sm:flex-col sm:justify-center sm:gap-0 sm:border-r sm:border-b-0 sm:p-0"
        >
          <UButton
            v-for="shortcut in CALENDAR_SHORTCUTS"
            :key="shortcut.id"
            :label="shortcut.label"
            color="neutral"
            variant="ghost"
            class="sm:rounded-none sm:px-4"
            :class="
              isSameDashboardRange(selected, dashboardRangeForCalendarShortcut(shortcut.id))
                ? 'bg-elevated'
                : 'hover:bg-elevated/50'
            "
            @click="selected = dashboardRangeForCalendarShortcut(shortcut.id)"
          />
        </div>

        <UCalendar v-model="calendarRange" class="p-2" :number-of-months="isWideScreen ? 2 : 1" range />
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import type { ComputedRef, WritableComputedRef } from 'vue'
import type { DateRange } from 'reka-ui'
import type { DashboardRange } from '~/composables/useStats'
import type { DashboardCalendarShortcutOption } from '~/types/GoupixDexDashboardDateRangePicker'
import { CalendarDate, getLocalTimeZone } from '@internationalized/date'
import { useMediaQuery } from '@vueuse/core'
import { endOfDay, startOfDay } from 'date-fns'
import {
  dashboardRangeForCalendarShortcut,
  detectDashboardRangePreset,
  isSameDashboardRange,
} from '~/utils/dashboardRange'

const selected = defineModel<DashboardRange>({ required: true })

const CALENDAR_SHORTCUTS: DashboardCalendarShortcutOption[] = [
  { id: 'thisWeek', label: 'Cette semaine' },
  { id: 'thisMonth', label: 'Ce mois-ci' },
  { id: 'days14', label: '14 derniers jours' },
  { id: 'months6', label: '6 derniers mois' },
]

const isWideScreen: ComputedRef<boolean> = useMediaQuery('(min-width: 640px)')

const isCustomRange: ComputedRef<boolean> = computed((): boolean => detectDashboardRangePreset(selected.value) === null)

const calendarRange: WritableComputedRef<DateRange | null> = computed({
  get: (): DateRange | null =>
    detectDashboardRangePreset(selected.value) === 'all'
      ? null
      : { start: toCalendarDate(selected.value.start), end: toCalendarDate(selected.value.end) },
  set: (value: DateRange | null): void => {
    if (!value?.start) {
      return
    }

    const firstDay: Date = value.start.toDate(getLocalTimeZone())
    const lastDay: Date = value.end ? value.end.toDate(getLocalTimeZone()) : firstDay
    selected.value = { start: startOfDay(firstDay), end: endOfDay(lastDay) }
  },
})

/**
 * Convertit une date JavaScript en jour du calendrier.
 * @param {Date} date - Date à convertir, en heure locale.
 * @returns {CalendarDate} Le jour correspondant.
 */
function toCalendarDate(date: Date): CalendarDate {
  return new CalendarDate(date.getFullYear(), date.getMonth() + 1, date.getDate())
}
</script>
