<template>
  <div class="group block w-full" :class="{ 'h-full': fill }">
    <GoupixDexBinderCoverCustom
      v-if="kind === 'custom'"
      :name="name"
      :color-hex="colorHex"
      :layout="layout"
      :fill="fill"
      :texture="texture"
    />

    <!-- mosaic -->
    <div
      v-else-if="kind === 'mosaic'"
      class="relative flex aspect-[63/88] items-center rounded-xl p-2"
      :style="{ backgroundColor: tintBg, ...fillStyle }"
    >
      <span
        v-if="textureClass"
        aria-hidden
        class="pointer-events-none absolute inset-0 z-10 rounded-[inherit]"
        :class="textureClass"
      />
      <div class="grid w-full grid-cols-2 gap-1.5">
        <template v-for="i in 4" :key="i">
          <div v-if="covers[i - 1]" class="card-tile aspect-[63/88]">
            <GoupixDexBinderCardImage :src="covers[i - 1].image_url" :alt="name" />
          </div>
          <div
            v-else
            class="aspect-[63/88] rounded-lg border border-dashed border-(--app-line) bg-(--app-surface-2)/50"
          />
        </template>
      </div>
    </div>

    <!-- showcase -->
    <div
      v-else-if="kind === 'showcase'"
      class="relative flex aspect-[63/88] items-center justify-center overflow-hidden rounded-xl border border-(--app-line) bg-(--app-surface-2)/60"
      :style="showcaseBg"
    >
      <span
        v-if="textureClass"
        aria-hidden
        class="pointer-events-none absolute inset-0 z-10 rounded-[inherit]"
        :class="textureClass"
      />
      <div
        v-if="covers[0]"
        class="card-tile aspect-[63/88] w-[62%] shadow-xl transition-transform duration-300 group-hover:scale-[1.03]"
      >
        <GoupixDexBinderCardImage :src="covers[0].image_url" :alt="name" />
      </div>
      <UIcon v-else name="i-lucide-notebook-tabs" class="h-10 w-10 text-(--app-faint)" aria-hidden />
    </div>

    <!-- fan -->
    <div
      v-else-if="kind === 'fan'"
      class="relative aspect-[63/88] overflow-hidden rounded-xl border border-(--app-line) bg-(--app-surface-2)/60 transition-transform duration-300 group-hover:scale-[1.02]"
      :style="fanBg"
    >
      <span
        v-if="textureClass"
        aria-hidden
        class="pointer-events-none absolute inset-0 z-10 rounded-[inherit]"
        :class="textureClass"
      />
      <div v-if="fanCovers.length === 0" class="absolute inset-0 flex items-center justify-center text-(--app-faint)">
        <UIcon name="i-lucide-notebook-tabs" class="h-10 w-10" aria-hidden />
      </div>
      <div v-else-if="fanCovers.length === 1" class="absolute inset-0 flex items-center justify-center">
        <div class="card-tile aspect-[63/88] w-[62%] shadow-xl">
          <GoupixDexBinderCardImage :src="fanCovers[0].image_url" :alt="name" />
        </div>
      </div>
      <div v-else-if="fanCovers.length === 2" class="absolute inset-0 flex items-center justify-center">
        <div class="card-tile aspect-[63/88] w-[52%] shrink-0 -rotate-6 shadow-xl">
          <GoupixDexBinderCardImage :src="fanCovers[0].image_url" :alt="name" />
        </div>
        <div class="card-tile z-10 -ml-[14%] aspect-[63/88] w-[52%] shrink-0 rotate-6 shadow-xl">
          <GoupixDexBinderCardImage :src="fanCovers[1].image_url" :alt="name" />
        </div>
      </div>
      <div v-else class="absolute inset-0 flex items-center justify-center">
        <div class="card-tile aspect-[63/88] w-[42%] shrink-0 translate-y-[5%] -rotate-[10deg] shadow-xl">
          <GoupixDexBinderCardImage :src="fanCovers[0].image_url" :alt="name" />
        </div>
        <div class="card-tile z-10 -mx-[7%] aspect-[63/88] w-[42%] shrink-0 -translate-y-[2%] shadow-xl">
          <GoupixDexBinderCardImage :src="fanCovers[1].image_url" :alt="name" />
        </div>
        <div class="card-tile aspect-[63/88] w-[42%] shrink-0 translate-y-[5%] rotate-[10deg] shadow-xl">
          <GoupixDexBinderCardImage :src="fanCovers[2].image_url" :alt="name" />
        </div>
      </div>
    </div>

    <!-- label -->
    <div
      v-else-if="kind === 'label'"
      class="relative flex aspect-[63/88] items-center justify-center overflow-hidden rounded-l-md rounded-r-xl border border-(--app-line) bg-(--app-surface-2)"
      :style="{ backgroundColor: colorHex ?? undefined, ...fillStyle }"
    >
      <span
        v-if="textureClass"
        aria-hidden
        class="pointer-events-none absolute inset-0 z-10 rounded-[inherit]"
        :class="textureClass"
      />
      <span aria-hidden class="absolute inset-y-0 left-0 w-2.5 bg-black/20" />
      <span aria-hidden class="absolute inset-y-0 left-2.5 w-px bg-white/20" />
      <div class="mx-6 w-full max-w-[70%] rounded-md bg-[#f5f1e6] px-3 py-4 text-center shadow-md">
        <p class="font-display truncate text-base font-bold text-[#1f1f1f]">{{ name }}</p>
      </div>
    </div>

    <!-- default binder -->
    <div
      v-else
      class="relative aspect-[63/88] overflow-hidden rounded-l-lg rounded-r-xl border border-(--app-line) bg-(--app-surface)"
      :style="fillStyle"
    >
      <span
        v-if="textureClass"
        aria-hidden
        class="pointer-events-none absolute inset-0 z-10 rounded-[inherit]"
        :class="textureClass"
      />
      <div
        class="absolute inset-y-0 left-0 flex w-7 flex-col items-center justify-evenly border-r border-(--app-line) bg-(--app-surface-2) py-3"
        :style="colorHex ? { backgroundColor: colorHex } : undefined"
      >
        <span
          v-for="i in 6"
          :key="i"
          class="h-1.5 w-1.5 rounded-full border border-(--app-line) bg-(--app-surface)"
          aria-hidden
        />
      </div>
      <div class="ml-7 flex h-full items-center p-2.5">
        <div class="grid w-full grid-cols-2 gap-1.5 rounded-lg bg-(--app-surface-2)/40 p-2 ring-1 ring-(--app-line)/60">
          <template v-for="i in 4" :key="i">
            <div v-if="covers[i - 1]" class="card-tile relative aspect-[63/88]">
              <GoupixDexBinderCardImage :src="covers[i - 1].image_url" :alt="name" />
              <span
                aria-hidden
                class="pointer-events-none absolute inset-0 rounded-[inherit] bg-gradient-to-br from-white/10 via-transparent to-transparent"
              />
            </div>
            <div
              v-else
              class="aspect-[63/88] rounded-lg border border-dashed border-(--app-line) bg-(--app-surface-2)/50"
            />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { binderStyle } from '~/utils/binder/binder-styles'
import type { CoverTexture } from '~/utils/binder/binder-design'
import { coverTextureClass } from '~/utils/binder/binder-design'
import type { CoverRender } from '~/utils/binder/binder-cover'

export type CoverItem = { image_url: string }

const props = withDefaults(
  defineProps<{
    coverStyle: string | null
    covers: CoverItem[]
    name: string
    colorHex: string | null
    fill?: boolean
    texture?: CoverTexture
    layout?: CoverRender | null
  }>(),
  { fill: false, texture: 'plain', layout: null },
)

const kind = computed(() => binderStyle(props.coverStyle))
const fanCovers = computed(() => props.covers.slice(0, 3))
const fillStyle = computed(() => (props.fill ? { aspectRatio: 'auto', height: '100%' } : undefined))
const tintBg = computed(() => (props.colorHex ? `${props.colorHex}1f` : undefined))
const showcaseBg = computed(() => ({
  ...fillStyle.value,
  backgroundImage: props.colorHex
    ? `radial-gradient(ellipse at 50% 35%, ${props.colorHex}59, transparent 70%)`
    : undefined,
}))
const fanBg = computed(() => ({
  ...fillStyle.value,
  backgroundImage: props.colorHex
    ? `radial-gradient(ellipse at 50% 60%, ${props.colorHex}47, transparent 72%)`
    : undefined,
}))

const textureClass = computed(() => coverTextureClass(props.texture))
</script>
