import type { UserProfilePayload } from '~/types/userProfile'

/**
 * Bloque « Créer sur Amazon » tant que le profil (nom, adresse, mobile) est incomplet.
 *
 * @returns Garde-fou profil + helpers API.
 */
export function useAmazonProvisionProfileGate() {
  const { $api } = useNuxtApp()
  const toast = useToast()
  const { openProfileDrawer } = useProfileDrawer()

  /** @returns Profil utilisateur ou null si l’API échoue. */
  async function fetchAmazonProvisionProfile(): Promise<UserProfilePayload | null> {
    try {
      const { data } = await $api.get<UserProfilePayload>('/users/me/profile')
      return data
    } catch {
      return null
    }
  }

  /** @returns true si le profil permet la création de compte Amazon. */
  async function ensureAmazonProvisionProfileReady(): Promise<boolean> {
    try {
      const data = await fetchAmazonProvisionProfile()
      if (!data) {
        throw new Error('Profil inaccessible')
      }
      if (data.amazon_provision_profile_complete) {
        return true
      }
      const missing: string[] = []
      if (!data.full_name?.trim()) {
        missing.push('nom complet')
      }
      if (!data.sender_address_complete) {
        missing.push('adresse expéditeur')
      }
      toast.add({
        title: 'Profil incomplet',
        description:
          missing.length > 0
            ? `Complétez ${missing.join(', ')} dans Mon profil avant de créer un compte Amazon.`
            : 'Complétez Mon profil avant de créer un compte Amazon.',
        color: 'warning',
      })
      openProfileDrawer()
      return false
    } catch (e: unknown) {
      toast.add({
        title: 'Profil inaccessible',
        description: e instanceof Error ? e.message : String(e),
        color: 'error',
      })
      return false
    }
  }

  return { ensureAmazonProvisionProfileReady, fetchAmazonProvisionProfile }
}
