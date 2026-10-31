import type { DashboardStats } from '~/composables/useStats'
import type { DashboardRangePresetId } from '~/utils/dashboardRange'

export type GoupixDexSalesDashboardProps = {
  stats: DashboardStats
  rangePresetId?: DashboardRangePresetId | null
}
