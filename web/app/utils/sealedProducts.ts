/** Libellés, options et formatage partagés par les écrans Produits scellés. */

import type { SealedProductType } from '~/composables/useSealed'

/** Libellé français par type de produit scellé (ordre d'affichage inclus). */
export const SEALED_TYPE_LABELS: Record<string, string> = {
  etb: 'ETB',
  upc: 'UPC',
  coffret: 'Coffret',
  tripack: 'Tripack',
  pokebox: 'Pokébox',
  mini_tin: 'Mini tin',
  display: 'Display',
  blister: 'Blister',
  autre: 'Autre',
}

/** Options `{ label, value }` pour un `USelect` de type de produit. */
export const SEALED_TYPE_OPTIONS: { label: string; value: SealedProductType }[] = (
  Object.keys(SEALED_TYPE_LABELS) as SealedProductType[]
).map((value) => ({ value, label: SEALED_TYPE_LABELS[value] as string }))

/**
 * Libellé lisible d'un type de produit scellé.
 * @param type - Valeur `product_type`.
 * @returns Le libellé français, ou la valeur brute si le type est inconnu.
 */
export function sealedProductTypeLabel(type: string): string {
  return SEALED_TYPE_LABELS[type] ?? type
}

/**
 * Formate un pourcentage de plus-value avec signe explicite et virgule française.
 * @param percent - Pourcentage de plus-value.
 * @returns La chaîne signée (ex. « +52,1 % »).
 */
export function formatSignedPercent(percent: number): string {
  const sign = percent >= 0 ? '+' : ''
  return `${sign}${percent.toFixed(1).replace('.', ',')} %`
}

/**
 * Convertit un champ texte de montant (virgule ou point) en nombre positif.
 * @param text - Valeur brute du champ.
 * @returns Le montant, ou `null` si vide ou invalide.
 */
export function parseEuroAmount(text: string): number | null {
  const value = Number.parseFloat(text.replace(',', '.'))
  return Number.isFinite(value) && value >= 0 ? value : null
}
