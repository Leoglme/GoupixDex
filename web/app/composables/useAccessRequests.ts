export interface AccessRequestPayload {
  email: string
  message?: string | null
}

export interface PasswordSetupInfo {
  email: string
  expires_at: string
}

export function useAccessRequests() {
  const { $api } = useNuxtApp()

  async function submitAccessRequest(body: AccessRequestPayload) {
    const { data } = await $api.post<{ ok: boolean, email: string }>(
      '/access-requests',
      body
    )
    return data
  }

  async function fetchPasswordSetupInfo(token: string) {
    const { data } = await $api.get<PasswordSetupInfo>(
      `/password-setup/${encodeURIComponent(token)}`
    )
    return data
  }

  async function completePasswordSetup(token: string, password: string) {
    const { data } = await $api.post<PasswordSetupInfo>(
      `/password-setup/${encodeURIComponent(token)}`,
      { password }
    )
    return data
  }

  return {
    submitAccessRequest,
    fetchPasswordSetupInfo,
    completePasswordSetup
  }
}
