/** Row for {@link useLazyFetch} `/api/phone-codes.json` (Nuxt UI — international phone). */
export type PhoneCode = {
  name: string
  code: string
  emoji: string
  dialCode: string
  /** Maska pattern (`#` = digit), e.g. `# ## ## ## ##` for France. */
  mask: string
}
