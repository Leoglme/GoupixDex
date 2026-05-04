export interface AppSettings {
  margin_percent: number
  vinted_enabled: boolean
  ebay_enabled: boolean
  ebay_marketplace_id: string
  ebay_category_id: string | null
  /** France leaf category baked into the API; read-only (override possible via ebay_category_id). */
  ebay_default_category_id: string
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

/**
 * User marketplace settings (`GET`/`PUT /settings`).
 *
 * @returns `getSettings` and `updateSettings`.
 */
export function useSettings() {
  const { $api } = useNuxtApp()

  /**
   * GET `/settings` — margin + marketplace toggles + eBay integration flags.
   *
   * @returns {Promise<AppSettings>} Current settings snapshot.
   */
  async function getSettings() {
    const { data } = await $api.get<AppSettings>('/settings')
    return data
  }

  /**
   * PUT `/settings` — partial update (merged server-side).
   *
   * @param patch - Mutable settings fields.
   * @returns {Promise<AppSettings>} Updated snapshot after save.
   */
  async function updateSettings(patch: AppSettingsPatch) {
    const { data } = await $api.put<AppSettings>('/settings', patch)
    return data
  }

  return { getSettings, updateSettings }
}
