import { useToast as useUiToast, type Toast } from '@nuxt/ui/composables'

/** Un seul toast succès visible : un nouveau remplace le précédent. */
const GOUPIX_SUCCESS_TOAST_ID = 'goupix-toast-success'

/**
 *
 */
export function useToast() {
  const toast = useUiToast()

  /**
   *
   */
  function add(options: Partial<Toast>) {
    if (options.color === 'success') {
      return toast.add({ ...options, id: GOUPIX_SUCCESS_TOAST_ID })
    }
    return toast.add(options)
  }

  return {
    toasts: toast.toasts,
    add,
    update: toast.update,
    remove: toast.remove,
    clear: toast.clear,
  }
}
