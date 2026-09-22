<template>
  <div ref="rootEl" class="max-w-full min-w-0 overflow-x-hidden outline-none" tabindex="0" @keydown="onKeyDown">
    <div class="relative mx-auto w-full max-w-[1400px] min-w-0 overflow-x-hidden md:pr-12">
      <div
        ref="spreadEl"
        class="flex max-w-full items-stretch justify-center [perspective:2000px]"
        :class="pageSize ? '' : 'invisible'"
        @pointerdown="opened ? onSpreadDown($event) : undefined"
        @pointerup="opened ? onSpreadUp($event) : undefined"
      >
        <template v-if="pageSize">
          <template v-if="flipping">
            <template v-if="perView === 2">
              <div class="shrink-0" :style="{ width: `${pageSize.w}px` }" aria-hidden />
              <GoupixDexBinderSpine
                :color-hex="colorHex"
                :ring-pos="ringPos"
                :ring-color="ringColor"
                :texture-class="textureClass"
                :extra-class="closing ? 'spine-out' : 'spine-in'"
              />
            </template>
            <div class="relative z-30 shrink-0 [perspective:2000px]" :style="pageStyle(pageSize)">
              <GoupixDexBinderPage
                :page-idx="0"
                role="right"
                :size="pageSize"
                :grid="grid"
                :per-page="perPage"
                :sheet="sheet"
                :ring-pos="ringPos"
                :design="design"
                :sheen="sheen"
                :by-pocket="byPocket"
                :pockets="pockets"
                :read-only="readOnly"
                :turn-class="turnClass('right')"
                :drag-id="drag?.id ?? null"
                :over-pocket="over"
                :picker-pocket="picker"
                :clean-view="cleanView"
                :pokedex-region="pokedexRegion"
                @edge-prev="closeBinder()"
                @edge-next="go(view + 1)"
                @open-picker="openPicker"
                @card-down="onCardDown"
                @card-move="onCardMove"
                @card-up="onCardUp"
                @card-cancel="onCardCancel"
                @remove="remove"
                @detail="detail = $event"
              />
              <div
                aria-hidden
                class="absolute inset-0 z-30 [transform-origin:left_center] [transform-style:preserve-3d] md:[transform-origin:-1.125rem_center]"
                :class="coverFlipClass"
                @animationend="onCoverAnimEnd"
              >
                <div v-if="showCoverFront" class="absolute inset-0">
                  <GoupixDexBinderCover
                    :cover-style="coverProps.coverStyle"
                    :covers="coverProps.covers"
                    :name="coverProps.name"
                    :color-hex="coverProps.colorHex"
                    :texture="coverProps.texture"
                    :layout="coverProps.layout"
                    fill
                  />
                </div>
                <div
                  v-else
                  class="absolute inset-0 [transform:rotateY(180deg)] rounded-l-xl border shadow-(--app-shadow-soft)"
                  :class="sheet.page"
                >
                  <span
                    aria-hidden
                    class="pointer-events-none absolute inset-y-0 right-0 w-12 rounded-r-[inherit] bg-gradient-to-l to-transparent"
                    :class="sheet.gutter"
                  />
                  <GoupixDexBinderHoles side="right" :positions="ringPos" :cls="sheet.holes" />
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="opened">
            <template v-for="(pg, i) in visible" :key="`${String(pg)}-${i}`">
              <GoupixDexBinderSpine
                v-if="perView === 2 && pageRole(i) === 'right'"
                :color-hex="colorHex"
                :ring-pos="ringPos"
                :ring-color="ringColor"
                :texture-class="textureClass"
              />
              <GoupixDexBinderBlankPage
                v-if="pg === 'blank'"
                :size="pageSize"
                :sheet="sheet"
                :ring-pos="ringPos"
                :turn-class="turnClass('left')"
                @edge-prev="closeBinder"
              />
              <GoupixDexBinderPage
                v-else
                :page-idx="pg"
                :role="pageRole(i)"
                :size="pageSize"
                :grid="grid"
                :per-page="perPage"
                :sheet="sheet"
                :ring-pos="ringPos"
                :design="design"
                :sheen="sheen"
                :by-pocket="byPocket"
                :pockets="pockets"
                :read-only="readOnly"
                :turn-class="turnClass(pageRole(i))"
                :drag-id="drag?.id ?? null"
                :over-pocket="over"
                :picker-pocket="picker"
                :clean-view="cleanView"
                :pokedex-region="pokedexRegion"
                @edge-prev="onPageEdgePrev(i)"
                @edge-next="go(view + 1)"
                @open-picker="openPicker"
                @card-down="onCardDown"
                @card-move="onCardMove"
                @card-up="onCardUp"
                @card-cancel="onCardCancel"
                @remove="remove"
                @detail="detail = $event"
              />
            </template>
          </template>

          <template v-else>
            <div class="flex w-full justify-center">
              <div class="flex items-stretch">
                <GoupixDexBinderSpine
                  v-if="perView === 2"
                  :color-hex="colorHex"
                  :ring-pos="ringPos"
                  :ring-color="ringColor"
                  :texture-class="textureClass"
                />
                <div class="relative shrink-0 [perspective:2000px]" :style="pageStyle(pageSize)">
                  <button
                    type="button"
                    class="group absolute inset-0 [transform-style:preserve-3d]"
                    aria-label="Ouvrir le classeur"
                    title="Ouvrir le classeur"
                    @click="openTo(0)"
                  >
                    <div class="relative h-full w-full transition group-hover:brightness-110">
                      <GoupixDexBinderCover
                        :cover-style="coverProps.coverStyle"
                        :covers="coverProps.covers"
                        :name="coverProps.name"
                        :color-hex="coverProps.colorHex"
                        :texture="coverProps.texture"
                        :layout="coverProps.layout"
                        fill
                      />
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </template>
        </template>
      </div>

      <GoupixDexBinderTabs
        v-if="perView === 2 && pageSize && !cleanView"
        orientation="vertical"
        :opened="opened"
        :view="view"
        :total-views="totalViews"
        :label-of="labelOf"
        :read-only="readOnly"
        :can-remove-sheet="canRemoveSheet"
        :dragging="drag != null"
        :over-tab="over"
        @close="closeBinder"
        @open-to="openTo"
        @add-sheet="changePageCount(totalPages + 2)"
        @remove-sheet="changePageCount(totalPages - 2)"
      />
    </div>

    <GoupixDexBinderTabs
      v-if="perView === 1 && pageSize && !cleanView"
      orientation="horizontal"
      :opened="opened"
      :view="view"
      :total-views="totalViews"
      :label-of="labelOf"
      :read-only="readOnly"
      :can-remove-sheet="canRemoveSheet"
      :dragging="drag != null"
      :over-tab="over"
      @close="closeBinder"
      @open-to="openTo"
      @add-sheet="changePageCount(totalPages + 2)"
      @remove-sheet="changePageCount(totalPages - 2)"
    />

    <div
      v-if="dragItem && drag"
      ref="ghostRef"
      class="pointer-events-none fixed top-0 left-0 z-50 will-change-transform"
      :style="{ width: `${drag.w}px`, height: `${drag.h}px` }"
      aria-hidden
    >
      <div class="card-tile h-full w-full scale-105 rotate-2 shadow-2xl">
        <GoupixDexBinderCardImage :src="dragItem.image_url" alt="" />
      </div>
    </div>

    <GoupixDexBinderPickerModal
      v-model:open="pickerOpen"
      v-model:query="pickerQ"
      v-model:set-filter="pickerSet"
      :place-label="pickerPlaceLabel"
      :results="pickerResults"
      :placed-ids="placedCollectionIds"
      :set-options="pickerSets"
      :catalog-searching="catalogSearching"
      :has-collection-candidates="candidates.length > 0"
      @pick="place"
    />

    <GoupixDexDialogModal
      v-model:open="detailOpen"
      :title="detailDex?.pokemonName ?? detail?.card_name ?? 'Carte'"
      width-class="max-w-md"
    >
      <template v-if="detail">
        <div class="card-tile mx-auto aspect-[63/88] max-w-[240px]">
          <GoupixDexBinderCardImage
            :src="detail.image_url || limitlessCardImageUrl(detail.tcgdex_card_id)"
            :alt="detail.card_name"
            :fallback-src="detailDex?.artworkUrl ?? null"
          />
        </div>
        <p class="text-muted mt-3 text-center text-sm">
          {{ detail.card_name }} · {{ detail.set_name }} · {{ detail.local_id }}
        </p>
        <div class="mt-5 flex flex-col gap-2">
          <NuxtLink
            v-if="hrefBase && detail.kind === 'owned'"
            :to="`${hrefBase}${detail.collection_card_id}`"
            class="dialog-btn-secondary text-center no-underline"
            @click="detail = null"
          >
            Voir dans ma collection
          </NuxtLink>
          <p v-else-if="detail.kind === 'wanted'" class="text-muted text-center text-sm">
            Carte du catalogue — pas encore dans ta collection physique.
          </p>
          <button
            v-if="!readOnly && detail.position != null"
            type="button"
            class="dialog-btn-primary"
            @click="openPickerFromDetail"
          >
            Changer la carte de cette pochette
          </button>
        </div>
      </template>
    </GoupixDexDialogModal>
  </div>
</template>

<script setup lang="ts">
import type { BinderCandidateItem, BinderDetail, BinderPocketItem } from '~/types/binders'
import { binderColorHex } from '~/utils/binder/binder-colors'
import {
  DRAG_THRESHOLD,
  TOUCH_HOLD_MS,
  HOVER_FLIP_MS,
  SWIPE_MIN,
  fitPage,
  SPINE_W,
  useBinderPagesSpread,
  useBinderPagesState,
  type Drag,
  type PointerState,
} from '~/composables/useBinderPages'
import { buildBinderPickerResults, CATALOG_MIN_QUERY } from '~/composables/useBinderPickerResults'
import type { CatalogSearchCardHit } from '~/composables/useCardCatalog'
import type { BinderPickerItem } from '~/types/binderPicker'
import type { CoverItem } from '~/components/binder/GoupixDexBinderCover.vue'
import { binderStyle } from '~/utils/binder/binder-styles'
import { coverLayout, renderCover } from '~/utils/binder/binder-cover'
import { pokedexPlaceholderAt } from '~/utils/pokedex/kanto'
import { limitlessCardImageUrl } from '~/utils/cards/limitlessCardImage'

const props = withDefaults(
  defineProps<{
    binder: BinderDetail
    candidates?: BinderCandidateItem[]
    readOnly?: boolean
    hrefBase?: string
    cleanView?: boolean
  }>(),
  { readOnly: false, cleanView: false, candidates: undefined },
)

const emit = defineEmits<{ updated: [BinderDetail] }>()

const items = computed(() => props.binder.items)
const gridCode = computed(() => props.binder.page_grid)
const pokedexRegion = computed(() => props.binder.pokedex_region)
const designRaw = computed(() => props.binder.design)
const pageCountProp = computed(() => props.binder.page_count)
const readOnly = computed(() => props.readOnly)
const perView = useBinderPagesSpread()

const {
  grid,
  perPage,
  design,
  sheet,
  ringPos,
  ringColor,
  sheen,
  textureClass,
  pockets,
  byPocket,
  totalPages,
  totalViews,
  labelOf,
  view,
  visible,
  go,
  opened,
  opening: _opening,
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
  pageMin,
  itemById,
} = useBinderPagesState(items, gridCode, designRaw, pageCountProp, readOnly, perView)

const colorHex = computed(() => binderColorHex(props.binder.color))
const name = computed(() => props.binder.name)
const coverLayoutResolved = computed(() => coverLayout(props.binder.cover))
const coverRender = computed(() =>
  renderCover(
    coverLayoutResolved.value,
    (path) => props.binder.cover_urls?.[path] ?? null,
    (itemId) => {
      const cardId = Number(itemId)
      const item = props.binder.items.find((i) => i.collection_card_id === cardId)
      return item?.image_url ?? null
    },
  ),
)
const coverProps = computed(() => ({
  coverStyle: props.binder.style,
  covers: props.binder.covers as CoverItem[],
  name: name.value,
  colorHex: colorHex.value,
  texture: design.value.coverTexture,
  layout: binderStyle(props.binder.style) === 'custom' ? coverRender.value : null,
}))

const candidates = computed(() => props.candidates ?? props.binder.candidates ?? [])
const cleanView = computed(() => props.cleanView)
const bindersApi = useBinders()
const { searchCatalogCards } = useCardCatalog()
const toast = useToast()
const catalogHits = ref<CatalogSearchCardHit[]>([])
const catalogSearching = ref(false)
let catalogSearchTimer: ReturnType<typeof setTimeout> | null = null
let catalogSearchAbort: AbortController | null = null

const spreadEl = ref<HTMLElement | null>(null)
const frame = ref<{ top: number; width: number; vh: number } | null>(null)
const pageSize = computed(() => {
  if (!frame.value) return null
  return fitPage(
    frame.value.vh - frame.value.top - (perView.value === 1 ? 96 : 24),
    frame.value.width - (perView.value === 2 ? SPINE_W + 4 : 0),
    grid.value.cols,
    grid.value.rows,
    perView.value,
    design.value.pageNumbers,
  )
})

function pageStyle(s: { w: number; h: number }) {
  return { width: `${s.w}px`, height: `${s.h}px` }
}

function pageRole(i: number): 'left' | 'right' | 'single' {
  if (perView.value === 1) return 'single'
  return i === 0 ? 'left' : 'right'
}

let spreadResizeObserver: ResizeObserver | null = null

function measureSpread() {
  if (!spreadEl.value) return
  const r = spreadEl.value.getBoundingClientRect()
  frame.value = {
    top: Math.round(r.top + window.scrollY),
    width: Math.round(r.width),
    vh: window.innerHeight,
  }
}

function teardownSpreadMeasure() {
  spreadResizeObserver?.disconnect()
  spreadResizeObserver = null
  window.removeEventListener('resize', measureSpread)
}

function attachSpreadMeasure() {
  teardownSpreadMeasure()
  if (!spreadEl.value) return
  spreadResizeObserver = new ResizeObserver(measureSpread)
  spreadResizeObserver.observe(spreadEl.value)
  window.addEventListener('resize', measureSpread)
  measureSpread()
}

onMounted(attachSpreadMeasure)
watch(spreadEl, attachSpreadMeasure)
onUnmounted(teardownSpreadMeasure)

const coverFlipClass = computed(() => {
  if (closing.value) return half.value ? 'cover-flip-close-b' : 'cover-flip-close-a'
  return half.value ? 'cover-flip-open-b' : 'cover-flip-open-a'
})
const showCoverFront = computed(() => (closing.value ? half.value : !half.value))

function onCoverAnimEnd(e: AnimationEvent) {
  const n = e.animationName
  if (n.includes('cover-flip-open-a') || n.includes('cover-flip-close-a')) half.value = true
  else if (n.includes('cover-flip-open-b')) finishOpening()
  else if (n.includes('cover-flip-close-b')) finishClosing()
}

async function refresh(detail: BinderDetail) {
  emit('updated', detail)
}

async function commitMove(id: string, to: number) {
  const before = ov.value
  const from = pockets.value.get(id)
  const occupant = byPocket.value.get(to)
  const entries: [string, number][] = [[id, to]]
  if (occupant && from != null) entries.push([occupant.id, from])
  patchOv(entries)
  try {
    const detail = await bindersApi.movePocket(props.binder.id, id, to)
    await refresh(detail)
  } catch {
    ov.value = before
    toast.add({ title: 'Déplacement non enregistré', color: 'error' })
  }
}

async function remove(key: string) {
  const before = ov.value
  patchOv([], undefined, key)
  try {
    const detail = await bindersApi.removeFromPocket(props.binder.id, key)
    const item = itemById.value.get(key)
    toast.add({
      title:
        item?.kind === 'wanted'
          ? 'Retirée du classeur (carte catalogue)'
          : 'Retirée du classeur — elle reste dans ta collection',
      color: 'success',
    })
    await refresh(detail)
  } catch {
    ov.value = before
    toast.add({ title: 'Retrait impossible', color: 'error' })
  }
}

const picker = ref<number | null>(null)
const pickerOpen = computed({
  get: () => picker.value != null,
  set: (v) => {
    if (!v) picker.value = null
  },
})
const pickerQ = ref('')
const pickerSet = ref('')
const pickerSets = computed(() => {
  const sets = new Set(candidates.value.map((c) => c.set_name))
  for (const hit of catalogHits.value) {
    if (hit.set_name?.trim()) sets.add(hit.set_name.trim())
  }
  return [...sets].sort((a, b) => a.localeCompare(b, 'fr'))
})
const pickerResults = computed(() =>
  buildBinderPickerResults(candidates.value, pockets.value, pickerQ.value, pickerSet.value, catalogHits.value),
)

watch(pickerQ, (q) => {
  if (catalogSearchTimer) clearTimeout(catalogSearchTimer)
  const trimmed = q.trim()
  if (trimmed.length < CATALOG_MIN_QUERY) {
    catalogHits.value = []
    catalogSearching.value = false
    catalogSearchAbort?.abort()
    return
  }
  catalogSearching.value = true
  catalogSearchTimer = setTimeout(() => {
    catalogSearchAbort?.abort()
    const controller = new AbortController()
    catalogSearchAbort = controller
    void searchCatalogCards('fr', trimmed)
      .then((res) => {
        if (!controller.signal.aborted) catalogHits.value = res.cards
      })
      .catch(() => {
        if (!controller.signal.aborted) catalogHits.value = []
      })
      .finally(() => {
        if (!controller.signal.aborted) catalogSearching.value = false
      })
  }, 300)
})

watch(pickerOpen, (isOpen) => {
  if (!isOpen) {
    catalogHits.value = []
    catalogSearching.value = false
  }
})

const pickerPlaceLabel = computed(() => {
  if (picker.value == null) {
    return undefined
  }
  const page = Math.floor(picker.value / perPage.value) + 1
  const slot = (picker.value % perPage.value) + 1
  return `Emplacement visé : page ${page} · pochette ${slot}`
})

const placedCollectionIds = computed(() => {
  const ids = new Set<number>()
  for (const key of pockets.value.keys()) {
    if (key.startsWith('i:')) {
      ids.add(Number(key.slice(2)))
    }
  }
  return ids
})

function openPickerFromDetail(): void {
  const position = detail.value?.position
  if (position == null) {
    return
  }
  detail.value = null
  openPicker(position)
}

function openPicker(pocket: number) {
  picker.value = pocket
  pickerQ.value = ''
  pickerSet.value = ''
}

function advancePicker(fromPocket: number) {
  const next = firstFreeIn(view.value, fromPocket) ?? firstFreeIn(view.value)
  picker.value = next
}

async function place(c: BinderPickerItem) {
  const pocket = picker.value
  if (pocket == null) return
  toast.add({ title: `${c.card_name} · ${pocketLabel(pocket)}`, color: 'success' })

  if (c.source === 'catalog') {
    const occupant = byPocket.value.get(pocket)
    advancePicker(pocket)
    const before = ov.value
    try {
      if (occupant) await bindersApi.removeFromPocket(props.binder.id, occupant.id)
      const detail = await bindersApi.placeCatalogInPocket(props.binder.id, c.tcgdex_card_id, pocket, 'fr')
      await refresh(detail)
    } catch {
      ov.value = before
      toast.add({ title: 'Carte non rangée', description: 'Catalogue ou réseau indisponible.', color: 'error' })
    }
    return
  }

  const key = `i:${c.collection_card_id}`
  if (pockets.value.has(key)) {
    advancePicker(pocket)
    await commitMove(key, pocket)
    return
  }
  const occupant = byPocket.value.get(pocket)
  advancePicker(pocket)
  const before = ov.value
  patchOv(
    [[key, pocket]],
    {
      id: key,
      kind: 'owned',
      collection_card_id: c.collection_card_id,
      card_name: c.card_name,
      set_name: c.set_name,
      local_id: c.local_id,
      tcgdex_card_id: c.tcgdex_card_id,
      image_url: c.image_url,
      quantity: c.quantity,
      position: pocket,
      created_at: '',
    },
    occupant?.id,
  )
  try {
    if (occupant) await bindersApi.removeFromPocket(props.binder.id, occupant.id)
    const detail = await bindersApi.placeItemInPocket(props.binder.id, c.collection_card_id, pocket)
    await refresh(detail)
  } catch {
    ov.value = before
    toast.add({ title: 'Carte non rangée', color: 'error' })
  }
}

async function changePageCount(next: number) {
  const before = pageMin.value
  pageMin.value = next
  try {
    const detail = await bindersApi.setPageCount(props.binder.id, next)
    await refresh(detail)
  } catch {
    pageMin.value = before
    toast.add({ title: 'Pages non enregistrées', color: 'error' })
  }
}

const detail = ref<BinderPocketItem | null>(null)
const detailDex = computed(() => pokedexPlaceholderAt(pokedexRegion.value, detail.value?.position ?? -1))
const detailOpen = computed({
  get: () => detail.value != null,
  set: (v) => {
    if (!v) detail.value = null
  },
})

const drag = ref<Drag | null>(null)
const dragItem = computed(() => (drag.value ? (itemById.value.get(drag.value.id) ?? null) : null))
const over = ref<string | null>(null)
const ghostRef = ref<HTMLElement | null>(null)
const pointer = ref<PointerState | null>(null)
const hoverKey = ref<string | null>(null)
const hoverTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const suppressClick = ref(false)
const swipe = ref<{ x: number; y: number; id: number } | null>(null)

function placeGhost(x: number, y: number) {
  const p = pointer.value
  const el = ghostRef.value
  if (!p || !el) return
  el.style.transform = `translate3d(${x - p.offX}px, ${y - p.offY}px, 0)`
}

function setHover(key: string | null) {
  if (hoverKey.value === key) return
  hoverKey.value = key
  if (hoverTimer.value) clearTimeout(hoverTimer.value)
  hoverTimer.value = null
  if (!key) return
  hoverTimer.value = setTimeout(() => {
    hoverTimer.value = null
    const [kind, value] = key.split(':')
    if (kind === 'tab') go(Number(value))
    else if (value === 'next') go(view.value + 1)
    else if (value === 'prev') go(view.value - 1)
  }, HOVER_FLIP_MS)
}

function clearPointer() {
  const p = pointer.value
  if (p?.holdTimer) clearTimeout(p.holdTimer)
  pointer.value = null
  setHover(null)
  drag.value = null
  over.value = null
}

function activateDrag() {
  const p = pointer.value
  if (!p || p.active) return
  p.active = true
  if (p.holdTimer) clearTimeout(p.holdTimer)
  p.holdTimer = null
  picker.value = null
  drag.value = { id: p.id, w: p.w, h: p.h }
}

function onCardDown(e: PointerEvent, id: string, el: HTMLElement) {
  if (readOnly.value || e.button !== 0 || pointer.value) return
  suppressClick.value = false
  const rect = el.getBoundingClientRect()
  const p: PointerState = {
    id,
    pointerId: e.pointerId,
    startX: e.clientX,
    startY: e.clientY,
    lastX: e.clientX,
    lastY: e.clientY,
    offX: e.clientX - rect.left,
    offY: e.clientY - rect.top,
    w: rect.width,
    h: rect.height,
    active: false,
    holdTimer: null,
  }
  pointer.value = p
  if (e.pointerType !== 'mouse') {
    p.holdTimer = setTimeout(activateDrag, TOUCH_HOLD_MS)
  }
}

function onCardMove(e: PointerEvent) {
  const p = pointer.value
  if (!p || p.active || p.pointerId !== e.pointerId) return
  p.lastX = e.clientX
  p.lastY = e.clientY
  const dist = Math.hypot(e.clientX - p.startX, e.clientY - p.startY)
  if (e.pointerType === 'mouse') {
    if (dist > DRAG_THRESHOLD) activateDrag()
  } else if (dist > DRAG_THRESHOLD + 2) {
    clearPointer()
  }
}

function onCardUp(e: PointerEvent) {
  const p = pointer.value
  if (!p || p.active || p.pointerId !== e.pointerId) return
  clearPointer()
}

function onCardCancel() {
  if (pointer.value && !pointer.value.active) clearPointer()
}

watch(drag, (d, _, onCleanup) => {
  if (!d) return
  const onMove = (e: PointerEvent) => {
    const p = pointer.value
    if (!p?.active || p.pointerId !== e.pointerId) return
    placeGhost(e.clientX, e.clientY)
    const under = document.elementFromPoint(e.clientX, e.clientY)
    const pocketEl = under?.closest('[data-pocket]') as HTMLElement | null
    const tabEl = under?.closest('[data-tab]') as HTMLElement | null
    const key = pocketEl ? `pocket:${pocketEl.dataset.pocket}` : tabEl ? `tab:${tabEl.dataset.tab}` : null
    over.value = key
    setHover(tabEl ? `tab:${tabEl.dataset.tab}` : null)
  }
  const onUp = (e: PointerEvent) => {
    const p = pointer.value
    if (!p || p.pointerId !== e.pointerId) return
    if (!p.active) {
      clearPointer()
      return
    }
    suppressClick.value = true
    const under = document.elementFromPoint(e.clientX, e.clientY)
    const pocketEl = under?.closest('[data-pocket]') as HTMLElement | null
    const tabEl = under?.closest('[data-tab]') as HTMLElement | null
    const id = p.id
    clearPointer()
    if (pocketEl) {
      const to = Number(pocketEl.dataset.pocket)
      if (to !== pockets.value.get(id)) void commitMove(id, to)
    } else if (tabEl) {
      const v = Number(tabEl.dataset.tab)
      go(v)
      void commitMoveToView(id, v)
    }
  }
  const block = (e: TouchEvent) => e.preventDefault()
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
  document.addEventListener('touchmove', block, { passive: false })
  onCleanup(() => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    document.removeEventListener('touchmove', block)
  })
})

async function commitMoveToView(id: string, v: number) {
  const pocket = firstFreeIn(v)
  if (pocket == null) {
    toast.add({ title: 'Ces pages sont pleines', color: 'error' })
    return
  }
  go(v)
  await commitMove(id, pocket)
}

function onSpreadDown(e: PointerEvent) {
  if (e.pointerType === 'mouse') return
  swipe.value = { x: e.clientX, y: e.clientY, id: e.pointerId }
}

function onSpreadUp(e: PointerEvent) {
  const s = swipe.value
  swipe.value = null
  if (!s || s.id !== e.pointerId || pointer.value?.active) return
  const dx = e.clientX - s.x
  const dy = e.clientY - s.y
  if (Math.abs(dx) < SWIPE_MIN || Math.abs(dy) > 50) return
  if (dx < 0) go(view.value + 1)
  else if (view.value === 0) closeBinder()
  else go(view.value - 1)
}

function onPageEdgePrev(i: number) {
  if (view.value === 0 && i === 0) closeBinder()
  else go(view.value - 1)
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && pickerOpen.value) {
    e.preventDefault()
    picker.value = null
    return
  }
  if (pickerOpen.value || flipping.value) return
  if (!opened.value) {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      openTo(0)
    }
    return
  }
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    go(view.value + 1)
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    if (view.value === 0) closeBinder()
    else go(view.value - 1)
  }
}
</script>
