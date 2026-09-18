// app/types/GoupixDexStatsCard.ts

/**
 * Props for the GoupixDexStatsCard component (KPI tile).
 */
export type GoupixDexStatsCardProps = {
  /** Mono uppercase caption of the metric. */
  title: string
  /** Formatted value (already localized). */
  value: string | number
  /** Iconify icon shown in the accent tile. */
  icon?: string
  /** Small hint under the value. */
  description?: string
}
