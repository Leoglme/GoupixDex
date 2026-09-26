import type { CardScannerShortcut } from '~/types/CardScannerShortcut'
import { createSharedComposable } from '@vueuse/core'

const _useOpenCardScanner = (): CardScannerShortcut => {
  let openScanPageCamera: (() => void) | null = null

  /**
   * Enregistre la fonction qui ouvre la caméra de la page scan affichée.
   * @param {(() => void) | null} openCamera - Ouvre la caméra de la page scan ; null quand la page se démonte.
   * @returns {void}
   */
  function setScanPageCameraOpener(openCamera: (() => void) | null): void {
    openScanPageCamera = openCamera
  }

  /**
   * Ouvre le scanner de cartes : la caméra tout de suite si la page scan est déjà affichée, sinon la page scan.
   * @returns {void}
   */
  function openCardScanner(): void {
    if (openScanPageCamera) {
      openScanPageCamera()
      return
    }

    navigateTo('/collection/scan')
  }

  return { setScanPageCameraOpener, openCardScanner }
}

/**
 * Ouvre le scanner de cartes, ou directement sa caméra quand la page scan est déjà affichée.
 * @returns {CardScannerShortcut} Enregistrement de la caméra de la page scan et ouverture du scanner.
 */
export const useOpenCardScanner = createSharedComposable(_useOpenCardScanner)
