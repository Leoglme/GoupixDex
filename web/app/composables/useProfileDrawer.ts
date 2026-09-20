/**
 * Ouverture globale du drawer « Mon profil » (menu compte + garde-fou Leboncoin).
 *
 * @returns État et actions du drawer profil.
 */
export function useProfileDrawer() {
  const profileDrawerOpen = useState('goupix-profile-drawer-open', () => false)

  /** Ouvre le drawer Mon profil. */
  function openProfileDrawer(): void {
    profileDrawerOpen.value = true
  }

  /** Ferme le drawer Mon profil. */
  function closeProfileDrawer(): void {
    profileDrawerOpen.value = false
  }

  return {
    profileDrawerOpen,
    openProfileDrawer,
    closeProfileDrawer,
  }
}
