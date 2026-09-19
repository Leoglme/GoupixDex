<template>
  <span
    v-for="t in positions"
    :key="t"
    aria-hidden
    class="absolute h-3 w-3 -translate-y-1/2 rounded-full shadow-[inset_0_1px_2px_rgba(0,0,0,.9),0_0_0_1px_rgba(255,255,255,.06)]"
    :class="[cls, side === 'left' ? 'left-2' : 'right-2']"
    :style="{ top: `${t * 100}%` }"
  />
</template>

<script setup lang="ts">
defineProps<{
  side: 'left' | 'right'
  positions: number[]
  cls: string
}>()
</script>
