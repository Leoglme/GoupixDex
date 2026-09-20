/** Courbe d'évolution du prix marché, partagée par les cartes et les produits scellés. */

export interface GoupixPriceHistoryPoint {
  date: string
  price_eur: number
}

export interface GoupixPriceHistoryResponse {
  points: GoupixPriceHistoryPoint[]
  approximate: boolean
}
