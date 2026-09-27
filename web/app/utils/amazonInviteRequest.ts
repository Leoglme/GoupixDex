import type { AmazonInviteStatus } from '~/types/amazonInvites'

/**
 * Indique si l’invitation d’un produit reste à demander : pas encore demandée, ou vue sur invitation sans vérification.
 * @param {AmazonInviteStatus} status - Statut du produit sur le compte.
 * @returns {boolean} True quand « Demander l’invitation » s’applique.
 */
export function canRequestInvite(status: AmazonInviteStatus): boolean {
  return status === 'not_requested' || status === 'listing_only'
}
