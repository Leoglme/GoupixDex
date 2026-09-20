/** Ouvre la fiche d'une carte de collection dans le drawer persistant (même pile que les articles). */
export function useOpenCardDrawer() {
  const drawerStack = useGoupixDrawerStack()

  /**
   * Ouvre la fiche d'une carte de collection.
   * @param cardId - Identifiant de la carte de collection.
   */
  function openCard(cardId: number): void {
    drawerStack.restoreStackFromSession()
    drawerStack.pushCard(cardId)
  }

  /**
   * Clic gauche : ouvre le drawer ; clics modifiés : navigation normale (nouvel onglet…).
   * @param cardId - Identifiant de la carte de collection.
   * @param event - Événement souris du clic.
   */
  function openCardFromClick(cardId: number, event: MouseEvent): void {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    openCard(cardId)
  }

  return { openCard, openCardFromClick }
}
