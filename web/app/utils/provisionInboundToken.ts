/** JWT prod réservé au poll OTP Amazon (watch + inbound-code), sans changer NUXT_PUBLIC_API_BASE. */
export const PROVISION_INBOUND_TOKEN_KEY = 'goupix_provision_inbound_token'

export function readProvisionInboundToken(): string | null {
  if (!import.meta.client) {
    return null
  }
  return localStorage.getItem(PROVISION_INBOUND_TOKEN_KEY)
}

export function persistProvisionInboundToken(accessToken: string | null): void {
  if (!import.meta.client) {
    return
  }
  if (accessToken) {
    localStorage.setItem(PROVISION_INBOUND_TOKEN_KEY, accessToken)
  } else {
    localStorage.removeItem(PROVISION_INBOUND_TOKEN_KEY)
  }
}
