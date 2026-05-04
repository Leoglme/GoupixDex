import type { AmazonStatusSelectItem } from '~/types/amazonInvites'

/**
 * Props pour le composant ``GoupixDexAmazonInvitesToolbar.vue``.
 */
export interface GoupixDexAmazonInvitesToolbarProps {
  loading: boolean
  refreshing: boolean
  resultCount: number
  totalLoaded: number
  statusSelectItems: AmazonStatusSelectItem[]
}
