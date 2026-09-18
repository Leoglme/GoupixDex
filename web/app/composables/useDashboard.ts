import { createSharedComposable } from '@vueuse/core'

const _useDashboard = (): void => {
  const router = useRouter()

  defineShortcuts({
    'g-d': () => router.push('/dashboard'),
    'g-a': () => router.push('/articles/stock'),
    'g-s': () => router.push('/settings'),
  })
}

/**
 * Shared shell state for the default layout: registers the global `g-*` navigation shortcuts once.
 *
 * @returns {void} Nothing — shortcuts are registered as a side effect (singleton via `@vueuse/core`).
 */
export const useDashboard = createSharedComposable(_useDashboard)
