import { useEventListener } from '@vueuse/core'
import { onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'

export type DashboardMainColumnBounds = {
  left: Ref<number>
  width: Ref<number>
}

/**
 * Viewport bounds of the active UDashboardPanel column (area to the right of the sidebar).
 * Used to center teleported overlays (bulk bar) on the main preview, not the full window.
 */
export function useDashboardMainColumnBounds(anchorRef: Ref<HTMLElement | null>): DashboardMainColumnBounds {
  const left = ref(0)
  const width = ref(0)

  let panelEl: HTMLElement | null = null
  let panelObserver: ResizeObserver | null = null

  /**
   *
   */
  function findPanelRoot(from: HTMLElement): HTMLElement | null {
    let node: HTMLElement | null = from
    while (node) {
      if (node.classList.contains('min-h-svh') && node.classList.contains('flex-col')) {
        return node
      }
      node = node.parentElement
    }
    return null
  }

  /**
   *
   */
  function measure(): void {
    if (!import.meta.client || !panelEl) {
      return
    }
    const rect = panelEl.getBoundingClientRect()
    left.value = rect.left
    width.value = rect.width
  }

  /**
   *
   */
  function bindPanel(from: HTMLElement | null): void {
    panelObserver?.disconnect()
    panelObserver = null
    panelEl = from ? findPanelRoot(from) : null
    if (!panelEl) {
      left.value = 0
      width.value = import.meta.client ? window.innerWidth : 0
      return
    }
    panelObserver = new ResizeObserver(measure)
    panelObserver.observe(panelEl)
    measure()
  }

  watch(
    anchorRef,
    (el) => {
      bindPanel(el)
    },
    { immediate: true },
  )

  if (import.meta.client) {
    useEventListener(window, 'resize', measure, { passive: true })
  }

  onUnmounted(() => {
    panelObserver?.disconnect()
  })

  return { left, width }
}
