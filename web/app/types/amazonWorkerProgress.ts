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
  /** Normalized invite (search or `/dp` check) for incremental UI while refreshing. */
  invite_preview?: AmazonInvite
}
