import { differenceInCalendarDays, endOfDay, startOfDay, startOfMonth, startOfWeek, subDays, subMonths } from 'date-fns'
import type { DashboardRange } from '~/composables/useStats'

export type DashboardRangePresetId = 'days7' | 'days30' | 'months3' | 'months12' | 'all'

export type DashboardCalendarShortcutId = 'thisWeek' | 'thisMonth' | 'days14' | 'months6'

export const DASHBOARD_RANGE_PRESET_IDS: DashboardRangePresetId[] = ['days7', 'days30', 'months3', 'months12', 'all']

const ALL_TIME_RANGE_START: Date = new Date(2000, 0, 1)

/**
 * Bornes d'une période proposée en un clic : 3 mois = 13 semaines pleines, 12 mois = 12 mois calendaires.
 * @param {DashboardRangePresetId} preset - Période choisie.
 * @returns {DashboardRange} Du début du premier jour à la fin d'aujourd'hui, en heure locale.
 */
export function dashboardRangeForPreset(preset: DashboardRangePresetId): DashboardRange {
  const now: Date = new Date()
  const end: Date = endOfDay(now)

  switch (preset) {
    case 'days7':
      return { start: startOfDay(subDays(now, 6)), end }
    case 'days30':
      return { start: startOfDay(subDays(now, 29)), end }
    case 'months3':
      return { start: startOfDay(subDays(now, 90)), end }
    case 'months12':
      return { start: startOfMonth(subMonths(now, 11)), end }
    case 'all':
      return { start: ALL_TIME_RANGE_START, end }
  }
}

/**
 * Bornes d'un raccourci du calendrier : semaine depuis lundi, mois en cours, 14 jours ou 26 semaines pleines.
 * @param {DashboardCalendarShortcutId} shortcut - Raccourci choisi.
 * @returns {DashboardRange} Du début du premier jour à la fin d'aujourd'hui, en heure locale.
 */
export function dashboardRangeForCalendarShortcut(shortcut: DashboardCalendarShortcutId): DashboardRange {
  const now: Date = new Date()
  const end: Date = endOfDay(now)

  switch (shortcut) {
    case 'thisWeek':
      return { start: startOfWeek(now, { weekStartsOn: 1 }), end }
    case 'thisMonth':
      return { start: startOfMonth(now), end }
    case 'days14':
      return { start: startOfDay(subDays(now, 13)), end }
    case 'months6':
      return { start: startOfDay(subDays(now, 181)), end }
  }
}

/**
 * Indique si deux périodes couvrent les mêmes jours.
 * @param {DashboardRange} first - Première période.
 * @param {DashboardRange} second - Seconde période.
 * @returns {boolean} Vrai quand les premiers et derniers jours coïncident.
 */
export function isSameDashboardRange(first: DashboardRange, second: DashboardRange): boolean {
  return (
    differenceInCalendarDays(first.start, second.start) === 0 && differenceInCalendarDays(first.end, second.end) === 0
  )
}

/**
 * Retrouve la période en un clic qui correspond aux dates affichées.
 * @param {DashboardRange} range - Dates affichées.
 * @returns {DashboardRangePresetId | null} La période, ou null pour des dates choisies au calendrier.
 */
export function detectDashboardRangePreset(range: DashboardRange): DashboardRangePresetId | null {
  return (
    DASHBOARD_RANGE_PRESET_IDS.find((preset: DashboardRangePresetId): boolean =>
      isSameDashboardRange(range, dashboardRangeForPreset(preset)),
    ) ?? null
  )
}
