import type { AmazonInvite } from '~/types/amazonInvites'

/**
 * Props pour le composant ``GoupixDexAmazonInviteCard.vue``.
 */
export interface GoupixDexAmazonInviteCardProps {
  invite: AmazonInvite
  /** True while ``POST /amazon/invites/request`` is in flight for this card’s ASIN. */
  requestInviteLoading?: boolean
}

/**
 * Nuxt UI badge color for invite status on the card.
 */
export type GoupixDexAmazonInviteStatusBadgeColor = 'warning' | 'success' | 'neutral' | 'error' | 'primary'
