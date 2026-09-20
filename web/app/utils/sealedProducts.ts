/** Libellés, options et formatage partagés par les écrans Produits scellés. */

import type { SealedProductType } from '~/composables/useSealed'

/** Libellé français par type de produit scellé (aligné sur les catégories Cardmarket). */
export const SEALED_TYPE_LABELS: Record<string, string> = {
  etb: 'ETB',
  display: 'Display',
  box_set: 'Coffret',
  booster: 'Booster',
  tin: 'Tin',
  blister: 'Blister',
  theme_deck: 'Deck',
  trainer_kit: 'Trainer Kit',
  autre: 'Autre',
}

/** Icône Lucide par type de produit scellé (repli : boîte générique). */
export const SEALED_TYPE_ICONS: Record<string, string> = {
  etb: 'i-lucide-box',
  display: 'i-lucide-boxes',
  box_set: 'i-lucide-gift',
  booster: 'i-lucide-package',
  tin: 'i-lucide-cylinder',
  blister: 'i-lucide-credit-card',
  theme_deck: 'i-lucide-layers',
  trainer_kit: 'i-lucide-graduation-cap',
  autre: 'i-lucide-box',
}

/**
 * Icône Lucide d'un type de produit scellé.
 * @param type - Valeur `product_type`.
 * @returns Le nom d'icône, ou une boîte générique.
 */
export function sealedProductTypeIcon(type: string): string {
  return SEALED_TYPE_ICONS[type] ?? 'i-lucide-box'
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
