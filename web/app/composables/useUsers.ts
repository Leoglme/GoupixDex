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

/**
 * Admin user CRUD, access-request moderation, password-setup links, and `/users/me/vinted` patch.
 *
 * @returns REST helpers bound to the authenticated `$api` client.
 */
export function useUsers() {
  const { $api } = useNuxtApp()

  /**
   * GET `/users` — list users for the admin table.
   *
   * @returns {Promise<AdminUser[]>} User rows (empty array if response shape is unexpected).
   */
  async function listUsers() {
    const { data } = await $api.get<AdminUser[]>('/users')
    return Array.isArray(data) ? data : []
  }

  /**
   * POST `/users` — create a user (admin).
   *
   * @param body - Email, password, optional Vinted credentials.
   * @returns {Promise<AdminUser>} Created user row.
   */
  async function createUser(body: CreateUserBody) {
    const { data } = await $api.post<AdminUser>('/users', body)
    return data
  }

  /**
   * DELETE `/users/:id` — remove a user (admin).
   *
   * @param userId - Target user id.
   * @returns {Promise<void>} Resolves when the server returns 2xx.
   */
  async function deleteUser(userId: number) {
    await $api.delete(`/users/${userId}`)
  }

  /**
   * POST `/access-requests/:id/approve` — approve a pending account.
   *
   * @param userId - User / request id from the admin list.
   * @returns {Promise<AdminUser>} Updated user row.
   */
  async function approveUser(userId: number) {
    const { data } = await $api.post<AdminUser>(`/access-requests/${userId}/approve`)
    return data
  }

  /**
   * POST `/access-requests/:id/reject` — reject a pending account.
   *
   * @param userId - User / request id.
   * @returns {Promise<AdminUser>} Updated user row.
   */
  async function rejectUser(userId: number) {
    const { data } = await $api.post<AdminUser>(`/access-requests/${userId}/reject`)
    return data
  }

  /**
   * POST `/access-requests/:id/ban` — ban a user.
   *
   * @param userId - User id.
   * @returns {Promise<AdminUser>} Updated user row.
   */
  async function banUser(userId: number) {
    const { data } = await $api.post<AdminUser>(`/access-requests/${userId}/ban`)
    return data
  }

  /**
   * POST `/access-requests/:id/password-link` — issue a one-time password setup link.
   *
   * @param userId - User id.
   * @returns {Promise<PasswordSetupLink>} Token + `setup_url` for emailing.
   */
  async function generatePasswordLink(userId: number) {
    const { data } = await $api.post<PasswordSetupLink>(`/access-requests/${userId}/password-link`)
    return data
  }

  /**
   * PUT `/users/me/vinted` — update the current user’s Vinted credentials.
   *
   * @param patch - Optional email/password fields (null clears).
   * @returns {Promise<AppUser>} Updated profile (`AppUser` subset).
   */
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
    updateMyVintedCredentials,
  }
}
