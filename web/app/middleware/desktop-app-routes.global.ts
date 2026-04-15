/**
 * Exécutable Tauri uniquement : pas de landing marketing sur `/`, pas de page téléchargements.
 * Symétrique à « Journal Vinted » (réservé au desktop), ici landing + /downloads restent pour le web.
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
