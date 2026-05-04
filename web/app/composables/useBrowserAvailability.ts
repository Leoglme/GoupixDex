/**
 * Check for Chrome / Edge on the user's machine (Tauri app only).
 *
 * The local Vinted worker drives Chrome via nodriver. If Chrome is missing:
 * - Edge is used as fallback (set automatically in Rust in
 *   `VINTED_CHROME_EXECUTABLE` when spawning the sidecar);
 * - otherwise the user must install Chrome.
 *
 * On the web (no Tauri) we return a neutral state: the modal never shows.
 */
import type { ComputedRef, Ref } from 'vue'
import type {
  GoupixDexBrowserAvailability,
  GoupixDexBrowserAvailabilityTauriPayload,
} from '~/types/GoupixDexBrowserAvailability'

const STATE_KEY: string = 'goupix_browser_availability'

/**
 * Shared browser availability state (`useState`) and Tauri helpers for Chrome/Edge detection.
 *
 * @returns Reactive `state` / `checked`, plus `check()` and `openExternal()`.
 */
export function useBrowserAvailability(): {
  state: Ref<GoupixDexBrowserAvailability | null>
  checked: Ref<boolean>
  check: (force?: boolean) => Promise<GoupixDexBrowserAvailability>
  openExternal: (url: string) => Promise<void>
} {
  const desktopRuntime: ReturnType<typeof useDesktopRuntime> = useDesktopRuntime()
  const isDesktopApp: ComputedRef<boolean> = desktopRuntime.isDesktopApp

  const state: Ref<GoupixDexBrowserAvailability | null> = useState<GoupixDexBrowserAvailability | null>(
    STATE_KEY,
    () => null,
  )
  const checked: Ref<boolean> = useState<boolean>(`${STATE_KEY}_checked`, () => false)

  /**
   * Check browser availability (desktop only).
   * @param {boolean} force - When true, bypass cached state.
   * @returns {Promise<GoupixDexBrowserAvailability>} The computed availability.
   */
  async function check(force: boolean = false): Promise<GoupixDexBrowserAvailability> {
    if (!import.meta.client) {
      return makeNeutralState()
    }
    if (!force && state.value) {
      return state.value
    }
    if (!isDesktopApp.value) {
      const neutral: GoupixDexBrowserAvailability = makeNeutralState()
      state.value = neutral
      checked.value = true
      return neutral
    }
    try {
      const tauriCore: typeof import('@tauri-apps/api/core') = await import('@tauri-apps/api/core')
      const raw: GoupixDexBrowserAvailabilityTauriPayload =
        await tauriCore.invoke<GoupixDexBrowserAvailabilityTauriPayload>('check_browser_availability')
      const next: GoupixDexBrowserAvailability = {
        chromeAvailable: Boolean(raw.chromeAvailable),
        edgeAvailable: Boolean(raw.edgeAvailable),
        chromePath: raw.chromePath ?? null,
        edgePath: raw.edgePath ?? null,
        chromeInstallUrl: raw.chromeInstallUrl || 'https://www.google.com/intl/fr_fr/chrome/',
        noBrowser: !raw.chromeAvailable && !raw.edgeAvailable,
      }
      state.value = next
      checked.value = true
      return next
    } catch (e) {
      console.warn('[GoupixDex] check_browser_availability indisponible', e)
      const fallback: GoupixDexBrowserAvailability = makeNeutralState()
      state.value = fallback
      checked.value = true
      return fallback
    }
  }

  /**
   * Open a URL externally (desktop: via Tauri shell; web: window.open fallback).
   * @param {string} url - Target URL.
   * @returns {Promise<void>} Resolves when the URL has been opened (best-effort).
   */
  async function openExternal(url: string): Promise<void> {
    if (!isDesktopApp.value || !import.meta.client) {
      window.open(url, '_blank', 'noopener')
      return
    }
    try {
      const shell: typeof import('@tauri-apps/plugin-shell') = await import('@tauri-apps/plugin-shell')
      await shell.open(url)
    } catch {
      window.open(url, '_blank', 'noopener')
    }
  }

  return { state, checked, check, openExternal }
}

/**
 * Neutral “no-op” state for non-desktop runtimes.
 * @returns {GoupixDexBrowserAvailability} A safe default availability object.
 */
function makeNeutralState(): GoupixDexBrowserAvailability {
  return {
    chromeAvailable: true,
    edgeAvailable: false,
    chromePath: null,
    edgePath: null,
    chromeInstallUrl: 'https://www.google.com/intl/fr_fr/chrome/',
    noBrowser: false,
  }
}
