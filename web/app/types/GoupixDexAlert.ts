export type GoupixDexAlertVariant = 'warning' | 'success' | 'error' | 'info'

export interface GoupixDexAlertProps {
  variant?: GoupixDexAlertVariant
  title: string
  description?: string
  icon?: string
  /** Classes CSS pour l’icône (ex. animate-spin pour un loader). */
  iconClass?: string
}
