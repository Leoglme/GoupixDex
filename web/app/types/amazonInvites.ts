/**
 * Product-invite data from the local Amazon worker (sealed Pokémon).
 */
/**
 * Invite row status (aligned with product-page check: ``accepted`` = commandable,
 * ``requested`` / ``not_requested`` = invitation flow, ``listing_only`` = search hit not verified on /dp).
 */
export type AmazonInviteStatus = 'accepted' | 'requested' | 'not_requested' | 'listing_only' | 'expired' | 'unknown'

export interface AmazonInvite {
  id: string
  title: string
  asin?: string
  image_url: string | null
  product_url: string | null
  status: AmazonInviteStatus
  /** ISO 8601 */
  invited_at: string | null
  price_hint?: string | null
}

export type AmazonSessionState = 'ready' | 'needs_login' | 'busy' | 'error'

export interface AmazonSessionResponse {
  state: AmazonSessionState
  message?: string
  last_sync_at?: string | null
}

/** Client-side filter (same buckets as amazon-pokemon-scelled) */
export type AmazonStatusFilter = 'all' | 'accepted' | 'requested' | 'not_requested'

/** Per-status counts for the invites status dropdown labels */
export interface AmazonInviteStatusCounts {
  all: number
  accepted: number
  requested: number
  not_requested: number
}

/** One row for `USelect` status filter */
export interface AmazonStatusSelectItem {
  label: string
  value: AmazonStatusFilter
}

/** Parameters sent to the worker (GET / POST refresh). */
export interface AmazonInvitesFetchParams {
  /** Optional Amazon-side search */
  q: string
  /** Number of result pages to scan (1–50) */
  max_pages: number
}

export interface AmazonInvitesResponse {
  items: AmazonInvite[]
  refreshed_at: string | null
  /** Parameters actually applied (if the worker returns them) */
  params?: {
    q: string | null
    max_pages: number
  }
}

export interface AmazonRefreshResponse {
  items: AmazonInvite[]
  refreshed_at: string | null
  message?: string
  params?: {
    q: string | null
    max_pages: number
  }
}

/** ``POST /amazon/invites/request`` — worker posts Amazon’s invite API (cookies). */
export interface AmazonRequestInviteResponse {
  success: boolean
  message: string
  invite?: AmazonInvite
}
