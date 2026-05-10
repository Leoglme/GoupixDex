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

  /**
   * Dump read-only prod MariaDB → import into local DB. Requires debug Tauri build + `.env.sync`.
   *
   * @returns Human-readable summary of the sync (e.g. tables imported / row counts) returned by Tauri.
   */
  async function syncDevDatabaseFromProd(): Promise<string> {
    if (!import.meta.dev || !import.meta.client || !isDesktopApp.value) {
      throw new Error('DB sync is only available in desktop dev mode.')
    }
    const { invoke } = await import('@tauri-apps/api/core')
    return invoke<string>('sync_dev_database_from_prod')
  }

  return { isDesktopApp, restartLocalWorkers, stopLocalWorkers, syncDevDatabaseFromProd }
}
