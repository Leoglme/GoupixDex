import type { DashboardPeriod, SalesTimelinePoint } from '~/composables/useStats'

export type GoupixDexDashboardSalesChartProps = {
  points: SalesTimelinePoint[]
  period: DashboardPeriod
}

export type SalesChartBar = {
  date: string
  label: string
  revenueHeight: string
  profitHeight: string
  detail: string
}

export type SalesChartTick = {
  date: string
  label: string
  isHiddenOnMobile: boolean
}
