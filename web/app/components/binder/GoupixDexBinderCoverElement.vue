<template>
  <span
    v-if="el.type === 'text'"
    class="max-w-[88cqw] shrink-0 leading-tight break-words drop-shadow-[0_1px_2px_rgba(0,0,0,.45)]"
    :class="[fontClass[el.font], textSizeClass[el.size], el.weight === 'bold' ? 'font-bold' : 'font-normal']"
    :style="{ color: el.color }"
  >
    {{ el.text }}
  </span>
  <img
    v-else-if="el.type === 'logo'"
    :src="`${el.url}.png`"
    alt=""
    loading="lazy"
    class="shrink-0 object-contain drop-shadow-[0_2px_4px_rgba(0,0,0,.5)]"
    :class="mediaWidth[el.size]"
  />
  <img
    v-else-if="el.type === 'image'"
    :src="el.url"
    alt=""
    loading="lazy"
    class="shrink-0 shadow-lg"
    :class="[mediaWidth[el.size], imageShapeClass(el.shape)]"
  />
  <div v-else class="card-tile aspect-[63/88] shrink-0" :class="cardWidth[el.size]">
    <GoupixDexBinderCardImage :src="el.url" alt="" />
  </div>
</template>

<script setup lang="ts">
import type { ImageShape, RenderElement } from '~/utils/binder/binder-cover'

defineProps<{ el: RenderElement }>()

const textSizeClass = {
  sm: 'text-[4.5cqw]',
  md: 'text-[6.5cqw]',
  lg: 'text-[9cqw]',
  xl: 'text-[13cqw]',
} as const

const fontClass = { display: 'font-display', sans: '', mono: 'font-mono' } as const
const mediaWidth = { sm: 'w-[16cqw]', md: 'w-[22cqw]', lg: 'w-[28cqw]' } as const
const cardWidth = { sm: 'w-[16cqw]', md: 'w-[22cqw]', lg: 'w-[28cqw]' } as const

function imageShapeClass(shape: ImageShape): string {
  if (shape === 'round') return 'aspect-square rounded-full object-cover'
  if (shape === 'free') return 'h-auto max-h-[42cqw] rounded-[2cqw] object-contain'
  return 'aspect-square rounded-[2cqw] object-cover'
}
</script>
