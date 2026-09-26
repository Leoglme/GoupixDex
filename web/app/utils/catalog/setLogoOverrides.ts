// Logos de set embarqués (source: repo TailTCG) pour les sets sans logo TCGdex.
// Généré depuis set-logos.json ; clé = id de set TCGdex (minuscule en FR/EN, casse d'origine en JA).

import type { CatalogLocale } from '~/composables/useCardCatalog'

const INTERNATIONAL_SET_LOGOS: Record<string, string> = {
  '2011bw': '/set-logos/fr/2011bw.webp',
  '2012bw': '/set-logos/fr/2012bw.webp',
  '2013bw': '/set-logos/fr/2013bw.webp',
  '2014xy': '/set-logos/fr/2014xy.webp',
  '2015xy': '/set-logos/fr/2015xy.webp',
  '2016xy': '/set-logos/fr/2016xy.webp',
  '2017sm': '/set-logos/fr/2017sm.webp',
  '2018sm-fr': '/set-logos/fr/2018sm-fr.webp',
  '2019sm-fr': '/set-logos/fr/2019sm-fr.webp',
  '2021swsh': '/set-logos/fr/2021swsh.webp',
  '2022swsh': '/set-logos/fr/2022swsh.webp',
  '2023sv': '/set-logos/fr/2023sv.webp',
  '2024sv': '/set-logos/fr/2024sv.webp',
  '30th-c': '/set-logos/fr/30th-c.webp',
  cel25cc: '/set-logos/fr/cel25cc.webp',
  jumbo: '/set-logos/fr/jumbo.webp',
  mee: '/set-logos/fr/mee.webp',
  mep: '/set-logos/fr/mep.webp',
  sma: '/set-logos/fr/sma.webp',
  swsh10tg: '/set-logos/fr/swsh10tg.webp',
  swsh11tg: '/set-logos/fr/swsh11tg.webp',
  'swsh12.5gg': '/set-logos/fr/swsh12.5gg.webp',
  swsh12tg: '/set-logos/fr/swsh12tg.webp',
  'swsh4.5sv': '/set-logos/fr/swsh4.5sv.webp',
  swsh9tg: '/set-logos/fr/swsh9tg.webp',
  'tk-bw-e': '/set-logos/fr/tk-bw-e.webp',
  'tk-bw-z': '/set-logos/fr/tk-bw-z.webp',
  'tk-dp-l': '/set-logos/fr/tk-dp-l.webp',
  'tk-dp-m': '/set-logos/fr/tk-dp-m.webp',
  'tk-ex-latia': '/set-logos/fr/tk-ex-latia.webp',
  'tk-ex-latio': '/set-logos/fr/tk-ex-latio.webp',
  'tk-ex-m': '/set-logos/fr/tk-ex-m.webp',
  'tk-ex-p': '/set-logos/fr/tk-ex-p.webp',
  'tk-hs-g': '/set-logos/fr/tk-hs-g.webp',
  'tk-hs-r': '/set-logos/fr/tk-hs-r.webp',
  'tk-sm-r': '/set-logos/fr/tk-sm-r.webp',
  'tk-xy-b': '/set-logos/fr/tk-xy-b.webp',
  'tk-xy-latia': '/set-logos/fr/tk-xy-latia.webp',
  'tk-xy-latio': '/set-logos/fr/tk-xy-latio.webp',
  'tk-xy-n': '/set-logos/fr/tk-xy-n.webp',
  'tk-xy-p': '/set-logos/fr/tk-xy-p.webp',
  'tk-xy-su': '/set-logos/fr/tk-xy-su.webp',
  'tk-xy-sy': '/set-logos/fr/tk-xy-sy.webp',
  'tk-xy-w': '/set-logos/fr/tk-xy-w.webp',
}

const SET_LOGO_OVERRIDES: Record<CatalogLocale, Record<string, string>> = {
  fr: {
    ...INTERNATIONAL_SET_LOGOS,
    '30th': '/set-logos/fr/30th.webp',
    sve: '/set-logos/fr/sve.webp',
    svp: '/set-logos/fr/svp.webp',
  },
  en: INTERNATIONAL_SET_LOGOS,
  ja: {
    E3: '/set-logos/ja/E3.webp',
    E4: '/set-logos/ja/E4.webp',
    E5: '/set-logos/ja/E5.webp',
    L1a: '/set-logos/ja/L1a.webp',
    L1b: '/set-logos/ja/L1b.webp',
    VS1: '/set-logos/ja/VS1.webp',
    web1: '/set-logos/ja/web1.webp',
    XY11a: '/set-logos/ja/XY11a.webp',
    XY1a: '/set-logos/ja/XY1a.webp',
    XY5a: '/set-logos/ja/XY5a.webp',
    XY5b: '/set-logos/ja/XY5b.webp',
    XY8a: '/set-logos/ja/XY8a.webp',
  },
}

/**
 * Logo de set embarqué pour un id de set dépourvu de logo TCGdex dans la langue du catalogue.
 * @param setId Identifiant du set TCGdex.
 * @param locale Langue du catalogue (les ids japonais gardent leur casse).
 * @returns Le chemin public du logo embarqué, ou null.
 */
export function setLogoOverride(setId: string | null | undefined, locale: CatalogLocale): string | null {
  if (!setId) {
    return null
  }
  const key: string = locale === 'ja' ? setId : setId.toLowerCase()
  return SET_LOGO_OVERRIDES[locale][key] ?? null
}
