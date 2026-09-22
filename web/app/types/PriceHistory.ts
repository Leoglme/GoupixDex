/** Courbe d'évolution du prix marché, partagée par les cartes et les produits scellés. */

export interface GoupixPriceHistoryPoint {
  date: string
  price_eur: number
}

export interface GoupixPriceHistoryResponse {
  points: GoupixPriceHistoryPoint[]
  approximate: boolean
}

/** Fichier `sealed-catalog/history/{n}.json` : par idProduct TCGplayer, points `[date ISO, prix €]` croissants. */
export type GoupixSealedCatalogPriceHistoryShard = {
  v: number
  products: Record<string, [string, number][]>
}
