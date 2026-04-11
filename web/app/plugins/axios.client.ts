import axios from 'axios'

const TOKEN_KEY = 'goupix_token'

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const token = useState<string | null>(TOKEN_KEY, () => null)

  if (import.meta.client) {
    token.value = localStorage.getItem(TOKEN_KEY)
  }

  const api = axios.create({
    baseURL: config.public.apiBase as string,
    headers: { Accept: 'application/json' }
  })

  api.interceptors.request.use((req) => {
    const t
      = token.value
        ?? (import.meta.client ? localStorage.getItem(TOKEN_KEY) : null)
    if (t) {
      req.headers.Authorization = `Bearer ${t}`
    }
    return req
  })

  api.interceptors.response.use(
    r => r,
    (err) => {
      if (import.meta.client && err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        token.value = null
        const path = window.location.pathname
        if (path !== '/login' && !path.startsWith('/login')) {
          navigateTo('/login')
        }
      }
      return Promise.reject(err)
    }
  )

  return {
    provide: {
      api
    }
  }
})
