/**
 * Detect GoupixDex desktop (Tauri WebView) vs plain browser — client-only, SSR-safe.
 *
 * @returns Desktop detection + contrôle optionnel des workers Python locaux (Tauri).
 */
export function useDesktopRuntime() {
  const isDesktopApp = computed(() => {
    if (!import.meta.client) {
      return false
    }
    const w = window as Window & {
      __TAURI__?: unknown
      __TAURI_INTERNALS__?: unknown
    }
    return Boolean(w.__TAURI__ || w.__TAURI_INTERNALS__)
  })

  /**
   * Arrête puis relance les workers Vinted + Amazon (ports libérés). No-op hors desktop.
   */
  async function restartLocalWorkers(): Promise<void> {
    if (!import.meta.client || !isDesktopApp.value) {
      return
    }
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('restart_local_workers')
  }

  /**
   * Tue les workers sans les relancer (ex. avant mise à jour). No-op hors desktop.
   */
  async function stopLocalWorkers(): Promise<void> {
    if (!import.meta.client || !isDesktopApp.value) {
      return
    }
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('stop_local_worker')
  }

  return { isDesktopApp, restartLocalWorkers, stopLocalWorkers }
}
