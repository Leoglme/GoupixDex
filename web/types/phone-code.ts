/** Entrée pour {@link useLazyFetch} `/api/phone-codes.json` (doc Nuxt UI — téléphone international). */
export type PhoneCode = {
  name: string
  code: string
  emoji: string
  dialCode: string
  /** Masque maska (`#` = chiffre), ex. `# ## ## ## ##` pour la France. */
  mask: string
}
