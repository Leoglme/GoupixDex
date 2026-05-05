/**
 * Detect GoupixDex desktop (Tauri WebView) vs plain browser — client-only, SSR-safe.
 *
 * @returns Desktop detection and optional control of local Python workers (Tauri).
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
   * Stops then restarts Vinted + Amazon workers (ports released). No-op outside desktop.
   */
  async function restartLocalWorkers(): Promise<void> {
    if (!import.meta.client || !isDesktopApp.value) {
      return
    }
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('restart_local_workers')
  }

  /**
   * Kills workers without restarting (e.g. before an update). No-op outside desktop.
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
