const DEFAULT_PROVISION_INBOUND_API_BASE = 'https://api.goupixdex.dibodev.fr'

function isLocalApiBase(apiBase: string): boolean {
  const base = apiBase.replace(/\/$/, '')
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(base)
}

/** Webhook Resend → API prod : en local, lire les OTP sur l’API cloud, pas sur 127.0.0.1. */
export function resolveProvisionInboundApiBase(apiBase: string, override?: string): string {
  const cloud = (override || DEFAULT_PROVISION_INBOUND_API_BASE).replace(/\/$/, '')
  const base = apiBase.replace(/\/$/, '')
  if (isLocalApiBase(base)) {
    return cloud
  }
  return base
}
