export interface AppSettings {
  margin_percent: number
  vinted_enabled: boolean
  ebay_enabled: boolean
  ebay_marketplace_id: string
  ebay_category_id: string | null
  /** Catégorie par défaut serveur (EBAY_DEFAULT_CATEGORY_ID) ; lecture seule. */
  ebay_default_category_id: string | null
  ebay_merchant_location_key: string | null
  ebay_fulfillment_policy_id: string | null
  ebay_payment_policy_id: string | null
  ebay_return_policy_id: string | null
  ebay_connected: boolean
  ebay_listing_config_complete: boolean
  ebay_oauth_configured: boolean
  ebay_environment: string
}

export type AppSettingsPatch = Partial<{
  margin_percent: number
  vinted_enabled: boolean
  ebay_enabled: boolean
  ebay_marketplace_id: string
  ebay_category_id: string | null
  ebay_merchant_location_key: string | null
  ebay_fulfillment_policy_id: string | null
  ebay_payment_policy_id: string | null
  ebay_return_policy_id: string | null
}>

export function useSettings() {
  const { $api } = useNuxtApp()

  async function getSettings() {
    const { data } = await $api.get<AppSettings>('/settings')
    return data
  }

  async function updateSettings(patch: AppSettingsPatch) {
    const { data } = await $api.put<AppSettings>('/settings', patch)
    return data
  }

  return { getSettings, updateSettings }
}
