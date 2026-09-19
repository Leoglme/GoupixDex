<template>
  <div class="relative z-20 w-9 shrink-0 self-stretch" :class="extraClass" aria-hidden>
    <div
      class="absolute inset-x-0 -inset-y-1.5 overflow-hidden rounded-md bg-(--app-surface-2)"
      :style="colorHex ? { backgroundColor: colorHex } : undefined"
    >
      <div class="absolute inset-0 rounded-md bg-gradient-to-r from-black/40 via-white/10 to-black/45" />
      <span v-if="textureClass" class="absolute inset-0 rounded-md" :class="textureClass" />
    </div>
    <span
      v-for="t in ringPos"
      :key="t"
      class="absolute left-1/2 h-4 w-16 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] shadow-[0_1px_2px_rgba(0,0,0,.7),inset_0_1px_1px_rgba(255,255,255,.5)]"
      :style="{ top: `${t * 100}%`, borderColor: ringColor }"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  colorHex: string | null
  ringPos: number[]
  ringColor: string
  textureClass: string
  extraClass?: string
}>()
</script>
