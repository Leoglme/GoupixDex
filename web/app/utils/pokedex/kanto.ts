// Placeholders de complétion Pokédex d'un classeur.
// Une pochette de position `p` correspond au Pokémon n° (region.from + p) ;
// tant qu'aucune carte n'y est rangée, on affiche l'artwork + le nom + le n°.

import { KANTO_DEX_NAMES } from '~/utils/pokedex/kanto-dex'

export interface PokedexRegion {
  code: string
  label: string
  from: number
  to: number
}

export const POKEDEX_REGIONS: readonly PokedexRegion[] = [{ code: 'kanto', label: 'Kanto', from: 1, to: 151 }]

export interface PokedexPlaceholder {
  dexNumber: number
  pokemonName: string
  artworkUrl: string
}

/**
 * Région de complétion associée à un code (`kanto`), ou `null` pour un classeur libre.
 * @param code Code de région stocké sur le classeur (`binder.pokedex_region`).
 */
export function pokedexRegion(code: string | null | undefined): PokedexRegion | null {
  if (!code) {
    return null
  }
  return POKEDEX_REGIONS.find((region) => region.code === code) ?? null
}

/**
 * URL de l'artwork officiel d'un Pokémon (asset local `web/public/pokedex/kanto/`).
 * @param dexNumber Numéro national du Pokémon.
 */
export function pokedexArtworkUrl(dexNumber: number): string {
  return `/pokedex/kanto/${dexNumber}.webp`
}

/**
 * Nom français d'un Pokémon par numéro national, avec repli `N°xxx`.
 * @param dexNumber Numéro national du Pokémon.
 */
export function pokedexPokemonName(dexNumber: number): string {
  return KANTO_DEX_NAMES[dexNumber - 1] ?? `N°${dexNumber}`
}

/**
 * Placeholder (artwork + nom FR + n°) pour un numéro national donné.
 * @param dexNumber Numéro national du Pokémon.
 */
export function pokedexPlaceholder(dexNumber: number): PokedexPlaceholder {
  return {
    dexNumber,
    pokemonName: pokedexPokemonName(dexNumber),
    artworkUrl: pokedexArtworkUrl(dexNumber),
  }
}

/**
 * Placeholder de complétion d'une pochette, ou `null` si le classeur n'est pas en
 * mode complétion ou si la pochette sort de la plage de la région.
 * @param regionCode Code de région du classeur.
 * @param pocket Position absolue de la pochette (0 = première).
 */
export function pokedexPlaceholderAt(regionCode: string | null | undefined, pocket: number): PokedexPlaceholder | null {
  const region = pokedexRegion(regionCode)
  if (!region) {
    return null
  }
  const dexNumber = region.from + pocket
  if (dexNumber < region.from || dexNumber > region.to) {
    return null
  }
  return pokedexPlaceholder(dexNumber)
}

/**
 * Nombre de pochettes couvertes par la région de complétion (0 si classeur libre).
 * @param regionCode Code de région du classeur.
 */
export function pokedexRegionSize(regionCode: string | null | undefined): number {
  const region = pokedexRegion(regionCode)
  return region ? region.to - region.from + 1 : 0
}
