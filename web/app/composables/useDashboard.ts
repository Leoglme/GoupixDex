import type { Ref } from 'vue'
import { createSharedComposable } from '@vueuse/core'

const _useDashboard = () => {
  const router = useRouter()
  const route = useRoute()
  const isNotificationsSlideoverOpen: Ref<boolean> = ref(false)

  defineShortcuts({
    'g-d': () => router.push('/dashboard'),
    'g-a': () => router.push('/articles/stock'),
    'g-s': () => router.push('/settings'),
    n: () => {
      isNotificationsSlideoverOpen.value = !isNotificationsSlideoverOpen.value
    },
  })

  watch(
    () => route.fullPath,
    () => {
      isNotificationsSlideoverOpen.value = false
    },
  )

  return {
    isNotificationsSlideoverOpen,
  }
}

/**
 * Shared shell UI state for the default layout (keyboard shortcuts + notifications slideover).
 *
 * @returns {{ isNotificationsSlideoverOpen: Ref<boolean> }} Shared reactive flag (singleton via `@vueuse/core`).
 */
export const useDashboard = createSharedComposable(_useDashboard)
