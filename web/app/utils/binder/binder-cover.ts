// Couverture sur mesure — json `binders.cover` (parité TailTCG, ids cartes = collection_card_id).

export const ZONES = ['tl', 'tc', 'tr', 'ml', 'mc', 'mr', 'bl', 'bc', 'br'] as const
export type ZoneKey = (typeof ZONES)[number]

export const ZONE_LABELS: Record<ZoneKey, string> = {
  tl: 'Haut gauche',
  tc: 'Haut centre',
  tr: 'Haut droite',
  ml: 'Milieu gauche',
  mc: 'Centre',
  mr: 'Milieu droite',
  bl: 'Bas gauche',
  bc: 'Bas centre',
  br: 'Bas droite',
}

export const TEXT_SIZES = [
  { code: 'sm', label: 'Petit' },
  { code: 'md', label: 'Moyen' },
  { code: 'lg', label: 'Grand' },
  { code: 'xl', label: 'Géant' },
] as const
export const ELEMENT_SIZES = [
  { code: 'sm', label: 'Petit' },
  { code: 'md', label: 'Moyen' },
  { code: 'lg', label: 'Grand' },
] as const
export const FONTS = [
  { code: 'display', label: 'Titre' },
  { code: 'sans', label: 'Texte' },
  { code: 'mono', label: 'Mono' },
] as const

export const TEXT_COLORS = [
  '#ffffff',
  '#f5f1e6',
  '#1f1f1f',
  '#dc2626',
  '#ea580c',
  '#ca8a04',
  '#16a34a',
  '#2563eb',
  '#7c3aed',
  '#db2777',
] as const

export const BG_COLORS = [
  '#1f1f23',
  '#0f172a',
  '#f5f1e6',
  '#dc2626',
  '#ea580c',
  '#ca8a04',
  '#16a34a',
  '#2563eb',
  '#7c3aed',
  '#db2777',
] as const

export type TextSize = (typeof TEXT_SIZES)[number]['code']
export type ElementSize = (typeof ELEMENT_SIZES)[number]['code']
export type Font = (typeof FONTS)[number]['code']
export type ImageShape = 'square' | 'round' | 'free'

export const IMAGE_SHAPES = [
  { code: 'square', label: 'Carrée' },
  { code: 'round', label: 'Ronde' },
  { code: 'free', label: 'Libre' },
] as const

export type CoverText = {
  type: 'text'
  text: string
  size: TextSize
  weight: 'normal' | 'bold'
  color: string
  font: Font
}
export type CoverLogo = {
  type: 'logo'
  setId: string
  setName: string
  url: string
  size: ElementSize
}
export type CoverImage = {
  type: 'image'
  path: string
  size: ElementSize
  shape: ImageShape
}
export type CoverCard = { type: 'card'; itemId: string; size: ElementSize }
export type CoverElement = CoverText | CoverLogo | CoverImage | CoverCard

export type CoverBackground = {
  kind: 'color' | 'image' | 'card'
  color: string | null
  image: string | null
  card: string | null
  dim: number
}
export type CoverLayout = {
  bg: CoverBackground
  zones: Partial<Record<ZoneKey, CoverElement>>
}

export const EMPTY_COVER: CoverLayout = {
  bg: { kind: 'color', color: null, image: null, card: null, dim: 35 },
  zones: {},
}

const HEX_RE = /^#[0-9a-f]{6}$/i
const CARD_ID_RE = /^\d+$/
const TCGDEX_ASSET = /^https:\/\/assets\.tcgdex\.net\/[\w./-]+$/
export const TEXT_MAX = 80

function pick<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly unknown[]).includes(value) ? (value as T) : fallback
}
const str = (v: unknown, max: number) => (typeof v === 'string' ? v.slice(0, max) : '')

function element(raw: unknown): CoverElement | null {
  if (!raw || typeof raw !== 'object') return null
  const e = raw as Record<string, unknown>
  const sizes3 = ELEMENT_SIZES.map((s) => s.code)
  switch (e.type) {
    case 'text': {
      const text = str(e.text, TEXT_MAX).trim()
      if (!text) return null
      const color = str(e.color, 7)
      return {
        type: 'text',
        text,
        size: pick(
          e.size,
          TEXT_SIZES.map((s) => s.code),
          'md',
        ),
        weight: e.weight === 'normal' ? 'normal' : 'bold',
        color: HEX_RE.test(color) ? color.toLowerCase() : '#ffffff',
        font: pick(
          e.font,
          FONTS.map((f) => f.code),
          'display',
        ),
      }
    }
    case 'logo': {
      const url = str(e.url, 300)
      if (!TCGDEX_ASSET.test(url)) return null
      return {
        type: 'logo',
        setId: str(e.setId, 60),
        setName: str(e.setName, 120),
        url,
        size: pick(e.size, sizes3, 'md'),
      }
    }
    case 'image': {
      const path = str(e.path, 300)
      if (!path) return null
      const shape: ImageShape =
        e.round === true ? 'round' : pick(e.shape, ['square', 'round', 'free'] as const, 'square')
      return { type: 'image', path, size: pick(e.size, sizes3, 'md'), shape }
    }
    case 'card': {
      const itemId = str(e.itemId, 20)
      if (!CARD_ID_RE.test(itemId)) return null
      return { type: 'card', itemId, size: pick(e.size, sizes3, 'md') }
    }
    default:
      return null
  }
}

export function coverLayout(raw: unknown): CoverLayout {
  const d = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const b = (d.bg && typeof d.bg === 'object' ? d.bg : {}) as Record<string, unknown>
  const color = str(b.color, 7)
  const image = str(b.image, 300)
  const card = str(b.card, 20)
  const dimRaw = typeof b.dim === 'number' ? Math.round(b.dim) : EMPTY_COVER.bg.dim
  const bg: CoverBackground = {
    kind: pick(b.kind, ['color', 'image', 'card'] as const, 'color'),
    color: HEX_RE.test(color) ? color.toLowerCase() : null,
    image: image || null,
    card: CARD_ID_RE.test(card) ? card : null,
    dim: Math.max(0, Math.min(85, dimRaw)),
  }
  if (bg.kind === 'image' && !bg.image) bg.kind = 'color'
  if (bg.kind === 'card' && !bg.card) bg.kind = 'color'

  const zones: CoverLayout['zones'] = {}
  const z = (d.zones && typeof d.zones === 'object' ? d.zones : {}) as Record<string, unknown>
  for (const key of ZONES) {
    const el = element(z[key])
    if (el) zones[key] = el
  }
  return { bg, zones }
}

export function coverStoragePaths(layout: CoverLayout): string[] {
  const paths: string[] = []
  if (layout.bg.image) paths.push(layout.bg.image)
  for (const el of Object.values(layout.zones)) {
    if (el?.type === 'image') paths.push(el.path)
  }
  return [...new Set(paths)]
}

export function coverItemIds(layout: CoverLayout): string[] {
  const ids: string[] = []
  if (layout.bg.card) ids.push(layout.bg.card)
  for (const el of Object.values(layout.zones)) {
    if (el?.type === 'card') ids.push(el.itemId)
  }
  return [...new Set(ids)]
}

export type RenderElement =
  | CoverText
  | { type: 'logo'; url: string; size: ElementSize }
  | { type: 'image'; url: string; size: ElementSize; shape: ImageShape }
  | { type: 'card'; url: string; size: ElementSize }

export type CoverRender = {
  bg: { color: string | null; imageUrl: string | null; imageIsCard: boolean; dim: number }
  zones: Partial<Record<ZoneKey, RenderElement>>
}

/**
 * Résout un chemin d'image de couverture en URL affichable.
 * Un poster embarqué (`/binder-covers/…`) ou une URL absolue est renvoyé tel quel ;
 * sinon on lit la table `cover_urls` fournie par l'API (chemins Supabase signés).
 * @param coverUrls table chemin -> URL renvoyée par le backend
 * @returns un résolveur utilisable par `renderCover`
 */
export function coverImageResolver(coverUrls?: Record<string, string> | null): (path: string) => string | null {
  return (path: string): string | null => {
    if (!path) return null
    if (path.startsWith('/') || path.startsWith('http')) return path
    return coverUrls?.[path] ?? null
  }
}

export function renderCover(
  layout: CoverLayout,
  imageUrl: (path: string) => string | null,
  cardUrl: (itemId: string) => string | null,
): CoverRender {
  const bgImage =
    layout.bg.kind === 'image' && layout.bg.image
      ? imageUrl(layout.bg.image)
      : layout.bg.kind === 'card' && layout.bg.card
        ? cardUrl(layout.bg.card)
        : null
  const zones: CoverRender['zones'] = {}
  for (const key of ZONES) {
    const el = layout.zones[key]
    if (!el) continue
    if (el.type === 'text') zones[key] = el
    else if (el.type === 'logo') zones[key] = { type: 'logo', url: el.url, size: el.size }
    else if (el.type === 'image') {
      const url = imageUrl(el.path)
      if (url) zones[key] = { type: 'image', url, size: el.size, shape: el.shape }
    } else {
      const url = cardUrl(el.itemId)
      if (url) zones[key] = { type: 'card', url, size: el.size }
    }
  }
  return {
    bg: {
      color: layout.bg.color,
      imageUrl: bgImage,
      imageIsCard: layout.bg.kind === 'card',
      dim: layout.bg.dim,
    },
    zones,
  }
}

export function coverHasContent(render: CoverRender | null | undefined): boolean {
  return !!render && (render.bg.imageUrl != null || Object.keys(render.zones).length > 0)
}
