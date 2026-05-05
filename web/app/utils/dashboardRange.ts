import { differenceInCalendarDays, endOfDay, startOfDay, startOfMonth, startOfWeek, subDays, subMonths } from 'date-fns'
import type { DashboardPeriod, DashboardRange } from '~/composables/useStats'

/** Presets shown next to the calendar on the dashboard (replaces the old chart bucket selector). */
export type DashboardRangePresetId = 'week' | 'month' | 'days30' | 'months3' | 'all' | 'custom'

function allTimeRangeStart(): Date {
  return startOfDay(new Date(2000, 0, 1))
}

/**
 * Bucket granularity for the revenue timeline API and chart axis labels.
 */
export function chartPeriodForDashboardRange(range: DashboardRange): DashboardPeriod {
  const days = differenceInCalendarDays(range.end, range.start) + 1
  if (days <= 45) {
    return 'daily'
  }
  if (days <= 190) {
    return 'weekly'
  }
  return 'monthly'
}

function normalizeRange(r: DashboardRange): DashboardRange {
  return { start: startOfDay(r.start), end: endOfDay(r.end) }
}

/**
 * Compute date bounds for a dashboard preset (week starts Monday).
 */
export function dashboardRangeForPreset(preset: Exclude<DashboardRangePresetId, 'custom'>): DashboardRange {
  const now = new Date()
  const end = endOfDay(now)
  switch (preset) {
    case 'week':
      return { start: startOfDay(startOfWeek(now, { weekStartsOn: 1 })), end }
    case 'month':
      return { start: startOfDay(startOfMonth(now)), end }
    case 'days30':
      return { start: startOfDay(subDays(now, 30)), end }
    case 'months3':
      return { start: startOfDay(subMonths(now, 3)), end }
    case 'all':
      return { start: allTimeRangeStart(), end }
    default:
      return { start: startOfDay(subDays(now, 30)), end }
  }
}

function rangesMatch(a: DashboardRange, b: DashboardRange): boolean {
  const x = normalizeRange(a)
  const y = normalizeRange(b)
  return differenceInCalendarDays(x.start, y.start) === 0 && differenceInCalendarDays(x.end, y.end) === 0
}

/**
 * Guess which preset matches the current range, or `custom` after calendar tweaks.
 */
export function detectDashboardRangePreset(range: DashboardRange): DashboardRangePresetId {
  const presets: Exclude<DashboardRangePresetId, 'custom'>[] = ['week', 'month', 'days30', 'months3', 'all']
  for (const id of presets) {
    if (rangesMatch(range, dashboardRangeForPreset(id))) {
      return id
    }
  }
  return 'custom'
}
