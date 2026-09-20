/** Ouvre la fiche d'un produit scellé dans le drawer persistant (même pile que les articles). */
export function useOpenSealedDrawer() {
  const drawerStack = useGoupixDrawerStack()

  /**
   * Ouvre la fiche d'un produit scellé.
   * @param sealedId - Identifiant du produit scellé.
   */
  function openSealed(sealedId: number): void {
    drawerStack.restoreStackFromSession()
    drawerStack.pushSealed(sealedId)
  }

  /**
   * Clic gauche : ouvre le drawer ; clics modifiés : navigation normale (nouvel onglet…).
   * @param sealedId - Identifiant du produit scellé.
   * @param event - Événement souris du clic.
   */
  function openSealedFromClick(sealedId: number, event: MouseEvent): void {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    openSealed(sealedId)
  }

  return { openSealed, openSealedFromClick }
}
