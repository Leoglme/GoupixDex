import type { AxiosInstance } from 'axios'
import type { CardmarketSessionResponse } from '~/types/CardmarketSession'

/**
 * HTTP helpers around the local Cardmarket worker (`NUXT_PUBLIC_CARDMARKET_LOCAL_BASE`,
 * default `http://127.0.0.1:18770`). Mirrors `useAmazonWorker` for the connection card.
 *
 * @returns Session helpers (`fetchSession`, `openLoginBrowser`, `logout`).
 */
export function useCardmarketWorker() {
  const { $cardmarketLocal } = useNuxtApp() as { $cardmarketLocal: AxiosInstance }

  const client = computed(() => $cardmarketLocal)

  /**
   * GET `/cardmarket/session` — connection state from the worker (live DOM read or persisted JSON).
   *
   * @returns Current Cardmarket session payload (logged-in flag, username, last check…).
   */
  async function fetchSession(): Promise<CardmarketSessionResponse> {
    const { data } = await client.value.get<CardmarketSessionResponse>('/cardmarket/session')
    return data
  }

  /**
   * POST `/cardmarket/open-login` — opens Chromium on the Cardmarket Pokémon home so the user can sign in.
   * The worker keeps a background polling loop that updates the persisted session as soon as a username appears.
   *
   * @returns Whether the helper window was opened, and the URL it points to.
   */
  async function openLoginBrowser(): Promise<{ opened: boolean; url: string }> {
    const { data } = await client.value.post<{ opened: boolean; url: string }>('/cardmarket/open-login')
    return data
  }

  /**
   * POST `/cardmarket/logout` — closes the helper browser and forgets the cached username.
   * (Cookies stay in the persistent profile so re-login is automatic next time.)
   */
  async function logout(): Promise<void> {
    await client.value.post('/cardmarket/logout')
  }

  return {
    fetchSession,
    openLoginBrowser,
    logout,
  }
}
