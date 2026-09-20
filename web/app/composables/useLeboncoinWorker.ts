import type { AxiosInstance } from 'axios'

export type LeboncoinSessionState = 'ready' | 'needs_login' | 'busy' | 'unreadable'

export interface LeboncoinSessionResponse {
  state: LeboncoinSessionState
  profile_dir?: string
}

/**
 * Local Leboncoin worker (`NUXT_PUBLIC_LEBONCOIN_LOCAL_BASE`, default `127.0.0.1:18769`).
 */
export function useLeboncoinWorker() {
  const { $leboncoinLocal } = useNuxtApp() as { $leboncoinLocal: AxiosInstance }
  const client = computed(() => $leboncoinLocal)

  /**
   *
   */
  async function fetchSession(): Promise<LeboncoinSessionResponse> {
    const { data } = await client.value.get<LeboncoinSessionResponse>('/leboncoin/session')
    return data
  }

  /**
   *
   */
  async function openLoginBrowser(): Promise<{ opened: boolean; url: string }> {
    const { data } = await client.value.post<{ opened: boolean; url: string }>('/leboncoin/open-login')
    return data
  }

  return { fetchSession, openLoginBrowser }
}
