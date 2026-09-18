import type { Ref } from 'vue'
import { createSharedComposable } from '@vueuse/core'

const _useCommandPalette = () => {
  const isOpen: Ref<boolean> = ref(false)

  /**
   * Opens the command palette.
   */
  function open(): void {
    isOpen.value = true
  }

  /**
   * Closes the command palette.
   */
  function close(): void {
    isOpen.value = false
  }

  /**
   * Toggles the command palette.
   */
  function toggle(): void {
    isOpen.value = !isOpen.value
  }

  return { isOpen, open, close, toggle }
}

/**
 * Shared open/close state of the Ctrl+K command palette (singleton via `@vueuse/core`).
 *
 * @returns {{ isOpen: Ref<boolean>; open: () => void; close: () => void; toggle: () => void }} Palette state + helpers.
 */
export const useCommandPalette = createSharedComposable(_useCommandPalette)
