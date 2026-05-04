import type { AmazonInvite } from '~/types/amazonInvites'

/**
 * Payload broadcast by the local Amazon worker over {@link WebSocket} `/ws/progress`.
 */
export interface AmazonWorkerProgressPayload {
  status: string
  message?: string
  current_page?: number
  total_pages?: number
  items_found?: number
  item_title?: string
  asin?: string
  /** Fiche normalisée (recherche ou vérification `/dp`) pour affichage incrémental pendant l’actualisation. */
  invite_preview?: AmazonInvite
}
