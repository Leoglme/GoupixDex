// Recherche dans la grille d'un classeur : nom du Pokémon (FR ou EN), n° de carte ou rang dans le classeur.

import { KANTO_DEX_NAMES, KANTO_DEX_NAMES_EN } from '~/utils/pokedex/kanto-dex'
import { normalizeSearchQuery } from '~/utils/searchNormalize'

export interface BinderGridSearchEntry {
  /** Rang dans le classeur (1 = première pochette). */
  rank: number
  /** Numéro imprimé de la carte (`064`, `TG05`…), si connu. */
  cardNumber: string | null
  /** Noms déjà normalisés sur lesquels chercher (carte + Pokémon en FR et EN). */
  names: string[]
}

interface KantoNames {
  fr: string
  en: string
}

let kantoNames: KantoNames[] | null = null

/**
 * Noms FR/EN normalisés des Pokémon de Kanto, calculés une seule fois.
 * @returns {KantoNames[]} Index 0 = Pokédex n°1.
 */
function normalizedKantoNames(): KantoNames[] {
  kantoNames ??= KANTO_DEX_NAMES.map(
    (fr: string, index: number): KantoNames => ({
      fr: normalizeSearchQuery(fr),
      en: normalizeSearchQuery(KANTO_DEX_NAMES_EN[index] ?? ''),
    }),
  )
  return kantoNames
}

/**
 * Indique si `word` apparaît dans `text` comme mot entier (pas au milieu d'un autre nom).
 * @param {string} text - Texte normalisé.
 * @param {string} word - Mot normalisé recherché.
 * @returns {boolean} `true` si le mot est présent.
 */
function containsWord(text: string, word: string): boolean {
  if (!word) {
    return false
  }
  const isLetter = (char: string | undefined): boolean => !!char && /[\p{L}\p{N}]/u.test(char)
  let index: number = text.indexOf(word)
  while (index !== -1) {
    if (!isLetter(text[index - 1]) && !isLetter(text[index + word.length])) {
      return true
    }
    index = text.indexOf(word, index + 1)
  }
  return false
}

/**
 * Noms de recherche d'une pochette : le nom de la carte, plus le nom FR et EN du Pokémon
 * (celui de la pochette Pokédex, ou celui reconnu dans le nom de la carte).
 * @param {string | null | undefined} cardName - Nom affiché de la carte.
 * @param {number | null} dexNumber - N° Pokédex de la pochette, en mode complétion.
 * @returns {string[]} Noms normalisés.
 */
export function binderGridSearchNames(cardName: string | null | undefined, dexNumber: number | null): string[] {
  const names = new Set<string>()
  const normalizedCardName: string = normalizeSearchQuery(cardName ?? '')
  if (normalizedCardName) {
    names.add(normalizedCardName)
  }
  const kanto: KantoNames[] = normalizedKantoNames()
  const dexNames: KantoNames | undefined = dexNumber != null ? kanto[dexNumber - 1] : undefined
  if (dexNames) {
    names.add(dexNames.fr)
    names.add(dexNames.en)
  }
  if (normalizedCardName) {
    for (const pokemon of kanto) {
      if (containsWord(normalizedCardName, pokemon.fr) || containsWord(normalizedCardName, pokemon.en)) {
        names.add(pokemon.fr)
        names.add(pokemon.en)
      }
    }
  }
  return [...names].filter(Boolean)
}

/**
 * Teste une pochette contre la recherche : un nombre cherche le n° de carte ou le rang,
 * un texte cherche dans les noms (FR ou EN, sans accents ni casse).
 * @param {BinderGridSearchEntry} entry - Pochette indexée.
 * @param {string} rawQuery - Saisie de l'utilisateur.
 * @returns {boolean} `true` si la pochette correspond (toujours vrai pour une saisie vide).
 */
export function matchesBinderGridSearch(entry: BinderGridSearchEntry, rawQuery: string): boolean {
  const query: string = normalizeSearchQuery(rawQuery)
  if (!query) {
    return true
  }
  // « 64 », « #64 », « n°64 » ou « 064/165 » : n° de carte (sans les zéros de tête) ou rang.
  const numberMatch: RegExpMatchArray | null = query.match(/^(?:#|n°|no\.?)?\s*0*(\d+)(?:\s*\/\s*\d+)?$/)
  if (numberMatch) {
    const wanted: number = Number(numberMatch[1])
    const cardNumber: string = (entry.cardNumber ?? '').trim()
    return entry.rank === wanted || (/^\d+$/.test(cardNumber) && Number(cardNumber) === wanted)
  }
  const cardNumber: string = normalizeSearchQuery(entry.cardNumber ?? '')
  return (cardNumber !== '' && cardNumber === query) || entry.names.some((name: string) => name.includes(query))
}
