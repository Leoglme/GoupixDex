import type { AxiosInstance } from 'axios'
import type {
  AmazonInvitesFetchParams,
  AmazonInvitesResponse,
  AmazonRefreshResponse,
  AmazonRequestInviteResponse,
  AmazonSessionResponse,
} from '~/types/amazonInvites'

/**
 * Serialize invite-list query params for the local worker.
 *
 * @param p - Max pages and optional search string.
 * @returns {Record<string, string | number>} Axios `params` object.
 */
function buildQueryParams(p: AmazonInvitesFetchParams): Record<string, string | number> {
  const out: Record<string, string | number> = { max_pages: p.max_pages }
  const q = p.q?.trim()
  if (q) {
    out.q = q
  }
  return out
}

/**
 * Full WebSocket URL for `/ws/progress` (JWT + remote API as query params).
 *
 * @returns URL string, or `null` when token or bases are missing (client-only).
 */
export function buildAmazonProgressWebSocketUrl(): string | null {
  if (!import.meta.client) {
    return null
  }
  const token = localStorage.getItem('goupix_token')
  if (!token?.trim()) {
    return null
  }
  const config = useRuntimeConfig()
  const base = String(config.public.amazonLocalBase || '').replace(/\/$/, '')
  const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
  if (!base || !apiBase) {
    return null
  }
  const wsBase = base.replace(/^http/i, (m) => (m.toLowerCase() === 'https' ? 'wss' : 'ws'))
  const q = new URLSearchParams({ token: token.trim(), remote_api: apiBase })
  return `${wsBase}/ws/progress?${q.toString()}`
}

/**
 * HTTP calls to the local Amazon worker (`NUXT_PUBLIC_AMAZON_LOCAL_BASE`, default `127.0.0.1:18768`).
 * Uses the same JWT as the main API via the axios plugin.
 *
 * @returns Session + invites helpers (`fetchSession`, `fetchInvites`, `refreshInvites`, `requestInvite`, `openLoginBrowser`).
 */
export function useAmazonWorker() {
  const { $amazonLocal } = useNuxtApp() as { $amazonLocal: AxiosInstance }

  const client = computed(() => $amazonLocal)

  /**
   * GET `/amazon/session` — worker Chrome session state for the invites UI.
   *
   * @returns {Promise<AmazonSessionResponse>} Session payload from the sidecar.
   */
  async function fetchSession(): Promise<AmazonSessionResponse> {
    const { data } = await client.value.get<AmazonSessionResponse>('/amazon/session')
    return data
  }

  /**
   * GET `/amazon/invites` — list invites (cached scrape).
   *
   * @param params - Pagination / search forwarded as query params.
   * @returns {Promise<AmazonInvitesResponse>} Items + metadata from the worker.
   */
  async function fetchInvites(params: AmazonInvitesFetchParams): Promise<AmazonInvitesResponse> {
    const { data } = await client.value.get<AmazonInvitesResponse>('/amazon/invites', {
      params: buildQueryParams(params),
    })
    return data
  }

  /**
   * POST `/amazon/invites/refresh` — force a refresh scrape, then return normalized invites.
   *
   * @param params - Same shape as `fetchInvites` (search + max pages).
   * @returns {Promise<AmazonRefreshResponse>} Refreshed list + optional worker `message`.
   */
  async function refreshInvites(params: AmazonInvitesFetchParams): Promise<AmazonRefreshResponse> {
    const { data } = await client.value.post<AmazonRefreshResponse>('/amazon/invites/refresh', {
      q: params.q?.trim() || null,
      max_pages: params.max_pages,
    })
    return data
  }

  /**
   * POST `/amazon/invites/request` — submit invite request on Amazon (worker session cookies).
   *
   * @param asin - Product ASIN (10 characters).
   * @returns {Promise<AmazonRequestInviteResponse>} Worker response (success, message, updated row).
   */
  async function requestInvite(asin: string): Promise<AmazonRequestInviteResponse> {
    const { data } = await client.value.post<AmazonRequestInviteResponse>('/amazon/invites/request', {
      asin: asin.trim(),
    })
    return data
  }

  /**
   * POST `/amazon/open-login` — opens Chromium (Amazon profile) on the sign-in page.
   * Server alias: `/amazon/browser/open-login`.
   *
   * @returns Worker response `{ opened, url }`.
   */
  async function openLoginBrowser(): Promise<{ opened: boolean; url: string }> {
    const { data } = await client.value.post<{ opened: boolean; url: string }>('/amazon/open-login')
    return data
  }

  return {
    fetchSession,
    fetchInvites,
    refreshInvites,
    requestInvite,
    openLoginBrowser,
  }
}
