export type GoupixDexAlertVariant = 'warning' | 'success' | 'error' | 'info'

export interface GoupixDexAlertProps {
  variant?: GoupixDexAlertVariant
  title: string
  description?: string
  icon?: string
  /** CSS classes for the icon (e.g. `animate-spin` for a loader). */
  iconClass?: string
}
