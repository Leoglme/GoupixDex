export type UserStatus = 'pending' | 'approved' | 'rejected' | 'banned'

export interface AppUser {
  id: number
  email: string
  vinted_email: string | null
  is_admin: boolean
  status: UserStatus
  created_at: string
}

/** Full user payload exposed to admins on the /users page. */
export interface AdminUser {
  id: number
  email: string
  vinted_email: string | null
  vinted_linked: boolean
  vinted_enabled: boolean
  ebay_enabled: boolean
  margin_percent: number
  is_admin: boolean
  status: UserStatus
  request_message: string | null
  created_at: string
  has_password: boolean
  has_password_setup_link: boolean
}

export interface CreateUserBody {
  email: string
  password: string
  vinted_email?: string | null
  vinted_password?: string | null
}

export interface VintedCredentialsPatch {
  vinted_email?: string | null
  vinted_password?: string | null
}

export interface PasswordSetupLink {
  token: string
  expires_at: string
  setup_url: string
}

export function useUsers() {
  const { $api } = useNuxtApp()

  async function listUsers() {
    const { data } = await $api.get<AdminUser[]>('/users')
    return Array.isArray(data) ? data : []
  }

  async function createUser(body: CreateUserBody) {
    const { data } = await $api.post<AdminUser>('/users', body)
    return data
  }

  async function deleteUser(userId: number) {
    await $api.delete(`/users/${userId}`)
  }

  async function approveUser(userId: number) {
    const { data } = await $api.post<AdminUser>(`/access-requests/${userId}/approve`)
    return data
  }

  async function rejectUser(userId: number) {
    const { data } = await $api.post<AdminUser>(`/access-requests/${userId}/reject`)
    return data
  }

  async function banUser(userId: number) {
    const { data } = await $api.post<AdminUser>(`/access-requests/${userId}/ban`)
    return data
  }

  async function generatePasswordLink(userId: number) {
    const { data } = await $api.post<PasswordSetupLink>(
      `/access-requests/${userId}/password-link`
    )
    return data
  }

  async function updateMyVintedCredentials(patch: VintedCredentialsPatch) {
    const { data } = await $api.put<AppUser>('/users/me/vinted', patch)
    return data
  }

  return {
    listUsers,
    createUser,
    deleteUser,
    approveUser,
    rejectUser,
    banUser,
    generatePasswordLink,
    updateMyVintedCredentials
  }
}
