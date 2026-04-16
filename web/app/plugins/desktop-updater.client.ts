import { check } from '@tauri-apps/plugin-updater'

export default defineNuxtPlugin(async () => {
  const { isDesktopApp } = useDesktopRuntime()

  if (!isDesktopApp.value || !import.meta.client) {
    return
  }

  if (window.sessionStorage.getItem('goupix-updater-checked') === '1') {
    return
  }
  window.sessionStorage.setItem('goupix-updater-checked', '1')

  try {
    const update = await check()

    if (!update) {
      return
    }

    const confirmed = window.confirm(
      `Une mise a jour ${update.version} est disponible.\n\n` +
      'Voulez-vous la telecharger et l installer maintenant ?'
    )

    if (!confirmed) {
      return
    }

    await update.downloadAndInstall()

    window.alert(
      'La mise a jour est installee. Fermez puis relancez GoupixDex pour appliquer la nouvelle version.'
    )
  } catch (error) {
    console.error('[Updater] Echec de verification/installation de mise a jour:', error)
  }
})
