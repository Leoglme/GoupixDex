<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-2 sm:gap-4 sm:p-3">
    <div
      class="from-primary/20 to-elevated ring-default/50 relative aspect-[5/7] w-[5.75rem] rounded-lg bg-linear-to-br ring-2 sm:w-24"
    >
      <div
        v-if="!reduceMotion"
        class="goupix-flow-scan-line bg-primary pointer-events-none absolute inset-x-1.5 top-0 h-0.5 rounded-full shadow-[0_0_10px_rgba(232,97,18,0.55)]"
      />
      <UIcon name="i-lucide-scan-line" class="text-primary absolute right-1 bottom-1 size-5 sm:size-6" />
    </div>
    <span class="text-highlighted max-w-[16rem] text-center text-sm font-medium sm:text-base"
      >Lecture & reconnaissance</span
    >
  </div>
</template>

<script setup lang="ts">
defineProps<{
  reduceMotion: boolean
}>()
</script>
