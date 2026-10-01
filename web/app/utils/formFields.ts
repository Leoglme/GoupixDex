const EMAIL_ADDRESS_PATTERN: RegExp = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Vrai quand le champ contient autre chose que des espaces.
 * @param {string} value - Valeur saisie.
 * @returns {boolean} Si le champ est rempli.
 */
export function isFieldFilled(value: string): boolean {
  return value.trim() !== ''
}

/**
 * Vrai pour une adresse e-mail plausible (un « @ » puis un domaine avec un point), espaces autour ignorés.
 * @param {string} value - Adresse saisie.
 * @returns {boolean} Si l'adresse peut recevoir une réponse.
 */
export function isEmailAddress(value: string): boolean {
  return EMAIL_ADDRESS_PATTERN.test(value.trim())
}
