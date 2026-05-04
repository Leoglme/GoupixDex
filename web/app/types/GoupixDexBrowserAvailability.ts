/**
 * Browser availability information (desktop runtime).
 */
export interface GoupixDexBrowserAvailability {
  chromeAvailable: boolean
  edgeAvailable: boolean
  chromePath: string | null
  edgePath: string | null
  chromeInstallUrl: string
  /** No compatible browser found (neither Chrome nor Edge). */
  noBrowser: boolean
}

/**
 * Raw payload returned by the Tauri command `check_browser_availability`.
 */
export interface GoupixDexBrowserAvailabilityTauriPayload {
  chromeAvailable: boolean
  edgeAvailable: boolean
  chromePath: string | null
  edgePath: string | null
  chromeInstallUrl: string
}
