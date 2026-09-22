import type { GoupixPriceHistoryPoint } from '~/types/PriceHistory'

export type GoupixDexPriceHistoryChartProps = {
  points: GoupixPriceHistoryPoint[]
}

export type GoupixDexPriceHistoryChartRecord = {
  date: Date
  price: number
}

export type GoupixDexPriceHistoryChartRange = {
  key: string
  label: string
  days: number | null
}

export type GoupixDexPriceHistoryChartPeriodChange = {
  amountEur: number
  ratio: number | null
}

export type GoupixDexPriceHistoryChartPeriodChangeDirection = 'up' | 'down' | 'flat'
