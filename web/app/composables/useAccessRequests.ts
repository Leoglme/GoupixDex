export interface AccessRequestPayload {
  email: string
  message?: string | null
}

export interface PasswordSetupInfo {
  email: string
  expires_at: string
}

/**
 * Waitlist access requests and password-setup token flows (GoupixDex API).
 *
 * @returns API helpers for submitting requests and completing password setup.
 */
export function useAccessRequests() {
  const { $api } = useNuxtApp()

  /**
   * POST `/access-requests` — submit email (and optional message) for approval.
   *
   * @param body - Payload forwarded to the API.
   * @returns {Promise<{ ok: boolean; email: string }>} Acknowledgement from the server.
   */
  async function submitAccessRequest(body: AccessRequestPayload) {
    const { data } = await $api.post<{ ok: boolean; email: string }>('/access-requests', body)
    return data
  }

  /**
   * GET `/password-setup/:token` — load email + expiry for the setup form.
   *
   * @param token - URL-safe setup token from the emailed link.
   * @returns {Promise<PasswordSetupInfo>} Token metadata when valid.
   */
  async function fetchPasswordSetupInfo(token: string) {
    const { data } = await $api.get<PasswordSetupInfo>(`/password-setup/${encodeURIComponent(token)}`)
    return data
  }

  /**
   * POST `/password-setup/:token` — set the user password and finish onboarding.
   *
   * @param token - Setup token from the email link.
   * @param password - New password chosen by the user.
   * @returns {Promise<PasswordSetupInfo>} Confirmed account info after success.
   */
  async function completePasswordSetup(token: string, password: string) {
    const { data } = await $api.post<PasswordSetupInfo>(`/password-setup/${encodeURIComponent(token)}`, { password })
    return data
  }

  return {
    submitAccessRequest,
    fetchPasswordSetupInfo,
    completePasswordSetup,
  }
}
