// Affichage lisible d'un nom de set : les sets japonais uniquement (m1l, sv-p…) n'ont pas
// de nom FR/EN chez TCGdex ; on montre alors le code du set (SV-P, M1L), latin et reconnu.

const JAPANESE_RE = /[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]/

/**
 * Vrai si le texte contient des caractères japonais (hiragana, katakana, kanji).
 * @param text Texte à tester.
 * @returns `true` si au moins un caractère japonais est présent.
 */
export function hasJapanese(text: string | null | undefined): boolean {
  return !!text && JAPANESE_RE.test(text)
}

/**
 * Libellé de set lisible : le nom s'il est latin, sinon le code du set (ex. `SV-P`), sinon un repli.
 * @param setName Nom du set (peut être en japonais).
 * @param setCode Code du set (latin, ex. `SV-P`).
 * @param fallback Repli si aucun des deux n'est exploitable (ex. l'id de set).
 * @returns Le libellé le plus lisible disponible.
 */
export function readableSetLabel(setName?: string | null, setCode?: string | null, fallback?: string | null): string {
  const name = (setName ?? '').trim()
  if (name && !hasJapanese(name)) {
    return name
  }
  const code = (setCode ?? '').trim()
  if (code) {
    return code.toUpperCase()
  }
  return name || (fallback ?? '').trim() || '—'
}
