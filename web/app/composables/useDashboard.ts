import { createSharedComposable } from '@vueuse/core'

const _useDashboard = () => {
  const router = useRouter()
  const route = useRoute()
  const isNotificationsSlideoverOpen = ref(false)

  defineShortcuts({
    'g-d': () => router.push('/dashboard'),
    'g-a': () => router.push('/articles/stock'),
    'g-s': () => router.push('/settings'),
    'n': () => { isNotificationsSlideoverOpen.value = !isNotificationsSlideoverOpen.value }
  })

  watch(() => route.fullPath, () => {
    isNotificationsSlideoverOpen.value = false
  })

  return {
    isNotificationsSlideoverOpen
  }
}

export const useDashboard = createSharedComposable(_useDashboard)
