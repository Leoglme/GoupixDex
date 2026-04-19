/**
 * Vérifie la présence de Chrome / Edge sur la machine de l'utilisateur (app Tauri uniquement).
 *
 * Le worker Vinted local pilote un Chrome installé via nodriver. S'il n'y en a pas :
 * - Edge est utilisé en fallback (renseigné automatiquement côté Rust dans
 *   `VINTED_CHROME_EXECUTABLE` au moment de spawn du sidecar) ;
 * - sinon il faut demander à l'utilisateur d'installer Chrome.
 *
 * Côté web (sans Tauri) on renvoie un état neutre : la modale ne s'affiche jamais.
 */
export interface BrowserAvailability {
  chromeAvailable: boolean
  edgeAvailable: boolean
  chromePath: string | null
  edgePath: string | null
  chromeInstallUrl: string
  /** Aucun navigateur compatible trouvé (ni Chrome ni Edge). */
  noBrowser: boolean
}

const STATE_KEY = 'goupix_browser_availability'

export function useBrowserAvailability() {
  const { isDesktopApp } = useDesktopRuntime()
  const state = useState<BrowserAvailability | null>(STATE_KEY, () => null)
  const checked = useState<boolean>(`${STATE_KEY}_checked`, () => false)

  async function check(force = false): Promise<BrowserAvailability> {
    if (!import.meta.client) {
      return makeNeutralState()
    }
    if (!force && state.value) {
      return state.value
    }
    if (!isDesktopApp.value) {
      const neutral = makeNeutralState()
      state.value = neutral
      checked.value = true
      return neutral
    }
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      const raw = await invoke<{
        chromeAvailable: boolean
        edgeAvailable: boolean
        chromePath: string | null
        edgePath: string | null
        chromeInstallUrl: string
      }>('check_browser_availability')
      const next: BrowserAvailability = {
        chromeAvailable: Boolean(raw.chromeAvailable),
        edgeAvailable: Boolean(raw.edgeAvailable),
        chromePath: raw.chromePath ?? null,
        edgePath: raw.edgePath ?? null,
        chromeInstallUrl: raw.chromeInstallUrl || 'https://www.google.com/intl/fr_fr/chrome/',
        noBrowser: !raw.chromeAvailable && !raw.edgeAvailable
      }
      state.value = next
      checked.value = true
      return next
    } catch (e) {
      console.warn('[GoupixDex] check_browser_availability indisponible', e)
      const fallback = makeNeutralState()
      state.value = fallback
      checked.value = true
      return fallback
    }
  }

  async function openExternal(url: string): Promise<void> {
    if (!isDesktopApp.value || !import.meta.client) {
      window.open(url, '_blank', 'noopener')
      return
    }
    try {
      const shell = await import('@tauri-apps/plugin-shell')
      await shell.open(url)
    } catch {
      window.open(url, '_blank', 'noopener')
    }
  }

  return { state, checked, check, openExternal }
}

function makeNeutralState(): BrowserAvailability {
  return {
    chromeAvailable: true,
    edgeAvailable: false,
    chromePath: null,
    edgePath: null,
    chromeInstallUrl: 'https://www.google.com/intl/fr_fr/chrome/',
    noBrowser: false
  }
}
