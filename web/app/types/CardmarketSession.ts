/**
 * Cardmarket session payload from the local desktop worker (`/cardmarket/session`).
 */
export type CardmarketSessionState = 'ready' | 'needs_login' | 'busy' | 'error'

export interface CardmarketSessionResponse {
  state: CardmarketSessionState
  message: string | null
  username: string | null
  credit_eur: number | null
  last_seen: string | null
  browser_open: boolean
}
