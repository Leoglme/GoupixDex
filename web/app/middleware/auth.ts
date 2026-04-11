export default defineNuxtRouteMiddleware(() => {
  if (import.meta.server) {
    return
  }
  const token = localStorage.getItem('goupix_token')
  if (!token) {
    return navigateTo('/login')
  }
})
