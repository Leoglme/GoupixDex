import type { ContactMessagePayload, UseContactMessage } from '~/types/ContactMessage'

/**
 * Envoi d'un message de la page contact à l'API GoupixDex.
 * @returns {UseContactMessage} L'envoi du message.
 */
export function useContactMessage(): UseContactMessage {
  const { $api } = useNuxtApp()

  /**
   * POST `/contact` — le message part par e-mail vers la boîte de l'éditeur.
   * @param {ContactMessagePayload} payload - Message du visiteur.
   * @returns {Promise<void>} Résolue quand l'e-mail est parti.
   * @throws {Error} Quand l'API refuse le message (trop de messages, envoi impossible).
   */
  async function sendContactMessage(payload: ContactMessagePayload): Promise<void> {
    await $api.post('/contact', payload)
  }

  return { sendContactMessage }
}
