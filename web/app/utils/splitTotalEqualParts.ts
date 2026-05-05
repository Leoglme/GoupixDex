/**
 * Split a total EUR amount into `count` equal parts in cents; remainder centimes
 * are assigned to the first lines so the sum matches `totalEur` exactly.
 * @param totalEur - Whole-lot price (e.g. 16.0).
 * @param count - Number of articles (≥ 1).
 * @returns Per-line amounts in euros, same length as `count`.
 */
export function splitTotalEqualParts(totalEur: number, count: number): number[] {
  if (count <= 0) {
    return []
  }
  const cents = Math.round(totalEur * 100)
  const base = Math.floor(cents / count)
  const rem = cents - base * count
  const out: number[] = []
  for (let i = 0; i < count; i++) {
    const c = base + (i < rem ? 1 : 0)
    out.push(c / 100)
  }
  return out
}

/**
 * Poids pour la répartition d’un lot : prix affiché sur l’annonce, sinon prix d’achat.
 */
export function articleListingWeight(a: { sell_price: number | null; purchase_price: number }): number {
  const sp = a.sell_price
  if (sp != null && sp > 0) {
    return sp
  }
  if (a.purchase_price > 0) {
    return a.purchase_price
  }
  return 0
}

/**
 * Répartit `totalEur` proportionnellement aux poids (ex. prix affichés).
 * Méthode du plus grand reste en centimes pour que la somme soit exacte.
 * Si la somme des poids est nulle, délègue à {@link splitTotalEqualParts}.
 */
export function splitTotalByWeights(totalEur: number, weights: number[]): number[] {
  const n = weights.length
  if (n === 0) {
    return []
  }
  const sumW = weights.reduce((a, b) => a + b, 0)
  if (sumW <= 0) {
    return splitTotalEqualParts(totalEur, n)
  }
  const totalCents = Math.round(totalEur * 100)
  const exact = weights.map((w) => (totalCents * w) / sumW)
  const floors = exact.map((x) => Math.floor(x))
  const allocated = floors.reduce((a, b) => a + b, 0)
  const rem = totalCents - allocated
  const order = exact
    .map((x, i) => ({ i, frac: x - Math.floor(x) }))
    .sort((a, b) => (b.frac !== a.frac ? b.frac - a.frac : a.i - b.i))
  const out = [...floors]
  for (let k = 0; k < rem; k++) {
    const idx = order[k]?.i
    if (idx !== undefined) {
      out[idx]++
    }
  }
  return out.map((c) => c / 100)
}
