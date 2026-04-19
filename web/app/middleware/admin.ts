export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.server) {
    return
  }
  const token = localStorage.getItem('goupix_token')
  if (!token) {
    return navigateTo('/login')
  }
  const { me, refreshMe } = useAuth()
  if (!me.value) {
    await refreshMe()
  }
  if (!me.value || !me.value.is_admin) {
    return navigateTo('/dashboard')
  }
})
