import axios from 'axios'
import { provisionInboundUsesSeparateApi, resolveProvisionInboundApiBase } from '~/utils/provisionInboundApiBase'
import { persistProvisionInboundToken } from '~/utils/provisionInboundToken'

/** Après login local : second login silencieux sur l’API prod pour le poll OTP Amazon. */
export async function syncProvisionInboundLogin(email: string, password: string): Promise<void> {
  if (!import.meta.client) {
    return
  }
  const config = useRuntimeConfig()
  const apiBase = String(config.public.apiBase || '')
  const inboundOverride = config.public.provisionInboundApiBase as string | undefined
  if (!provisionInboundUsesSeparateApi(apiBase, inboundOverride)) {
    persistProvisionInboundToken(null)
    return
  }
  const inboundBase = resolveProvisionInboundApiBase(apiBase, inboundOverride)
  try {
    const { data } = await axios.post<{ access_token: string }>(`${inboundBase}/auth/login`, {
      email,
      password,
    })
    persistProvisionInboundToken(data.access_token || null)
  } catch {
    persistProvisionInboundToken(null)
  }
}
