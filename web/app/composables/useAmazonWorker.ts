import type { AxiosInstance } from 'axios'
import type {
  AmazonInvitesFetchParams,
  AmazonInvitesResponse,
  AmazonInvite,
  AmazonRefreshResponse,
  AmazonReverifyResponse,
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
 * WebSocket connection target for `/ws/progress`.
 * The JWT travels as a `goupix-jwt.<token>` subprotocol instead of a query param,
 * so it never lands in worker access logs; `remote_api` stays in the query string.
 */
export type AmazonProgressWebSocketTarget = {
  url: string
  protocols: string[]
}

/**
 * Build the `/ws/progress` connection target (URL + auth subprotocol).
 *
 * @returns Target object, or `null` when token or bases are missing (client-only).
 */
export function buildAmazonProgressWebSocketUrl(): AmazonProgressWebSocketTarget | null {
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
  const q = new URLSearchParams({ remote_api: apiBase })
  return {
    url: `${wsBase}/ws/progress?${q.toString()}`,
    protocols: [`goupix-jwt.${token.trim()}`],
  }
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
  async function fetchWorkerMeta(): Promise<{ build: string; features: string[] } | null> {
    try {
      const { data } = await client.value.get<{ build: string; features: string[] }>('/amazon/meta')
      return data
    } catch {
      return null
    }
  }

  /**
   *
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
    const body: Record<string, string | number | null> = {
      q: params.q?.trim() || null,
      max_pages: params.max_pages,
    }
    if (params.max_items != null) {
      body.max_items = params.max_items
    }
    const { data } = await client.value.post<AmazonRefreshResponse>('/amazon/invites/refresh', body)
    return data
  }

  /**
   * POST `/amazon/invites/reverify` — re-check invite status for existing rows (account switch).
   *
   * @param items - Current catalog (ASIN + display fields); worker falls back to its search cache when empty.
   */
  async function reverifyInvites(items: AmazonInvite[]): Promise<AmazonReverifyResponse> {
    const { data } = await client.value.post<AmazonReverifyResponse>(
      '/amazon/invites/reverify',
      {
        items: items.map((inv) => ({
          asin: inv.asin ?? null,
          title: inv.title,
          product_url: inv.product_url,
          image_url: inv.image_url,
          price_hint: inv.price_hint ?? null,
        })),
      },
      { timeout: 120_000 },
    )
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

  /**
   * POST `/amazon/browser/close` — closes the login Chromium so the profile
   * flushes its cookies (the on-disk session detection needs the window gone).
   *
   * @returns Worker response `{ closed, message }`.
   */
  async function closeLoginBrowser(): Promise<{ closed: boolean; message: string | null }> {
    const { data } = await client.value.post<{ closed: boolean; message: string | null }>('/amazon/browser/close')
    return data
  }

  /**
   *
   */
  async function activateVaultAccount(accountId: number): Promise<{ ok: boolean; active_account_id: number }> {
    const { data } = await client.value.post<{ ok: boolean; active_account_id: number }>(
      `/amazon/accounts/${accountId}/activate`,
    )
    return data
  }

  /**
   *
   */
  async function autoLoginVaultAccount(
    accountId: number,
  ): Promise<{ success: boolean; message: string; active_account_id: number }> {
    const { data } = await client.value.post<{ success: boolean; message: string; active_account_id: number }>(
      `/amazon/accounts/${accountId}/auto-login`,
    )
    return data
  }

  /**
   *
   */
  async function openProvisionRegister(payload: { email: string; password: string; customer_name?: string }): Promise<{
    success: boolean
    email_prefilled: boolean
    message: string
    url?: string
    email?: string
  }> {
    const { data } = await client.value.post<{
      success: boolean
      email_prefilled: boolean
      message: string
      url?: string
      email?: string
    }>('/amazon/provision/open-register', payload, {
      timeout: 130_000,
    })
    return data
  }

  /**
   *
   */
  async function discardProvisionStaging(): Promise<void> {
    await client.value.post('/amazon/provision/discard')
  }

  /**
   * Saisit le code OTP e-mail Amazon dans la fenêtre Chrome ouverte par le worker local.
   */
  async function fillProvisionEmailVerificationCode(code: string): Promise<{ success: boolean; message: string }> {
    const { data } = await client.value.post<{ success: boolean; message: string }>(
      '/amazon/provision/fill-email-verification-code',
      { code },
      { timeout: 60_000 },
    )
    return data
  }

  /** Préremplit l’étape CVF « Ajouter un numéro de téléphone » si la page est affichée. */
  async function fillProvisionCvfPhone(phone_e164: string): Promise<{ success: boolean; message: string }> {
    const { data } = await client.value.post<{ success: boolean; message: string }>(
      '/amazon/provision/fill-cvf-phone',
      { phone_e164 },
      { timeout: 60_000 },
    )
    return data
  }

  /** @returns Inboxes Receive SMS allouées pour la provision Amazon. */
  async function allocateReceiveSmsInboxes(count: number): Promise<{
    ok: boolean
    message: string
    inboxes: { inbox_url: string; phone_e164: string; message_count: number }[]
  }> {
    const { data } = await client.value.post<{
      ok: boolean
      message: string
      inboxes: { inbox_url: string; phone_e164: string; message_count: number }[]
    }>('/amazon/provision/receive-sms/allocate', null, { params: { count }, timeout: 180_000 })
    return data
  }

  /** @returns Détails d’une inbox Receive SMS (code OTP éventuel). */
  async function inspectReceiveSmsInbox(url: string): Promise<{
    ok: boolean
    amazon_history: boolean
    code: string | null
    message_count: number
    message: string
  }> {
    const { data } = await client.value.get<{
      ok: boolean
      amazon_history: boolean
      code: string | null
      message_count: number
      message: string
    }>('/amazon/provision/receive-sms/inbox', { params: { url }, timeout: 45_000 })
    return data
  }

  /**
   *
   */
  async function claimStagingProfile(accountId: number): Promise<{ ok: boolean; active_account_id: number }> {
    const { data } = await client.value.post<{ ok: boolean; active_account_id: number }>(
      `/amazon/accounts/${accountId}/claim-staging-profile`,
    )
    return data
  }

  /**
   *
   */
  async function openRegisterBrowser(accountId: number): Promise<{
    success: boolean
    email_prefilled: boolean
    message: string
    url?: string
    active_account_id: number
  }> {
    const { data } = await client.value.post<{
      success: boolean
      email_prefilled: boolean
      message: string
      url?: string
      active_account_id: number
    }>(`/amazon/accounts/${accountId}/open-register`, null, {
      timeout: 130_000,
    })
    return data
  }

  return {
    fetchWorkerMeta,
    fetchSession,
    fetchInvites,
    refreshInvites,
    reverifyInvites,
    requestInvite,
    openLoginBrowser,
    closeLoginBrowser,
    activateVaultAccount,
    autoLoginVaultAccount,
    openProvisionRegister,
    fillProvisionEmailVerificationCode,
    fillProvisionCvfPhone,
    inspectReceiveSmsInbox,
    allocateReceiveSmsInboxes,
    discardProvisionStaging,
    claimStagingProfile,
    openRegisterBrowser,
  }
}
