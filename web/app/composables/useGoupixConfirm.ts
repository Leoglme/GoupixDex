export type GoupixConfirmColor = 'error' | 'primary' | 'neutral' | 'warning'

export interface GoupixConfirmOptions {
  title: string
  description?: string
  body?: string
  confirmLabel?: string
  cancelLabel?: string
  confirmColor?: GoupixConfirmColor
}

interface GoupixConfirmState {
  open: boolean
  options: GoupixConfirmOptions | null
}

let pendingResolve: ((value: boolean) => void) | null = null

/**
 * Promise-based confirmation dialog (replaces ``window.confirm``).
 * Render ``GoupixDexConfirmHost`` once in the app layout.
 */
export function useGoupixConfirm() {
  const state = useState<GoupixConfirmState>('goupix-confirm', () => ({
    open: false,
    options: null,
  }))

  /**
   *
   */
  function confirm(options: GoupixConfirmOptions): Promise<boolean> {
    return new Promise((resolve) => {
      pendingResolve = resolve
      state.value = {
        open: true,
        options,
      }
    })
  }

  /**
   *
   */
  function finish(confirmed: boolean): void {
    state.value = { open: false, options: null }
    const resolve = pendingResolve
    pendingResolve = null
    resolve?.(confirmed)
  }

  return {
    state,
    confirm,
    finish,
  }
}
