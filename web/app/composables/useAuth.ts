const TOKEN_KEY = 'goupix_token'

export interface MeUser {
  id: number
  email: string
  vinted_email: string | null
  created_at: string
}

export function useAuth() {
  const { $api } = useNuxtApp()
  const token = useState<string | null>(TOKEN_KEY, () => null)
  const me = useState<MeUser | null>('goupix_me', () => null)
  const meRefreshInflight = useState<Promise<void> | null>(
    'goupix_me_refresh_inflight',
    () => null
  )

  function persistToken(accessToken: string | null) {
    token.value = accessToken
    if (import.meta.client) {
      if (accessToken) {
        localStorage.setItem(TOKEN_KEY, accessToken)
      } else {
        localStorage.removeItem(TOKEN_KEY)
      }
    }
  }

  async function login(email: string, password: string) {
    const { data } = await $api.post<{ access_token: string }>('/auth/login', {
      email,
      password
    })
    persistToken(data.access_token)
    await refreshMe()
  }

  function logout() {
    persistToken(null)
    me.value = null
    return navigateTo('/login')
  }

  async function refreshMe() {
    if (!token.value && import.meta.client) {
      token.value = localStorage.getItem(TOKEN_KEY)
    }
    if (!token.value) {
      me.value = null
      return
    }
    if (meRefreshInflight.value) {
      return meRefreshInflight.value
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
    return meRefreshInflight.value
  }

  const isLoggedIn = computed(() => Boolean(token.value))

  return {
    token,
    me,
    isLoggedIn,
    login,
    logout,
    persistToken,
    refreshMe
  }
}
