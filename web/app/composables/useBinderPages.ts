import { layoutPockets, pageGrid, pocketsPerPage } from '~/utils/binder/binder-pages'
import {
  binderDesign,
  coverTextureClass,
  pocketSheen,
  ringHex,
  ringPositions,
  SHEETS,
  type BinderDesign,
} from '~/utils/binder/binder-design'
import type { BinderCandidateItem, BinderPocketItem } from '~/types/binders'

export type { BinderDesign }

export const DRAG_THRESHOLD = 6
export const TOUCH_HOLD_MS = 220
export const HOVER_FLIP_MS = 450
export const SWIPE_MIN = 60
export const FLIP_FALLBACK_MS = 900
export const PICKER_MAX = 80

export const PAD = { top: 14, bottom: 14, numbers: 22, gutter: 28, outer: 30, gap: 9 }
export const SPINE_W = 36
export const BOTTOM_GAP = { desktop: 24, mobile: 96 }
export const MIN_PAGE_H = 240
export const SPREAD_QUERY = '(min-width: 768px)'

export type Dir = 'next' | 'prev'
export type Role = 'left' | 'right' | 'single'
export type PageSize = { w: number; h: number; cardW: number; padB: number }

/**
 *
 */
export function refIdOf(key: string): string {
  return key.slice(2)
}

/**
 *
 */
export function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
}

/**
 *
 */
export function fitPage(
  availH: number,
  availW: number,
  cols: number,
  rows: number,
  perView: number,
  pageNumbers: boolean,
): PageSize {
  const padB = PAD.bottom + (pageNumbers ? PAD.numbers : 0)
  const chromeH = PAD.top + padB + 2 + (rows - 1) * PAD.gap
  const chromeW = PAD.gutter + PAD.outer + 2 + (cols - 1) * PAD.gap
  let cardW = ((Math.max(availH, MIN_PAGE_H) - chromeH) / rows) * (63 / 88)
  const maxW = availW / perView
  if (cols * cardW + chromeW > maxW) cardW = (maxW - chromeW) / cols
  cardW = Math.max(40, Math.floor(cardW))
  const cardH = (cardW * 88) / 63
  return {
    w: cols * cardW + chromeW,
    h: Math.ceil(rows * cardH + chromeH),
    cardW,
    padB,
  }
}

type Overrides = {
  key: string
  map: Map<string, number>
  extra: Map<string, BinderPocketItem>
  removed: Set<string>
}

type Drag = { id: string; w: number; h: number }
type PointerState = {
  id: string
  pointerId: number
  startX: number
  startY: number
  lastX: number
  lastY: number
  offX: number
  offY: number
  w: number
  h: number
  active: boolean
  holdTimer: ReturnType<typeof setTimeout> | null
}

/**
 *
 */
export function useBinderPagesSpread() {
  const perView = ref(2)
  onMounted(() => {
    const mq = window.matchMedia(SPREAD_QUERY)
    const sync = () => {
      perView.value = mq.matches ? 2 : 1
    }
    sync()
    mq.addEventListener('change', sync)
    onUnmounted(() => mq.removeEventListener('change', sync))
  })
  return perView
}

/**
 *
 */
export function useBinderPagesState(
  items: Ref<BinderPocketItem[]>,
  gridCode: Ref<string | null>,
  designRaw: Ref<unknown>,
  pageCountProp: Ref<number>,
  readOnly: Ref<boolean>,
  perView: Ref<number>,
) {
  const grid = computed(() => pageGrid(gridCode.value))
  const perPage = computed(() => pocketsPerPage(grid.value))
  const design = computed(() => binderDesign(designRaw.value))
  const sheet = computed(() => SHEETS[design.value.pageColor])
  const ringPos = computed(() => ringPositions(design.value.ringCount))
  const ringColor = computed(() => ringHex(design.value.ringFinish))
  const sheen = computed(() => pocketSheen(design.value.pocketFinish))
  const textureClass = computed(() => coverTextureClass(design.value.coverTexture))

  const serverKey = computed(() => items.value.map((i) => `${i.id}:${i.position ?? ''}`).join('|'))
  const base = computed(() =>
    layoutPockets(items.value.map((i) => ({ id: i.id, position: i.position, created_at: i.created_at }))),
  )

  const ov = ref<Overrides>({ key: '', map: new Map(), extra: new Map(), removed: new Set() })
  watch(serverKey, () => {
    ov.value = { key: '', map: new Map(), extra: new Map(), removed: new Set() }
  })

  const live = computed(() => (ov.value.key === serverKey.value ? ov.value : null))

  const pockets = computed(() => {
    const m = new Map(base.value)
    const l = live.value
    if (l) {
      for (const id of l.removed) m.delete(id)
      for (const [id, p] of l.map) if (!l.removed.has(id)) m.set(id, p)
    }
    return m
  })

  const itemById = computed(() => {
    const m = new Map<string, BinderPocketItem>()
    for (const i of items.value) m.set(i.id, i)
    const l = live.value
    if (l) for (const [id, it] of l.extra) m.set(id, it)
    return m
  })

  const byPocket = computed(() => {
    const m = new Map<number, BinderPocketItem>()
    for (const [id, p] of pockets.value) {
      const item = itemById.value.get(id)
      if (item) m.set(p, item)
    }
    return m
  })

  const pageMin = ref(pageCountProp.value)
  watch(pageCountProp, (v) => {
    pageMin.value = v
  })

  const maxPocket = computed(() => Math.max(-1, ...Array.from(pockets.value.values())))
  const usedPages = computed(() => Math.max(1, Math.ceil((maxPocket.value + 1) / perPage.value)))
  const autoPages = computed(() => (readOnly.value ? usedPages.value : usedPages.value + 1))
  const evenAdjust = (p: number) => (perView.value === 2 && (p - 1) % 2 === 1 ? p + 1 : p)
  const minTotal = computed(() => evenAdjust(autoPages.value))
  const totalPages = computed(() => Math.max(minTotal.value, evenAdjust(Math.max(0, pageMin.value))))
  const totalViews = computed(() => (perView.value === 2 ? 1 + (totalPages.value - 1) / 2 : totalPages.value))

  /**
   *
   */
  function pagesOf(v: number): (number | 'blank')[] {
    if (perView.value === 1) return [v]
    return v === 0 ? ['blank', 0] : [2 * v - 1, 2 * v]
  }

  /**
   *
   */
  function labelOf(v: number): string {
    const ps = pagesOf(v).filter((p): p is number => p !== 'blank')
    return ps.length === 2 ? `${ps[0] + 1}–${ps[1] + 1}` : `${ps[0] + 1}`
  }

  const nav = ref<{ view: number; dir: Dir | null }>({ view: 0, dir: null })
  const view = computed(() => Math.min(nav.value.view, totalViews.value - 1))
  const visible = computed(() => pagesOf(view.value))

  /**
   *
   */
  function go(v: number) {
    const target = Math.max(0, Math.min(totalViews.value - 1, v))
    nav.value = { view: target, dir: target >= nav.value.view ? 'next' : 'prev' }
  }

  const opened = ref(false)
  const opening = ref(false)
  const closing = ref(false)
  const half = ref(false)
  const pendingView = ref(0)
  const flipping = computed(() => opening.value || closing.value)

  /**
   *
   */
  function finishOpening() {
    opening.value = false
    half.value = false
    opened.value = true
    nav.value = { view: 0, dir: null }
    if (pendingView.value > 0) {
      const target = pendingView.value
      setTimeout(() => go(target), 80)
    }
  }

  /**
   *
   */
  function finishClosing() {
    closing.value = false
    half.value = false
    opened.value = false
    nav.value = { view: 0, dir: null }
  }

  /**
   *
   */
  function openTo(v: number) {
    if (opened.value) {
      go(v)
      return
    }
    if (flipping.value) return
    pendingView.value = v
    half.value = false
    opening.value = true
  }

  /**
   *
   */
  function closeBinder() {
    if (!opened.value || flipping.value) return
    const start = () => {
      half.value = false
      closing.value = true
    }
    if (view.value > 0) {
      go(0)
      setTimeout(start, 560)
      return
    }
    start()
  }

  watch(flipping, (on, _, onCleanup) => {
    if (!on) return
    const t = setTimeout(() => {
      if (opening.value) finishOpening()
      else if (closing.value) finishClosing()
    }, FLIP_FALLBACK_MS)
    onCleanup(() => clearTimeout(t))
  })

  /**
   *
   */
  function patchOv(entries: [string, number][], extra?: BinderPocketItem, removedKey?: string) {
    const key = serverKey.value
    const same = ov.value.key === key
    const map = new Map(same ? ov.value.map : [])
    const ex = new Map(same ? ov.value.extra : [])
    const removed = new Set(same ? ov.value.removed : [])
    for (const [k, v] of entries) {
      map.set(k, v)
      removed.delete(k)
    }
    if (extra) ex.set(extra.id, extra)
    if (removedKey) removed.add(removedKey)
    ov.value = { key, map, extra: ex, removed }
  }

  /**
   *
   */
  function firstFreeIn(v: number, after = -1): number | null {
    for (const pg of pagesOf(v)) {
      if (pg === 'blank') continue
      for (let k = 0; k < perPage.value; k++) {
        const pocket = pg * perPage.value + k
        if (pocket > after && !byPocket.value.has(pocket)) return pocket
      }
    }
    return null
  }

  const pocketLabel = (p: number) => `Page ${Math.floor(p / perPage.value) + 1} · Pochette ${(p % perPage.value) + 1}`

  /**
   *
   */
  function turnClass(role: Role): string {
    if (!nav.value.dir) return ''
    if (perView.value === 1) return nav.value.dir === 'next' ? 'page-slide-next' : 'page-slide-prev'
    if (nav.value.dir === 'next') return role === 'right' ? 'page-fade' : 'page-turn-left'
    return role === 'left' ? 'page-fade' : 'page-turn-right'
  }

  const canRemoveSheet = computed(() => !readOnly.value && totalPages.value > minTotal.value)

  return {
    grid,
    perPage,
    design,
    sheet,
    ringPos,
    ringColor,
    sheen,
    textureClass,
    pockets,
    itemById,
    byPocket,
    pageMin,
    totalPages,
    totalViews,
    pagesOf,
    labelOf,
    nav,
    view,
    visible,
    go,
    opened,
    opening,
    closing,
    half,
    flipping,
    openTo,
    closeBinder,
    finishOpening,
    finishClosing,
    patchOv,
    firstFreeIn,
    pocketLabel,
    turnClass,
    canRemoveSheet,
    ov,
    serverKey,
  }
}

/**
 *
 */
export function filterPickerCandidates(
  candidates: BinderCandidateItem[],
  pockets: Map<string, number>,
  q: string,
  fSet: string,
): BinderCandidateItem[] {
  const setName = typeof fSet === 'string' ? fSet.trim() : ''
  const needle = normalize(q.trim())
  return candidates
    .filter(
      (c) =>
        (!setName || c.set_name === setName) &&
        (!needle || normalize(`${c.card_name} ${c.set_name} ${c.local_id}`).includes(needle)),
    )
    .sort(
      (a, b) => (pockets.has(`i:${a.collection_card_id}`) ? 1 : 0) - (pockets.has(`i:${b.collection_card_id}`) ? 1 : 0),
    )
    .slice(0, PICKER_MAX)
}

export type { Drag, PointerState, Overrides }
