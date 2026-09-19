// Options de design d'un classeur, stockées en json dans `binders.design`.

export const PAGE_COLORS = [
  { code: 'black', label: 'Noires', description: 'Feuilles sombres, le classique' },
  { code: 'white', label: 'Blanches', description: 'Feuilles claires' },
  { code: 'clear', label: 'Transparentes', description: 'Feuilles translucides' },
] as const

export const RING_FINISHES = [
  { code: 'silver', label: 'Argent', hex: '#d4d4d8' },
  { code: 'black', label: 'Noir', hex: '#52525b' },
  { code: 'gold', label: 'Doré', hex: '#d9b45f' },
] as const

export const RING_COUNTS = [2, 3, 4, 9] as const

export const POCKET_FINISHES = [
  { code: 'glossy', label: 'Brillantes' },
  { code: 'matte', label: 'Mates' },
  { code: 'clear', label: 'Sans reflet' },
] as const

export const COVER_TEXTURES = [
  { code: 'plain', label: 'Lisse' },
  { code: 'leather', label: 'Cuir' },
  { code: 'fabric', label: 'Tissu' },
  { code: 'holo', label: 'Holo' },
] as const

export type PageColor = (typeof PAGE_COLORS)[number]['code']
export type RingFinish = (typeof RING_FINISHES)[number]['code']
export type RingCount = (typeof RING_COUNTS)[number]
export type PocketFinish = (typeof POCKET_FINISHES)[number]['code']
export type CoverTexture = (typeof COVER_TEXTURES)[number]['code']

export type BinderDesign = {
  pageColor: PageColor
  ringFinish: RingFinish
  ringCount: RingCount
  pocketFinish: PocketFinish
  coverTexture: CoverTexture
  pageNumbers: boolean
}

export const DEFAULT_DESIGN: BinderDesign = {
  pageColor: 'black',
  ringFinish: 'silver',
  ringCount: 4,
  pocketFinish: 'glossy',
  coverTexture: 'plain',
  pageNumbers: true,
}

function pick<T extends string | number>(value: unknown, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly unknown[]).includes(value) ? (value as T) : fallback
}

/** Design normalisé depuis le json — tolère null, champs manquants ou inconnus */
export function binderDesign(raw: unknown): BinderDesign {
  const d = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return {
    pageColor: pick(
      d.pageColor,
      PAGE_COLORS.map((p) => p.code),
      DEFAULT_DESIGN.pageColor,
    ),
    ringFinish: pick(
      d.ringFinish,
      RING_FINISHES.map((r) => r.code),
      DEFAULT_DESIGN.ringFinish,
    ),
    ringCount: pick(d.ringCount, RING_COUNTS, DEFAULT_DESIGN.ringCount),
    pocketFinish: pick(
      d.pocketFinish,
      POCKET_FINISHES.map((p) => p.code),
      DEFAULT_DESIGN.pocketFinish,
    ),
    coverTexture: pick(
      d.coverTexture,
      COVER_TEXTURES.map((t) => t.code),
      DEFAULT_DESIGN.coverTexture,
    ),
    pageNumbers: typeof d.pageNumbers === 'boolean' ? d.pageNumbers : DEFAULT_DESIGN.pageNumbers,
  }
}

/** Rendu des feuilles selon leur couleur — classes Tailwind partagées */
export const SHEETS = {
  black: {
    page: 'border-white/10 bg-[#17161a]',
    pocketBg: 'bg-black/30',
    pocketRing: 'ring-white/[0.06]',
    number: 'text-white/35',
    holes: 'bg-black/80',
    gutter: 'from-black/35',
  },
  white: {
    page: 'border-black/10 bg-[#f3f1ec]',
    pocketBg: 'bg-black/[0.08]',
    pocketRing: 'ring-black/10',
    number: 'text-black/40',
    holes: 'bg-black/40',
    gutter: 'from-black/15',
  },
  clear: {
    page: 'border-white/15 bg-white/[0.06] backdrop-blur-[2px]',
    pocketBg: 'bg-white/[0.05]',
    pocketRing: 'ring-white/10',
    number: 'text-(--app-ink-soft)',
    holes: 'bg-black/60',
    gutter: 'from-black/25',
  },
} as const

/** Dégradé de reflet d'une pochette selon sa finition (null = sans reflet) */
export function pocketSheen(finish: PocketFinish): string | null {
  if (finish === 'glossy') return 'from-white/[0.09] via-transparent to-black/10'
  if (finish === 'matte') return 'from-white/[0.03] via-transparent to-black/5'
  return null
}

/** Hauteurs relatives des anneaux (et des perforations en face) */
export function ringPositions(count: RingCount): number[] {
  if (count === 2) return [0.25, 0.75]
  if (count === 3) return [0.15, 0.5, 0.85]
  if (count === 9) return Array.from({ length: 9 }, (_, i) => 0.08 + (i * 0.84) / 8)
  return [0.13, 0.37, 0.63, 0.87]
}

const DEFAULT_DESIGN_RING_HEX = '#d4d4d8'

export function ringHex(finish: RingFinish): string {
  return RING_FINISHES.find((r) => r.code === finish)?.hex ?? DEFAULT_DESIGN_RING_HEX
}

/** Calque de texture posé sur la couverture et le dos du classeur */
export function coverTextureClass(texture: CoverTexture): string {
  switch (texture) {
    case 'leather':
      return 'bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.09)_1px,transparent_1.6px)] bg-[size:5px_5px] shadow-[inset_0_0_48px_rgba(0,0,0,0.45)]'
    case 'fabric':
      return 'bg-[repeating-linear-gradient(45deg,rgba(255,255,255,0.06)_0_2px,transparent_2px_5px),repeating-linear-gradient(-45deg,rgba(0,0,0,0.10)_0_2px,transparent_2px_5px)]'
    case 'holo':
      return 'bg-[linear-gradient(115deg,rgba(255,80,180,0.30),rgba(80,220,255,0.30)_30%,rgba(255,230,80,0.30)_55%,rgba(140,80,255,0.30)_80%,rgba(80,255,180,0.30))] mix-blend-screen'
    default:
      return ''
  }
}
