<template>
  <div
    class="[container-type:inline-size] relative aspect-[63/88] overflow-hidden rounded-l-lg rounded-r-xl border border-(--app-line) bg-(--app-surface-2)"
    :style="{ backgroundColor: bg?.color ?? colorHex ?? undefined, ...fillStyle }"
  >
    <div v-if="bg?.imageUrl && bg.imageIsCard" class="absolute inset-0">
      <GoupixDexBinderCardImage :src="bg.imageUrl" alt="" />
    </div>
    <img v-else-if="bg?.imageUrl" :src="bg.imageUrl" alt="" class="absolute inset-0 h-full w-full object-cover" />
    <span
      v-if="bg?.imageUrl && bg.dim > 0"
      aria-hidden
      class="absolute inset-0"
      :style="{ backgroundColor: `rgba(0,0,0,${bg.dim / 100})` }"
    />
    <span
      aria-hidden
      class="pointer-events-none absolute inset-y-0 left-0 w-[7cqw] bg-gradient-to-r from-black/35 to-transparent"
    />
    <span
      v-if="textureClass"
      aria-hidden
      class="pointer-events-none absolute inset-0 z-10 rounded-[inherit]"
      :class="textureClass"
    />
    <div
      v-if="hasContent && layout"
      class="absolute inset-0 z-20 grid grid-cols-3 grid-rows-3 gap-[3cqw] p-[6cqw] pl-[8cqw]"
    >
      <div v-for="z in ZONES" :key="z" class="flex min-w-0" :class="zoneClass(z)">
        <GoupixDexBinderCoverElement v-if="layout.zones[z]" :el="layout.zones[z]!" />
      </div>
    </div>
    <div v-else class="absolute inset-0 z-20 flex items-center justify-center p-[10cqw]">
      <span
        class="font-display text-center text-[9cqw] leading-tight font-bold text-white/85 drop-shadow-[0_1px_2px_rgba(0,0,0,.5)]"
      >
        {{ name }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ZONES, coverHasContent, type CoverRender, type ZoneKey } from '~/utils/binder/binder-cover'
import { coverTextureClass, type CoverTexture } from '~/utils/binder/binder-design'

const props = withDefaults(
  defineProps<{
    name: string
    colorHex: string | null
    layout?: CoverRender | null
    fill?: boolean
    texture?: CoverTexture
  }>(),
  { fill: false, texture: 'plain', layout: null },
)

const bg = computed(() => props.layout?.bg)
const hasContent = computed(() => coverHasContent(props.layout))
const fillStyle = computed(() => (props.fill ? { aspectRatio: 'auto', height: '100%' } : undefined))
const textureClass = computed(() => coverTextureClass(props.texture ?? 'plain'))

function zoneClass(z: ZoneKey): string {
  const row = z[0] === 't' ? 'items-start' : z[0] === 'm' ? 'items-center' : 'items-end'
  const col =
    z[1] === 'l' ? 'justify-start text-left' : z[1] === 'c' ? 'justify-center text-center' : 'justify-end text-right'
  return `${row} ${col}`
}
</script>
