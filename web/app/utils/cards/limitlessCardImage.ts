// Image de repli d'une carte japonaise récente absente de TCGdex, via le CDN LimitlessTCG.
// TCGdex n'illustre pas encore certains sets récents (Méga, promos) ; LimitlessTCG, si.
// Si l'URL construite n'existe pas (rareté différente), l'appelant retombe sur l'artwork Pokédex.

const LIMITLESS_CDN = 'https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc'

/**
 * URL de l'image LimitlessTCG (japonais) d'une carte à partir de son id TCGdex.
 * Ex. `M2a-250` → `.../tpc/M2a/M2a_250_R_JP_LG.png`, `m1l-064` → `.../tpc/M1L/M1L_64_R_JP_LG.png`. `null` si l'id est inexploitable.
 * @param tcgdexCardId Identifiant TCGdex au format `<set>-<numéro>`.
 */
export function limitlessCardImageUrl(tcgdexCardId: string | null | undefined): string | null {
  if (!tcgdexCardId) {
    return null
  }
  const dash = tcgdexCardId.lastIndexOf('-')
  if (dash < 1) {
    return null
  }
  const rawSetCode = tcgdexCardId.slice(0, dash).replace(/-/g, '')
  // Limitless garde la casse des codes japonais (`M2a`, `SM1p`) : seul un id tout en minuscules est remis en majuscules.
  const setCode = rawSetCode === rawSetCode.toLowerCase() ? rawSetCode.toUpperCase() : rawSetCode
  const localId = tcgdexCardId.slice(dash + 1).replace(/^0+/, '')
  if (!setCode || !localId) {
    return null
  }
  return `${LIMITLESS_CDN}/${setCode}/${setCode}_${localId}_R_JP_LG.png`
}
