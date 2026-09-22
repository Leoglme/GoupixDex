<template>
  <section
    :aria-label="`Page ${pageIdx + 1}`"
    :style="{ width: `${size.w}px`, height: `${size.h}px` }"
    class="relative z-0 shrink-0 overflow-hidden border shadow-(--app-shadow-soft) [backface-visibility:hidden]"
    :class="[
      sheet.page,
      role === 'left' ? 'rounded-l-xl' : role === 'right' ? 'rounded-r-xl' : 'rounded-xl',
      turnClass,
    ]"
  >
    <span
      aria-hidden
      class="pointer-events-none absolute inset-y-0 w-12 to-transparent"
      :class="[
        sheet.gutter,
        holesLeft ? 'left-0 rounded-l-[inherit] bg-gradient-to-r' : 'right-0 rounded-r-[inherit] bg-gradient-to-l',
      ]"
    />
    <GoupixDexBinderHoles :side="holesLeft ? 'left' : 'right'" :positions="ringPos" :cls="sheet.holes" />

    <button
      v-if="role === 'left' || role === 'single'"
      type="button"
      class="group/edge absolute inset-y-0 left-0 z-10 flex w-7 cursor-pointer items-center justify-center text-(--app-faint) transition hover:bg-gradient-to-r hover:from-black/25 hover:to-transparent hover:text-(--app-ink)"
      aria-label="Pages précédentes"
      @click="$emit('edge-prev')"
    >
      <UIcon name="i-lucide-chevron-left" class="opacity-40 group-hover/edge:opacity-100" />
    </button>
    <button
      v-if="role === 'right' || role === 'single'"
      type="button"
      class="group/edge absolute inset-y-0 right-0 z-10 flex w-7 cursor-pointer items-center justify-center text-(--app-faint) transition hover:bg-gradient-to-l hover:from-black/25 hover:to-transparent hover:text-(--app-ink)"
      aria-label="Pages suivantes"
      @click="$emit('edge-next')"
    >
      <UIcon name="i-lucide-chevron-right" class="opacity-40 group-hover/edge:opacity-100" />
    </button>

    <div
      class="grid"
      :style="{
        gridTemplateColumns: `repeat(${grid.cols}, ${size.cardW}px)`,
        gap: `${padGap}px`,
        padding: `${padTop}px ${padRight}px ${size.padB}px ${padLeft}px`,
      }"
    >
      <div
        v-for="k in perPage"
        :key="k - 1"
        :data-pocket="pageIdx * perPage + (k - 1)"
        class="group/p relative aspect-[63/88] rounded-md shadow-[inset_0_2px_8px_rgba(0,0,0,.45)] transition"
        :class="[sheet.pocketBg, pocketClass(pageIdx * perPage + (k - 1))]"
        @click="onPocketClick(pageIdx * perPage + (k - 1))"
      >
        <div
          v-if="displayItem(pageIdx * perPage + (k - 1))"
          :key="displayItem(pageIdx * perPage + (k - 1))!.id"
          class="absolute inset-[3%]"
        >
          <div
            role="button"
            tabindex="0"
            class="block h-full w-full cursor-pointer touch-manipulation select-none active:cursor-grabbing"
            @click.stop="onCardClick(pageIdx * perPage + (k - 1))"
            @pointerdown="onCardPointer($event, pageIdx * perPage + (k - 1))"
            @pointermove="(e) => $emit('card-move', e)"
            @pointerup="(e) => $emit('card-up', e)"
            @pointercancel="$emit('card-cancel')"
          >
            <div
              class="card-tile h-full w-full transition"
              :class="[
                isSource(pageIdx * perPage + (k - 1)) ? 'opacity-30' : '',
                displayItem(pageIdx * perPage + (k - 1))!.kind === 'wanted' && !previewComplete
                  ? 'opacity-75 grayscale-[0.35]'
                  : '',
              ]"
            >
              <GoupixDexBinderCardImage
                :src="
                  displayItem(pageIdx * perPage + (k - 1))!.image_url ||
                  limitlessCardImageUrl(displayItem(pageIdx * perPage + (k - 1))!.tcgdex_card_id)
                "
                :alt="displayItem(pageIdx * perPage + (k - 1))!.card_name"
                :fallback-src="placeholderAt(pageIdx * perPage + (k - 1))?.artworkUrl ?? null"
              />
              <span
                v-if="displayItem(pageIdx * perPage + (k - 1))!.kind === 'wanted' && !previewComplete"
                class="tile-badge num top-1 left-1 z-10 !bg-black/70 !text-white"
              >
                Manquante
              </span>
              <span
                v-else-if="displayItem(pageIdx * perPage + (k - 1))!.quantity > 1"
                class="tile-badge num top-1 right-1"
              >
                ×{{ displayItem(pageIdx * perPage + (k - 1))!.quantity }}
              </span>
            </div>
          </div>
        </div>
        <GoupixDexBinderPokedexPlaceholder
          v-if="!itemAt(pageIdx * perPage + (k - 1)) && placeholderAt(pageIdx * perPage + (k - 1))"
          :placeholder="placeholderAt(pageIdx * perPage + (k - 1))!"
        />
        <button
          v-if="itemAt(pageIdx * perPage + (k - 1)) && !readOnly"
          type="button"
          aria-label="Retirer du classeur"
          class="absolute top-1 left-1 z-20 flex h-6 w-6 items-center justify-center rounded-full border border-white/20 bg-black/65 text-white/90 opacity-0 shadow backdrop-blur-sm transition group-hover/p:opacity-100 hover:!bg-(--app-red) pointer-coarse:opacity-100"
          @pointerdown.stop
          @click.stop="$emit('remove', itemAt(pageIdx * perPage + (k - 1))!.id)"
        >
          <UIcon name="i-lucide-x" class="h-3 w-3" />
        </button>
        <UIcon
          v-if="!displayItem(pageIdx * perPage + (k - 1)) && !readOnly"
          name="i-lucide-plus"
          class="pointer-events-none absolute top-1/2 left-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-(--app-faint) opacity-0 transition group-hover/p:opacity-70"
          :class="pickerPocket === pageIdx * perPage + (k - 1) ? 'text-(--app-accent) opacity-90' : ''"
        />
        <span
          v-if="sheen"
          aria-hidden
          class="pointer-events-none absolute inset-0 rounded-md bg-gradient-to-br"
          :class="sheen"
        />
        <span
          v-if="design.pocketFinish === 'glossy'"
          aria-hidden
          class="pointer-events-none absolute inset-x-[8%] top-0 h-px bg-white/20"
        />
      </div>
    </div>
    <span
      v-if="design.pageNumbers"
      class="num absolute bottom-2 text-[11px]"
      :class="[sheet.number, holesLeft ? 'right-4' : 'left-4']"
    >
      {{ pageIdx + 1 }}
    </span>
  </section>
</template>

<script setup lang="ts">
import type { BinderDesign } from '~/utils/binder/binder-design'
import type { PageGrid } from '~/utils/binder/binder-pages'
import type { BinderPocketItem } from '~/types/binders'
import type { PageSize, Role } from '~/composables/useBinderPages'
import { pokedexPlaceholderAt } from '~/utils/pokedex/kanto'
import { limitlessCardImageUrl } from '~/utils/cards/limitlessCardImage'

const padTop = 14
const padGap = 9

const props = defineProps<{
  pageIdx: number
  role: Role
  size: PageSize
  grid: PageGrid
  perPage: number
  sheet: { page: string; pocketBg: string; pocketRing: string; number: string; holes: string; gutter: string }
  ringPos: number[]
  design: BinderDesign
  sheen: string | null
  byPocket: Map<number, BinderPocketItem>
  pockets: Map<string, number>
  readOnly: boolean
  turnClass: string
  dragId: string | null
  overPocket: string | null
  pickerPocket: number | null
  previewComplete?: boolean
  pokedexRegion?: string | null
}>()

const emit = defineEmits<{
  'edge-prev': []
  'edge-next': []
  'open-picker': [number]
  'card-down': [PointerEvent, string, HTMLElement]
  'card-move': [PointerEvent]
  'card-up': [PointerEvent]
  'card-cancel': []
  remove: [string]
  detail: [BinderPocketItem]
}>()

const holesLeft = computed(() => props.role !== 'left')
const padLeft = computed(() => (holesLeft.value ? 28 : 30))
const padRight = computed(() => (holesLeft.value ? 30 : 28))

function itemAt(pocket: number) {
  return props.byPocket.get(pocket) ?? null
}

function placeholderAt(pocket: number) {
  return pokedexPlaceholderAt(props.pokedexRegion, pocket)
}

function displayItem(pocket: number) {
  return itemAt(pocket)
}

function pocketClass(pocket: number) {
  const item = itemAt(pocket)
  const isOver = props.dragId && props.overPocket === `pocket:${pocket}` && props.pockets.get(props.dragId) !== pocket
  const isTarget = props.pickerPocket === pocket
  if (isOver || isTarget) return 'ring-2 ring-(--app-accent)'
  if (!item && !props.readOnly) return `ring-1 ${props.sheet.pocketRing} cursor-pointer hover:ring-(--app-ink-soft)`
  return `ring-1 ${props.sheet.pocketRing}`
}

function isSource(pocket: number) {
  const item = itemAt(pocket)
  return item && props.dragId === item.id
}

function onPocketClick(pocket: number) {
  if (!itemAt(pocket) && !props.readOnly) emit('open-picker', pocket)
}

function onCardClick(pocket: number) {
  const item = itemAt(pocket)
  if (item) emit('detail', item)
}

function onCardPointer(e: PointerEvent, pocket: number) {
  const item = itemAt(pocket)
  if (!item || props.readOnly) return
  emit('card-down', e, item.id, e.currentTarget as HTMLElement)
}
</script>
