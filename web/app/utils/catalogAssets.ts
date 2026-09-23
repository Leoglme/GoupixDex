import type { CatalogLocale } from '~/composables/useCardCatalog'

/** TCGdex CDN base for a card when the API omits image (JA sets). */
export function guessCardAssetBase(lang: CatalogLocale, serieId: string, setId: string, localId = '001'): string {
  if (lang === 'ja') {
    return `https://assets.tcgdex.net/ja/${serieId}/${setId}/${localId}`
  }
  return `https://assets.tcgdex.net/en/${serieId.toLowerCase()}/${setId.toLowerCase()}/${localId}`
}

export function catalogLogoCandidates(logo?: string, symbol?: string, cover?: string): string[] {
  const out: string[] = []
  if (logo?.trim()) {
    const l = logo.trim()
    out.push(l.endsWith('.webp') || l.endsWith('.png') ? l : `${l}.webp`)
    if (!l.endsWith('.png')) {
      out.push(l.endsWith('.webp') ? l.replace(/\.webp$/, '.png') : `${l}.png`)
    }
  }
  if (symbol?.trim()) {
    const s = symbol.trim()
    // Le logo est souvent présent sur le CDN TCGdex même quand l'index ne le référence pas :
    // il vit à côté du symbole (…/<set>/logo). On le tente avant de retomber sur le symbole/la carte.
    const derivedLogo = s.replace(/\/symbol(\.\w+)?$/, '/logo')
    if (derivedLogo !== s) {
      out.push(`${derivedLogo}.webp`, `${derivedLogo}.png`)
    }
    out.push(s.endsWith('.webp') || s.endsWith('.png') ? s : `${s}.webp`)
  }
  if (cover?.trim()) {
    out.push(cover.includes('/low.') ? cover : `${cover.replace(/\/$/, '')}/low.webp`)
  }
  return out
}

export function cardThumbFromImage(image?: string, imageLow?: string): string | undefined {
  if (imageLow?.trim()) {
    return imageLow.trim()
  }
  const base = image?.trim()
  if (!base) {
    return undefined
  }
  if (base.includes('/low.')) {
    return base
  }
  return `${base.replace(/\/$/, '')}/low.webp`
}
