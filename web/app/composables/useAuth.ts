const TOKEN_KEY = 'goupix_token'

export interface MeUser {
  id: number
  email: string
  vinted_email: string | null
  is_admin: boolean
  status: 'pending' | 'approved' | 'rejected' | 'banned'
  created_at: string
}

/**
 * JWT auth state (`useState`), `/users/me` hydration, login / logout.
 *
 * @returns Token, profile, derived flags, and auth helpers (client-aware `localStorage`).
 */
export function useAuth() {
  const { $api } = useNuxtApp()
  const token = useState<string | null>(TOKEN_KEY, () => null)
  const me = useState<MeUser | null>('goupix_me', () => null)
  const meRefreshInflight = useState<Promise<void> | null>('goupix_me_refresh_inflight', () => null)
  /**
   * Client-only: `true` once we know whether a token exists (sync `localStorage` read),
   * without waiting for `/users/me` — otherwise the CTA stays on skeleton if the API is slow or stuck.
   */
  const authResolved = useState<boolean>('goupix_auth_resolved', () => false)

  /**
   * Persist JWT in memory and optionally mirror to `localStorage`.
   *
   * @param accessToken - Bearer token, or `null` to clear.
   * @returns {void} Nothing.
   */
  function persistToken(accessToken: string | null): void {
    token.value = accessToken
    if (import.meta.client) {
      if (accessToken) {
        localStorage.setItem(TOKEN_KEY, accessToken)
      } else {
        localStorage.removeItem(TOKEN_KEY)
      }
    }
  }

  /**
   * POST `/auth/login`, store token, then refresh `/users/me`.
   *
   * @param email - Account email.
   * @param password - Plain password.
   * @returns {Promise<void>} Resolves when profile has been refreshed (or failed silently into `me = null`).
   */
  async function login(email: string, password: string): Promise<void> {
    const { data } = await $api.post<{ access_token: string }>('/auth/login', {
      email,
      password,
    })
    persistToken(data.access_token)
    await refreshMe()
  }

  /**
   * Clear credentials and redirect to `/login`.
   *
   * @returns Whatever `navigateTo('/login')` returns (navigation handle).
   */
  function logout() {
    persistToken(null)
    me.value = null
    return navigateTo('/login')
  }

  /**
   * Fetch `/users/me` when a token exists; dedupes concurrent calls via `meRefreshInflight`.
   *
   * @returns {Promise<void>} Resolves when the profile refresh attempt completes.
   */
  async function refreshMe(): Promise<void> {
    if (!token.value && import.meta.client) {
      token.value = localStorage.getItem(TOKEN_KEY)
    }
    if (!token.value) {
      me.value = null
      if (import.meta.client) {
        authResolved.value = true
      }
      return
    }

    if (import.meta.client) {
      authResolved.value = true
    }

    if (meRefreshInflight.value) {
      await meRefreshInflight.value
      return
    }
    meRefreshInflight.value = (async () => {
      try {
        const { data } = await $api.get<MeUser>('/users/me')
        me.value = data
      } catch {
        me.value = null
      } finally {
        meRefreshInflight.value = null
      }
    })()
    await meRefreshInflight.value
  }

  const isLoggedIn = computed(() => Boolean(token.value))

  return {
    token,
    me,
    isLoggedIn,
    authResolved,
    login,
    logout,
    persistToken,
    refreshMe,
  }
}
