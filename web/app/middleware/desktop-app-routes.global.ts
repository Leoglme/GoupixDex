/**
 * Tauri desktop build only: no marketing landing on `/`, no downloads page.
 * Mirror of “listing logs” (desktop-only): here landing + /downloads stay on the web build.
 */
export default defineNuxtRouteMiddleware((to) => {
  if (import.meta.server) {
    return
  }
  const w = window as Window & { __TAURI__?: unknown; __TAURI_INTERNALS__?: unknown }
  if (!w.__TAURI__ && !w.__TAURI_INTERNALS__) {
    return
  }

  const path = to.path === '' ? '/' : to.path

  if (path === '/downloads') {
    return navigateTo('/dashboard', { replace: true })
  }

  if (path === '/') {
    const token = localStorage.getItem('goupix_token')
    return navigateTo(token ? '/dashboard' : '/login', { replace: true })
  }
})
