import type { Ref } from 'vue'

/** Visual family of a toast. */
export type ToastType = 'success' | 'error' | 'info' | 'warning'

export type ToastItem = {
  id: number
  title: string
  description?: string
  type: ToastType
  duration: number
}

type ToastAddOptions = {
  title?: string
  description?: string
  color?: 'success' | 'error' | 'warning' | 'info' | 'primary' | 'neutral' | string
  duration?: number
  id?: string | number
}

let nextToastId = 1

/**
 *
 */
function useToastQueue(): Ref<ToastItem[]> {
  return useState<ToastItem[]>('goupix-app-toasts', () => [])
}

/**
 *
 */
function colorToType(color?: string): ToastType {
  if (color === 'success') return 'success'
  if (color === 'error') return 'error'
  if (color === 'warning') return 'warning'
  return 'info'
}

/**
 * Toasts style DevLeadHunter (succès vert, pas la barre orange GoupixDex).
 */
export function useToast() {
  const queue = useToastQueue()

  /**
   *
   */
  function remove(id: number): void {
    queue.value = queue.value.filter((t) => t.id !== id)
  }

  /**
   *
   */
  function clear(): void {
    queue.value = []
  }

  /**
   *
   */
  function showToast(title: string, type: ToastType, options?: { description?: string; duration?: number }): void {
    if (import.meta.server || !import.meta.client) {
      return
    }
    const duration = options?.duration ?? (type === 'error' ? 5000 : 3500)
    const item: ToastItem = {
      id: nextToastId++,
      title,
      description: options?.description,
      type,
      duration,
    }
    if (type === 'success') {
      queue.value = [...queue.value.filter((t) => t.type !== 'success'), item]
      return
    }
    queue.value = [...queue.value, item]
  }

  /**
   *
   */
  function add(options: ToastAddOptions) {
    const title = (options.title ?? '').trim() || 'Notification'
    const type = colorToType(options.color)
    showToast(title, type, { description: options.description, duration: options.duration })
    return { id: options.id ?? nextToastId - 1 }
  }

  return {
    toasts: queue,
    add,
    remove,
    clear,
    success: (message: string) => showToast(message, 'success'),
    error: (message: string) => showToast(message, 'error'),
    info: (message: string) => showToast(message, 'info'),
    warning: (message: string) => showToast(message, 'warning'),
    update: () => {},
  }
}

/**
 *
 */
export function useToastHost(): { toasts: Ref<ToastItem[]>; dismiss: (id: number) => void } {
  const queue = useToastQueue()

  /**
   *
   */
  function dismiss(id: number): void {
    queue.value = queue.value.filter((t) => t.id !== id)
  }

  return { toasts: queue, dismiss }
}
