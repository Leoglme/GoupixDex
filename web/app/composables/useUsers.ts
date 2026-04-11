export interface AppUser {
  id: number
  email: string
  vinted_email: string | null
  created_at: string
}

export interface CreateUserBody {
  email: string
  password: string
  vinted_email?: string | null
  vinted_password?: string | null
}

export function useUsers() {
  const { $api } = useNuxtApp()

  async function listUsers() {
    const { data } = await $api.get<AppUser[]>('/users')
    return Array.isArray(data) ? data : []
  }

  async function createUser(body: CreateUserBody) {
    const { data } = await $api.post<AppUser>('/users', body)
    return data
  }

  return {
    listUsers,
    createUser
  }
}
